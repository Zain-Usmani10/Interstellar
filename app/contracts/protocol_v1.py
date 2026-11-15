"""Interstellar wire protocol v1: reference implementation (standard library only).

This module is the executable form of ``protocol_v1.json``. It generates the golden
frames in ``fixtures/frames/`` and is used by the simulated controller and the tests.
The FPGA (Verilog) and the production serial transport must agree with it byte for byte.

Frame layout (all multi-byte numbers unsigned little-endian):

    offset  size  field
    0       2     magic A5 5A
    2       1     version = 1
    3       1     message type
    4       2     sequence
    6       4     session_id
    10      2     payload_length (<= 128)
    12      N     payload
    12+N    2     CRC-16/CCITT-FALSE over bytes [2 .. 12+N)  (magic and CRC excluded)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

MAGIC = b"\xA5\x5A"
VERSION = 1
HEADER_LEN = 12
CRC_LEN = 2
MAX_PAYLOAD = 128
MAX_FRAME = HEADER_LEN + MAX_PAYLOAD + CRC_LEN  # 142
INCOMPLETE_FRAME_TIMEOUT_S = 0.100
UNSET_TICK = 0xFFFFFFFF
TICK_HZ = 100
MAX_END_TICK = 360000


class MsgType(IntEnum):
    DISCOVER = 0x01
    OPEN_SESSION = 0x02
    GET_STATUS = 0x03
    LOAD_PLAN = 0x10
    COMMIT_PLAN = 0x11
    ARM = 0x12
    START = 0x13
    ABORT = 0x14
    CLEAR = 0x15
    SET_TRIP_DAYS = 0x16      # contracts 1.2.0: display only, plan section 18.3
    ACK = 0x80
    STATUS = 0x81


# Exact payload length per message type. A frame with any other length is discarded.
PAYLOAD_LEN = {
    MsgType.DISCOVER: 0,
    MsgType.OPEN_SESSION: 4,
    MsgType.GET_STATUS: 0,
    MsgType.LOAD_PLAN: 28,
    MsgType.COMMIT_PLAN: 6,
    MsgType.ARM: 4,
    MsgType.START: 4,
    MsgType.ABORT: 4,
    MsgType.CLEAR: 4,
    MsgType.SET_TRIP_DAYS: 8,
    MsgType.ACK: 16,
    MsgType.STATUS: 40,
}

READ_ONLY_TYPES = (MsgType.DISCOVER, MsgType.GET_STATUS)
MUTATION_TYPES = (MsgType.LOAD_PLAN, MsgType.COMMIT_PLAN, MsgType.ARM,
                  MsgType.START, MsgType.ABORT, MsgType.CLEAR, MsgType.SET_TRIP_DAYS)

MAX_TRIP_DAYS = 9999


class State(IntEnum):
    IDLE = 0
    LOADED = 1
    ARMED = 2
    RUNNING = 3
    SAFE = 4
    COMPLETE = 5
    ABORTED = 6


class Result(IntEnum):
    APPLIED = 0
    REJECTED = 1


class Detail(IntEnum):
    OK = 0
    BAD_STATE = 1
    BAD_MISSION = 2
    BAD_SESSION = 3
    BAD_PLAN = 4
    BAD_PLAN_CRC = 5
    SEQ_CONFLICT = 6
    STALE_SEQ = 7
    INSUFFICIENT_FUEL = 8
    UNSUPPORTED = 9


class SafeReason(IntEnum):
    NONE = 0
    NO_MAJORITY = 1
    ILLEGAL_STATE = 2
    FUEL = 3
    INTERNAL_INVARIANT = 4


MASK_DEPARTURE = 0x01
MASK_CAPTURE = 0x02


def crc16_ccitt_false(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, xorout 0.

    Check value: crc16_ccitt_false(b"123456789") == 0x29B1.
    """
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class FrameError(ValueError):
    """A byte string is not one valid frame. ``code`` says why."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class Frame:
    msg_type: int
    sequence: int
    session_id: int
    payload: bytes = b""


def encode_frame(msg_type: int, sequence: int, session_id: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise FrameError("OVERSIZE", "payload longer than 128 bytes")
    body = struct.pack("<BBHIH", VERSION, msg_type, sequence, session_id, len(payload)) + payload
    return MAGIC + body + struct.pack("<H", crc16_ccitt_false(body))


def decode_frame(data: bytes) -> Frame:
    """Decode exactly one complete frame. Raises FrameError on any integrity problem."""
    if len(data) < HEADER_LEN + CRC_LEN:
        raise FrameError("TRUNCATED")
    if data[:2] != MAGIC:
        raise FrameError("BAD_MAGIC")
    version, msg_type, sequence, session_id, length = struct.unpack_from("<BBHIH", data, 2)
    if version != VERSION:
        raise FrameError("BAD_VERSION")
    if length > MAX_PAYLOAD:
        raise FrameError("OVERSIZE")
    if len(data) != HEADER_LEN + length + CRC_LEN:
        raise FrameError("LENGTH_MISMATCH")
    (crc,) = struct.unpack_from("<H", data, HEADER_LEN + length)
    if crc != crc16_ccitt_false(data[2:HEADER_LEN + length]):
        raise FrameError("BAD_CRC")
    return Frame(msg_type, sequence, session_id, bytes(data[HEADER_LEN:HEADER_LEN + length]))


def shape_ok(frame: Frame) -> bool:
    """True when the type is known and the payload has that type's exact length."""
    try:
        return PAYLOAD_LEN[MsgType(frame.msg_type)] == len(frame.payload)
    except ValueError:
        return False


class StreamParser:
    """Reference byte-stream parser: fragmented input, garbage, false magic, bad CRC.

    Feed raw bytes; get back complete CRC-valid frames. Nothing is returned for a frame
    until all of it has arrived and its CRC matches. Counters record what was dropped.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._candidate_since: float | None = None
        self.garbage_bytes = 0
        self.bad_version = 0
        self.oversize = 0
        self.bad_crc = 0
        self.timeouts = 0

    def _drop(self, count: int) -> None:
        del self._buf[:count]
        self.garbage_bytes += count
        self._candidate_since = None

    def feed(self, data: bytes, now: float = 0.0) -> list[Frame]:
        """Add bytes received at monotonic time ``now`` (seconds); return finished frames."""
        frames: list[Frame] = []
        # A half-received candidate older than the timeout is abandoned: rescan after its magic.
        if (self._candidate_since is not None and self._buf
                and now - self._candidate_since > INCOMPLETE_FRAME_TIMEOUT_S):
            self.timeouts += 1
            self._drop(1)
        self._buf += data
        while True:
            start = self._buf.find(MAGIC)
            if start < 0:
                # Keep a trailing A5: it may be the first half of the next magic.
                keep = 1 if self._buf.endswith(MAGIC[:1]) else 0
                self._drop(len(self._buf) - keep)
                break
            if start:
                self._drop(start)
            if self._candidate_since is None:
                self._candidate_since = now
            if len(self._buf) < HEADER_LEN:
                break
            version, _type, _seq, _session, length = struct.unpack_from("<BBHIH", self._buf, 2)
            if version != VERSION:
                self.bad_version += 1
                self._drop(1)
                continue
            if length > MAX_PAYLOAD:
                self.oversize += 1
                self._drop(1)
                continue
            total = HEADER_LEN + length + CRC_LEN
            if len(self._buf) < total:
                break
            try:
                frames.append(decode_frame(bytes(self._buf[:total])))
            except FrameError:
                self.bad_crc += 1
                self._drop(1)
                continue
            del self._buf[:total]
            self._candidate_since = None
        return frames


# ---------------------------------------------------------------- payloads

@dataclass(frozen=True)
class Plan:
    """LOAD_PLAN payload: seven u32, 28 bytes."""
    mission_id: int
    departure_tick: int
    arrival_tick: int
    end_tick: int
    initial_fuel_g: int
    departure_fuel_g: int
    capture_fuel_g: int

    def pack(self) -> bytes:
        return struct.pack("<7I", self.mission_id, self.departure_tick, self.arrival_tick,
                           self.end_tick, self.initial_fuel_g, self.departure_fuel_g,
                           self.capture_fuel_g)

    @classmethod
    def unpack(cls, payload: bytes) -> "Plan":
        return cls(*struct.unpack("<7I", payload))

    def crc16(self) -> int:
        """plan_crc16: CRC over exactly these 28 payload bytes."""
        return crc16_ccitt_false(self.pack())

    def problem(self) -> str | None:
        """Why the board must reject this plan with BAD_PLAN, or None if it is valid."""
        if self.mission_id == 0:
            return "mission_id is zero"
        if not 0 < self.departure_tick < self.arrival_tick < self.end_tick <= MAX_END_TICK:
            return "need 0 < departure_tick < arrival_tick < end_tick <= 360000"
        if self.departure_fuel_g == 0 or self.capture_fuel_g == 0:
            return "fuel costs must be nonzero"
        if self.departure_fuel_g + self.capture_fuel_g > self.initial_fuel_g:
            return "fuel costs exceed initial fuel"
        return None


def pack_u32(value: int) -> bytes:
    """Payload of OPEN_SESSION (new session id) and ARM/START/ABORT/CLEAR (mission id)."""
    return struct.pack("<I", value)


def unpack_u32(payload: bytes) -> int:
    return struct.unpack("<I", payload)[0]


def pack_trip_days(mission_id: int, trip_days: int) -> bytes:
    """Payload of SET_TRIP_DAYS: the planned trip (departure to arrival tick) lasts trip_days days."""
    return struct.pack("<II", mission_id, trip_days)


def unpack_trip_days(payload: bytes) -> tuple[int, int]:
    return struct.unpack("<II", payload)


def trip_days_from_tof(tof_s: float) -> int:
    """Whole days of the trip, rounded half up and kept inside 1..MAX_TRIP_DAYS."""
    return max(1, min(MAX_TRIP_DAYS, int(tof_s / 86400.0 + 0.5)))


def days_to_arrival(tick: int, departure_tick: int, arrival_tick: int, trip_days: int) -> int:
    """Shared countdown formula (integers only); the board computes the same value."""
    if tick <= departure_tick:
        return trip_days
    if tick >= arrival_tick:
        return 0
    return trip_days - (tick - departure_tick) * trip_days // (arrival_tick - departure_tick)


def pack_commit(mission_id: int, plan_crc16: int) -> bytes:
    return struct.pack("<IH", mission_id, plan_crc16)


def unpack_commit(payload: bytes) -> tuple[int, int]:
    return struct.unpack("<IH", payload)


@dataclass(frozen=True)
class Ack:
    """ACK/NACK payload, 16 bytes."""
    original_type: int
    result: int
    detail: int
    mission_id: int
    applied_tick: int
    plan_crc16: int

    def pack(self) -> bytes:
        return struct.pack("<BBHIIHH", self.original_type, self.result, self.detail,
                           self.mission_id, self.applied_tick, self.plan_crc16, 0)

    @classmethod
    def unpack(cls, payload: bytes) -> "Ack":
        return cls(*struct.unpack("<BBHIIHH", payload)[:6])


@dataclass(frozen=True)
class Status:
    """STATUS payload, 40 bytes. One atomic snapshot of the controller."""
    mission_id: int = 0
    tick: int = 0
    state: int = State.IDLE
    executed_mask: int = 0
    safe_reason: int = SafeReason.NONE
    fuel_remaining_g: int = 0
    departure_executed_tick: int = UNSET_TICK
    capture_executed_tick: int = UNSET_TICK
    masked_fault_count: int = 0
    no_majority_count: int = 0
    rx_error_count: int = 0
    plan_crc16: int = 0

    def pack(self) -> bytes:
        return struct.pack("<IIBBBBIIIIIIHH", self.mission_id, self.tick, self.state,
                           self.executed_mask, self.safe_reason, 0, self.fuel_remaining_g,
                           self.departure_executed_tick, self.capture_executed_tick,
                           self.masked_fault_count, self.no_majority_count,
                           self.rx_error_count, self.plan_crc16, 0)

    @classmethod
    def unpack(cls, payload: bytes) -> "Status":
        f = struct.unpack("<IIBBBBIIIIIIHH", payload)
        return cls(f[0], f[1], f[2], f[3], f[4], f[6], f[7], f[8], f[9], f[10], f[11], f[12])
