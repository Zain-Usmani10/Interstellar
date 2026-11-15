"""Run: python -m unittest discover -s app/tests/transport -v."""
import json
import unittest
from collections import deque
from pathlib import Path

from app.contracts import protocol_v1 as p
from app.contracts.transport import TransportError
from app.backend.transport import DelayTransport, SerialTransport, create_transport
from app.backend.transport.codec import StreamParser, decode_frame, encode_frame


class CodecTests(unittest.TestCase):
    def test_all_golden_frames_and_every_stream_split(self):
        root = Path(p.__file__).parent / "fixtures" / "frames"
        manifest = json.loads((root / "manifest.json").read_text())
        frames = {f["name"]: bytes.fromhex(f["hex"]) for f in manifest["frames"]}
        self.assertEqual(p.crc16_ccitt_false(b"123456789"), 0x29B1)
        for f in manifest["frames"]:
            raw = frames[f["name"]]
            with self.subTest(name=f["name"]):
                if f.get("stream"):
                    expected = [frames[name] for name in f["expected_frames"]]
                    for split in range(len(raw) + 1):
                        parser = StreamParser()
                        got = parser.feed(raw[:split], 0) + parser.feed(raw[split:], 0.01)
                        got += parser.feed(b"", 0.2)
                        self.assertEqual(got, expected, (f["name"], split))
                elif f["valid"]:
                    decoded = decode_frame(raw)
                    self.assertEqual(encode_frame(decoded.msg_type, decoded.sequence,
                                                  decoded.session_id, decoded.payload), raw)
                    parser = StreamParser()
                    got = []
                    for byte in raw:
                        got += parser.feed(bytes([byte]), 0)
                    self.assertEqual(got, [raw])
                else:
                    with self.assertRaises(p.FrameError):
                        decode_frame(raw)
                    self.assertEqual(StreamParser().feed(raw, 0), [])

    def test_timeout_recovers_embedded_valid_frame(self):
        valid = encode_frame(p.MsgType.GET_STATUS, 0, 0)
        partial = encode_frame(p.MsgType.STATUS, 0, 0, p.Status().pack())[:12]
        parser = StreamParser()
        self.assertEqual(parser.feed(partial + valid, 0), [])
        self.assertEqual(parser.feed(b"", 0.101), [valid])
        self.assertEqual(parser.errors["timeout"], 1)

    def test_long_noise_keeps_bounded_buffer(self):
        parser = StreamParser()
        self.assertEqual(parser.feed(b"x" * 100000 + b"\xa5", 0), [])
        self.assertEqual(len(parser.buffer), 1)


class FakeSerial:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.is_open = True
        self.rx = bytearray()
        self.writes = []
        self.short = False
        self.broken = False

    def reset_input_buffer(self):
        self.rx.clear()

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, size):
        if self.broken:
            raise OSError("device removed")
        raw = bytes(self.rx[:size])
        del self.rx[:size]
        return raw

    def write(self, raw):
        self.writes.append(raw)
        return len(raw) - int(self.short)

    def close(self):
        self.is_open = False


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.transport = SerialTransport("TEST", serial_factory=FakeSerial)
        self.transport.open()
        self.device = self.transport._serial
        self.raw = encode_frame(p.MsgType.GET_STATUS, 0, 0)

    def test_factory_is_closed_and_honestly_labelled(self):
        transport = create_transport("COM99", 115200)
        self.assertFalse(transport.is_open())
        self.assertEqual(transport.controller_source, "fpga")

    def test_serial_settings_and_exact_bytes(self):
        self.assertEqual(self.device.options["baudrate"], 115200)
        self.assertFalse(self.device.options["xonxoff"])
        self.transport.send(self.raw)
        self.assertEqual(self.device.writes, [self.raw])

    def test_corrupt_frames_then_valid_and_concatenation(self):
        corrupt = self.raw[:-1] + bytes([self.raw[-1] ^ 1])
        self.device.rx.extend(corrupt + self.raw + self.raw)
        self.assertEqual(self.transport.receive(0), self.raw)
        self.assertEqual(self.transport.receive(0), self.raw)
        self.assertIsNone(self.transport.receive(0))
        self.assertGreater(self.transport.stats()["rx_errors"], 0)

    def test_partial_write_closes_and_is_not_retried(self):
        self.device.short = True
        with self.assertRaises(TransportError):
            self.transport.send(self.raw)
        self.assertFalse(self.transport.is_open())
        self.assertEqual(len(self.device.writes), 1)

    def test_device_failure_and_reopen_clear_partial_input(self):
        self.device.rx.extend(self.raw[:8])
        self.assertIsNone(self.transport.receive(0))
        self.device.broken = True
        with self.assertRaises(TransportError):
            self.transport.receive(0)
        self.transport.open()
        self.transport._serial.rx.extend(self.raw)
        self.assertEqual(self.transport.receive(0), self.raw)

    def test_closed_operations_and_idempotent_close(self):
        self.transport.close()
        self.transport.close()
        with self.assertRaises(TransportError):
            self.transport.send(self.raw)
        with self.assertRaises(TransportError):
            self.transport.receive(0)


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class FakeTransport:
    controller_source = "simulator"

    def __init__(self, clock):
        self.clock = clock
        self.opened = False
        self.incoming = deque()
        self.sent = []

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False
        self.incoming.clear()

    def is_open(self):
        return self.opened

    def send(self, raw):
        self.sent.append((self.clock(), raw))

    def receive(self, timeout):
        if self.incoming:
            return self.incoming.popleft()
        self.clock.now += timeout
        return None

    def stats(self):
        return {}


class DelayTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.inner = FakeTransport(self.clock)
        self.transport = DelayTransport(self.inner, 1, clock=self.clock)
        self.transport.open()
        self.start = encode_frame(p.MsgType.START, 1, 123, p.pack_u32(5))

    def test_fifo_when_delay_decreases(self):
        self.transport.send(self.start)
        self.transport.delay_s = 0.1
        self.transport.send(encode_frame(p.MsgType.ABORT, 2, 123, p.pack_u32(5)))
        self.transport.receive(1.1)
        self.assertEqual(len(self.inner.sent), 2)
        self.assertEqual(self.inner.sent[0][1], self.start)
        self.assertTrue(all(t >= 1 for t, _ in self.inner.sent))

    def test_ack_and_status_both_delayed(self):
        ack = encode_frame(p.MsgType.ACK, 1, 123, p.Ack(p.MsgType.START, 0, 0, 5, 0, 0).pack())
        status = encode_frame(p.MsgType.STATUS, 1, 123, p.Status().pack())
        self.inner.incoming.extend([ack, status])
        self.assertIsNone(self.transport.receive(0.9))
        self.assertEqual(self.transport.receive(0.2), ack)
        self.assertEqual(self.transport.receive(0), status)

    def test_reconnect_never_sends_queued_start(self):
        self.transport.send(self.start)
        self.transport.close()
        self.transport.open()
        self.transport.receive(2)
        self.assertEqual(self.inner.sent, [])

    def test_command_overflow_fails_closed(self):
        for _ in range(128):
            self.transport.send(self.start)
        with self.assertRaises(TransportError):
            self.transport.send(self.start)
        self.assertFalse(self.transport.is_open())
        self.assertEqual(self.transport.stats()["delay_tx_queued"], 0)

    def test_telemetry_coalescing_gets_new_release_time(self):
        for seq in range(128):
            self.inner.incoming.append(encode_frame(p.MsgType.STATUS, seq, 123, p.Status(tick=seq).pack()))
            self.transport.receive(0)
        self.clock.now = 0.5
        newest = encode_frame(p.MsgType.STATUS, 128, 123, p.Status(tick=128).pack())
        self.inner.incoming.append(newest)
        self.transport.receive(0)
        self.assertEqual(len(self.transport._rx), 128)
        self.assertEqual(self.transport._rx[-1], (1.5, newest))
        self.assertEqual(self.transport.stats()["telemetry_coalesced"], 1)

    def test_ack_overflow_fails_explicitly(self):
        ack = encode_frame(p.MsgType.ACK, 1, 123, p.Ack(p.MsgType.START, 0, 0, 5, 0, 0).pack())
        for _ in range(128):
            self.inner.incoming.append(ack)
            self.transport.receive(0)
        self.inner.incoming.append(ack)
        with self.assertRaises(TransportError):
            self.transport.receive(0)
        self.assertFalse(self.transport.is_open())

    def test_source_and_retry_budget_and_invalid_delay(self):
        self.assertEqual(self.transport.controller_source, "simulator")
        self.assertEqual(self.transport.retry_timeout_s, 6.5)
        self.transport.delay_s = float("nan")
        with self.assertRaises(TransportError):
            self.transport.send(self.start)


class RuntimeBoundaryTests(unittest.TestCase):
    def run_mission(self, transport):
        from app.backend.runtime.link import Link
        transport.open()
        link = Link(transport, lambda *_: None,
                    retry_timeout_s=getattr(transport, "retry_timeout_s", 0.02))
        self.assertEqual(link.open_session().result, p.Result.APPLIED)
        plan = p.Plan(5, 10, 12010, 12610, 30, 10, 20)
        for kind, payload in [(p.MsgType.LOAD_PLAN, plan.pack()),
                              (p.MsgType.COMMIT_PLAN, p.pack_commit(5, plan.crc16())),
                              (p.MsgType.ARM, p.pack_u32(5)),
                              (p.MsgType.START, p.pack_u32(5))]:
            self.assertEqual(link.mutate(kind, payload).result, p.Result.APPLIED)
        return link

    def test_real_runtime_link_over_delayed_simulator(self):
        from app.backend.runtime.sim_controller import SimulatorTransport
        inner = SimulatorTransport()
        transport = DelayTransport(inner, 0.01, max_delay_s=0.01)
        try:
            link = self.run_mission(transport)
            session, status = link.read_status()
            self.assertEqual(session, link.session_id)
            self.assertEqual(status.mission_id, 5)
            self.assertEqual(status.state, p.State.RUNNING)
        finally:
            transport.close()

    def test_lost_start_ack_retries_identical_bytes_and_applies_once(self):
        from app.backend.runtime.sim_controller import SimulatorTransport

        class DropFirstStartAck(SimulatorTransport):
            dropped = False

            def __init__(self):
                super().__init__()
                self.starts = []

            def send(self, raw):
                if decode_frame(raw).msg_type == p.MsgType.START:
                    self.starts.append(raw)
                super().send(raw)

            def receive(self, timeout_s):
                raw = super().receive(timeout_s)
                if raw is not None:
                    frame = decode_frame(raw)
                    if (frame.msg_type == p.MsgType.ACK and not self.dropped
                            and p.Ack.unpack(frame.payload).original_type == p.MsgType.START):
                        self.dropped = True
                        return None
                return raw

        transport = DropFirstStartAck()
        try:
            link = self.run_mission(transport)
            self.assertEqual(len(transport.starts), 2)
            self.assertEqual(transport.starts[0], transport.starts[1])
            self.assertEqual(link.next_seq, 5)
            self.assertEqual(transport.controller.state, p.State.RUNNING)
        finally:
            transport.close()


if __name__ == "__main__":
    unittest.main()
