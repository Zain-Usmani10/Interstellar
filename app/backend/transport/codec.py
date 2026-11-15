"""Strict protocol-v1 codec and bounded incremental serial parser."""
from __future__ import annotations

import struct
from collections import Counter

from app.contracts import protocol_v1 as p


def decode_frame(raw: bytes) -> p.Frame:
    frame = p.decode_frame(raw)
    if not p.shape_ok(frame):
        raise p.FrameError("BAD_SHAPE")
    return frame


def encode_frame(msg_type: int, sequence: int, session_id: int, payload: bytes = b"") -> bytes:
    raw = p.encode_frame(msg_type, sequence, session_id, payload)
    decode_frame(raw)
    return raw


class StreamParser:
    """At most one 142-byte candidate is retained, regardless of input chunk size."""

    def __init__(self):
        self.buffer = bytearray()
        self.since = None
        self.errors = Counter()

    def _drop(self, n=1):
        del self.buffer[:n]
        self.since = None

    def feed(self, data: bytes, now: float) -> list[bytes]:
        frames = []
        if self.since is not None and now - self.since >= 0.1:
            self.errors["timeout"] += 1
            self._drop()
        # Process each byte so a huge garbage read cannot grow the retained buffer.
        for byte in data:
            self.buffer.append(byte)
            self._scan(now, frames)
        self._scan(now, frames)
        return frames

    def _scan(self, now, frames):
        while self.buffer:
            start = self.buffer.find(p.MAGIC)
            if start < 0:
                keep = int(self.buffer[-1] == p.MAGIC[0])
                count = len(self.buffer) - keep
                if count:
                    self.errors["garbage_bytes"] += count
                    self._drop(count)
                if keep and self.since is None:
                    self.since = now
                return
            if start:
                self.errors["garbage_bytes"] += start
                self._drop(start)
            if self.since is None:
                self.since = now
            if len(self.buffer) < p.HEADER_LEN:
                return
            version, kind, _, _, size = struct.unpack_from("<BBHIH", self.buffer, 2)
            if version != 1 or size > 128 or p.PAYLOAD_LEN.get(kind) != size:
                self.errors["header"] += 1
                self._drop()
                continue
            total = 14 + size
            if len(self.buffer) < total:
                return
            raw = bytes(self.buffer[:total])
            try:
                decode_frame(raw)
            except p.FrameError:
                self.errors["crc"] += 1
                self._drop()
                continue
            frames.append(raw)
            self._drop(total)
