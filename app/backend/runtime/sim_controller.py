"""Simulated mission controller: a software stand-in for the DE10-Lite sequencer.

It speaks protocol v1 byte for byte and follows the state rules in
docs/plan/MAIN_BACKEND_FPGA_TASKS.md sections 7 and 8, so the backend, the browser and the
tests can run with no hardware. Anything driven by it is labelled SIMULATED CONTROLLER.
It is not evidence that the real FPGA works.

Differences from the board, on purpose:
  * No triplicated registers. ``inject_single`` / ``inject_divergence`` reproduce only the
    visible outcome (a counted masked fault, or a SAFE latch with NO_MAJORITY).
  * Ticks are computed from a clock when something asks, not by a 100 Hz hardware divider.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from app.contracts import protocol_v1 as p
from app.contracts.transport import TransportError

T, S, D, R = p.MsgType, p.State, p.Detail, p.Result


class SimulatedController:
    def __init__(self, clock: Callable[[], float] = time.monotonic, speed: float = 1.0):
        self._clock = clock
        self._speed = speed            # 1.0 = real 100 Hz ticks; tests may run faster
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Power-on / reprogram: IDLE, no session, no plan. Never auto-resumes."""
        self.session = 0
        self.state = S.IDLE
        self.staged: p.Plan | None = None
        self.plan: p.Plan | None = None
        self.tick = 0
        self.mask = 0
        self.fuel = 0
        self.departure_tick = p.UNSET_TICK
        self.capture_tick = p.UNSET_TICK
        self.safe_reason = p.SafeReason.NONE
        self.masked_faults = 0
        self.no_majority = 0
        self.rx_errors = 0
        self._clock_running = False    # run-clock latch: keeps ticking in SAFE/ABORTED
        self._t0 = 0.0
        self._last_seq = 0
        self._last_cmd = b""
        self._last_reply = b""
        self._telemetry_seq = 0

    # ------------------------------------------------------------ time and events

    def _advance(self) -> None:
        """Bring the tick counter up to the clock and fire any burn that became due."""
        if not self._clock_running or self.plan is None:
            return
        target = min(int((self._clock() - self._t0) * p.TICK_HZ * self._speed), self.plan.end_tick)
        plan = self.plan
        if self.state == S.RUNNING and not self.mask & p.MASK_DEPARTURE and target >= plan.departure_tick:
            self._burn(plan.departure_fuel_g, p.MASK_DEPARTURE, plan.departure_tick)
        if self.state == S.RUNNING and self.mask == p.MASK_DEPARTURE and target >= plan.arrival_tick:
            self._burn(plan.capture_fuel_g, p.MASK_CAPTURE, plan.arrival_tick)
            if self.state == S.RUNNING:          # capture succeeded: mission ends at this tick
                self.state = S.COMPLETE
                self.tick = plan.arrival_tick
                self._clock_running = False
                return
        self.tick = max(self.tick, target)
        if self.tick >= plan.end_tick:
            self._clock_running = False

    def _burn(self, cost_g: int, bit: int, at_tick: int) -> None:
        """Deduct fuel and record the event once, or latch SAFE if the ledger cannot pay."""
        if cost_g > self.fuel:
            self.state, self.safe_reason = S.SAFE, p.SafeReason.FUEL
            return
        self.fuel -= cost_g
        self.mask |= bit
        if bit == p.MASK_DEPARTURE:
            self.departure_tick = at_tick
        else:
            self.capture_tick = at_tick

    # ------------------------------------------------------------ fault injection (demo switches)

    def inject_single(self) -> None:
        """One lane upset: majority holds, the fault is counted, the mission continues."""
        with self._lock:
            self._advance()
            self.masked_faults += 1

    def inject_divergence(self) -> None:
        """All three lanes differ: no majority. Armed or executing missions latch SAFE."""
        with self._lock:
            self._advance()
            self.no_majority += 1
            if self.state in (S.ARMED, S.RUNNING):
                self.state, self.safe_reason = S.SAFE, p.SafeReason.NO_MAJORITY

    # ------------------------------------------------------------ frames

    def status_frame(self) -> bytes:
        with self._lock:
            return self._status_frame()

    def _status_frame(self) -> bytes:
        self._advance()
        status = p.Status(
            self.plan.mission_id if self.plan else 0, self.tick, self.state, self.mask,
            self.safe_reason, self.fuel, self.departure_tick, self.capture_tick,
            self.masked_faults, self.no_majority, self.rx_errors,
            self.plan.crc16() if self.plan else 0)
        frame = p.encode_frame(T.STATUS, self._telemetry_seq, self.session, status.pack())
        self._telemetry_seq = (self._telemetry_seq + 1) & 0xFFFF
        return frame

    def _ack(self, request: p.Frame, detail: D, mission_id: int) -> bytes:
        crc = 0
        if request.msg_type == T.LOAD_PLAN and self.staged and detail == D.OK:
            crc = self.staged.crc16()
        elif self.plan:
            crc = self.plan.crc16()
        elif self.staged:
            # No active plan: report the staged plan's CRC (golden frame 29, same as the FPGA).
            crc = self.staged.crc16()
        result = R.APPLIED if detail == D.OK else R.REJECTED
        ack = p.Ack(request.msg_type, result, detail, mission_id, self.tick, crc)
        return p.encode_frame(T.ACK, request.sequence, self.session, ack.pack())

    def handle(self, data: bytes) -> bytes | None:
        """Process one received frame. Returns the reply frame, or None if it was discarded."""
        with self._lock:
            try:
                frame = p.decode_frame(data)
            except p.FrameError:
                self.rx_errors += 1
                return None
            if not p.shape_ok(frame) or frame.msg_type in (T.ACK, T.STATUS):
                self.rx_errors += 1
                return None
            self._advance()
            if frame.msg_type in p.READ_ONLY_TYPES:
                return self._status_frame()
            if frame.msg_type == T.OPEN_SESSION:
                return self._open_session(frame)
            return self._mutation(frame, data)

    def _open_session(self, frame: p.Frame) -> bytes:
        new_id = p.unpack_u32(frame.payload)
        if self.state != S.IDLE:
            return self._ack(frame, D.BAD_STATE, 0)
        if new_id == 0 or frame.session_id != 0:
            return self._ack(frame, D.BAD_SESSION, 0)
        if new_id != self.session:       # an identical repeat keeps the sequence history
            self.session = new_id
            self._last_seq, self._last_cmd, self._last_reply = 0, b"", b""
            self.staged = None
        return self._ack(frame, D.OK, 0)

    def _mutation(self, frame: p.Frame, raw: bytes) -> bytes:
        mission_id = p.unpack_u32(frame.payload[:4])
        if self.session == 0 or frame.session_id != self.session:
            return self._ack(frame, D.BAD_SESSION, mission_id)
        if frame.sequence == self._last_seq and self._last_seq:
            if raw == self._last_cmd:
                return self._last_reply                      # exact retry: do not apply again
            return self._ack(frame, D.SEQ_CONFLICT, mission_id)
        if frame.sequence < self._last_seq or frame.sequence == 0:
            return self._ack(frame, D.STALE_SEQ, mission_id)
        reply = self._ack(frame, self._apply(frame, mission_id), mission_id)
        self._last_seq, self._last_cmd, self._last_reply = frame.sequence, raw, reply
        return reply

    def _apply(self, frame: p.Frame, mission_id: int) -> D:
        """State/value guards, then the change. Returns OK or the rejection detail."""
        kind = frame.msg_type
        if kind == T.LOAD_PLAN:
            if self.state != S.IDLE:
                return D.BAD_STATE
            plan = p.Plan.unpack(frame.payload)
            if plan.problem():
                return D.BAD_PLAN
            self.staged = plan
            return D.OK
        if kind == T.COMMIT_PLAN:
            _, crc = p.unpack_commit(frame.payload)
            if self.state != S.IDLE:
                return D.BAD_STATE
            if self.staged is None or self.staged.mission_id != mission_id:
                return D.BAD_MISSION
            if self.staged.crc16() != crc:
                return D.BAD_PLAN_CRC
            self.plan, self.staged = self.staged, None
            self.state, self.tick, self.mask = S.LOADED, 0, 0
            self.fuel = self.plan.initial_fuel_g
            self.departure_tick = self.capture_tick = p.UNSET_TICK
            self.safe_reason = p.SafeReason.NONE
            return D.OK
        # ARM, START, ABORT, CLEAR all need an active mission with a matching id.
        if self.plan is None:
            return D.BAD_STATE
        if self.plan.mission_id != mission_id:
            return D.BAD_MISSION
        if kind == T.ARM:
            if self.state != S.LOADED:
                return D.BAD_STATE
            self.state = S.ARMED
        elif kind == T.START:
            if self.state != S.ARMED:
                return D.BAD_STATE
            self.state, self.tick = S.RUNNING, 0
            self._t0, self._clock_running = self._clock(), True
        elif kind == T.ABORT:
            if self.state not in (S.LOADED, S.ARMED, S.RUNNING, S.SAFE):
                return D.BAD_STATE
            self.state = S.ABORTED               # the run clock, if started, keeps going
        elif kind == T.CLEAR:
            if self.state == S.RUNNING:
                return D.BAD_STATE
            session = self.session
            seq = self._last_seq
            self.reset_mission()
            self.session, self._last_seq = session, seq
        return D.OK

    def reset_mission(self) -> None:
        """CLEAR: drop the plan and stop the clock, keep session and fault counters."""
        self.state, self.plan, self.staged = S.IDLE, None, None
        self.tick, self.mask, self.fuel = 0, 0, 0
        self.departure_tick = self.capture_tick = p.UNSET_TICK
        self.safe_reason = p.SafeReason.NONE
        self._clock_running = False


class SimulatorTransport:
    """Transport (see app/contracts/transport.py) backed by a SimulatedController."""

    controller_source = "simulator"
    STATUS_PERIOD_S = 0.1          # the board emits STATUS at 10 Hz

    def __init__(self, controller: SimulatedController | None = None):
        self.controller = controller or SimulatedController()
        self._rx: deque[bytes] = deque(maxlen=128)
        self._open = False
        self._next_status = 0.0
        self._sent = self._received = 0

    def open(self) -> None:
        self._open = True
        self._next_status = time.monotonic() + self.STATUS_PERIOD_S

    def close(self) -> None:
        self._open = False
        self._rx.clear()

    def is_open(self) -> bool:
        return self._open

    def send(self, frame: bytes) -> None:
        if not self._open:
            raise TransportError("simulator transport is closed")
        self._sent += 1
        reply = self.controller.handle(frame)
        if reply is not None:
            self._rx.append(reply)

    def receive(self, timeout_s: float) -> bytes | None:
        if not self._open:
            raise TransportError("simulator transport is closed")
        deadline = time.monotonic() + timeout_s
        while True:
            if self._rx:
                self._received += 1
                return self._rx.popleft()
            now = time.monotonic()
            if now >= self._next_status:
                self._next_status = now + self.STATUS_PERIOD_S
                self._rx.append(self.controller.status_frame())
                continue
            if now >= deadline:
                return None
            time.sleep(min(deadline, self._next_status) - now)

    def stats(self) -> dict:
        return {"frames_sent": self._sent, "frames_received": self._received,
                "rx_errors": self.controller.rx_errors}
