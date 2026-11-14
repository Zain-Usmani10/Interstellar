"""Stop-and-wait command link over any Transport.

One instance is used by exactly one thread (the transport worker in mission.py).
It owns the wire session id and the mutation sequence counter, resends the identical frame
on timeout, and only reports success when the controller's ACK arrives. A write that was
merely sent is never treated as acknowledged.
"""
from __future__ import annotations

import secrets
import time
from typing import Callable

from app.contracts import protocol_v1 as p
from app.contracts.transport import Transport

T = p.MsgType


class LinkError(Exception):
    """No valid reply after all attempts. The command may or may not have been applied."""


class Link:
    def __init__(self, transport: Transport, on_status: Callable[[int, p.Status], None],
                 retry_timeout_s: float = 0.5, attempts: int = 3):
        self.transport = transport
        self.on_status = on_status          # called with (board session id, Status) for every STATUS
        self.retry_timeout_s = retry_timeout_s
        self.attempts = attempts
        self.session_id = 0
        self.next_seq = 1

    def pump(self, timeout_s: float) -> p.Frame | None:
        """Receive at most one frame. STATUS frames go to on_status; the frame is returned."""
        raw = self.transport.receive(timeout_s)
        if raw is None:
            return None
        try:
            frame = p.decode_frame(raw)
        except p.FrameError:
            return None
        if frame.msg_type == T.STATUS and p.shape_ok(frame):
            self.on_status(frame.session_id, p.Status.unpack(frame.payload))
        return frame

    def _exchange(self, request: bytes, accept: Callable[[p.Frame], bool]) -> p.Frame:
        for _ in range(self.attempts):
            self.transport.send(request)             # the same bytes every attempt
            deadline = time.monotonic() + self.retry_timeout_s
            while (remaining := deadline - time.monotonic()) > 0:
                frame = self.pump(remaining)
                if frame is not None and p.shape_ok(frame) and accept(frame):
                    return frame
        raise LinkError(f"no reply after {self.attempts} attempts")

    def read_status(self) -> tuple[int, p.Status]:
        """GET_STATUS. Returns (board's active session id, Status)."""
        frame = self._exchange(p.encode_frame(T.GET_STATUS, 0, self.session_id),
                               lambda f: f.msg_type == T.STATUS)
        return frame.session_id, p.Status.unpack(frame.payload)

    def open_session(self) -> p.Ack:
        """Start a fresh session with a random nonzero id. Only valid while the board is IDLE."""
        new_id = secrets.randbelow(0xFFFFFFFF) + 1
        request = p.encode_frame(T.OPEN_SESSION, 0, 0, p.pack_u32(new_id))
        frame = self._exchange(request, lambda f: f.msg_type == T.ACK and f.sequence == 0
                               and p.Ack.unpack(f.payload).original_type == T.OPEN_SESSION)
        ack = p.Ack.unpack(frame.payload)
        if ack.result == p.Result.APPLIED and frame.session_id == new_id:
            self.session_id, self.next_seq = new_id, 1
        return ack

    def mutate(self, msg_type: int, payload: bytes) -> p.Ack:
        """Send one mutation and wait for the ACK that matches its type and sequence."""
        if self.next_seq > 0xFFFF:
            raise LinkError("sequence exhausted; open a fresh session while IDLE")
        seq = self.next_seq
        request = p.encode_frame(msg_type, seq, self.session_id, payload)
        frame = self._exchange(request, lambda f: f.msg_type == T.ACK and f.sequence == seq
                               and p.Ack.unpack(f.payload).original_type == msg_type)
        ack = p.Ack.unpack(frame.payload)
        # The board consumes the sequence for APPLIED and for guard rejections, but not for
        # session/sequence errors.
        if ack.detail not in (p.Detail.BAD_SESSION, p.Detail.SEQ_CONFLICT, p.Detail.STALE_SEQ):
            self.next_seq = seq + 1
        return ack
