"""Recovery tests use fake serial devices only, never a physical COM port."""
import os
import unittest
from unittest.mock import patch

from app.backend.transport import ReconnectingSerialTransport, SerialTransport, create_transport
from app.contracts import protocol_v1 as p
from app.contracts.transport import Transport, TransportError
from test_transport import Clock, FakeSerial


class ReconnectTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.devices = []
        self.attempts = []
        self.absent = False

        def factory(**kwargs):
            self.attempts.append((self.clock(), kwargs["port"]))
            if self.absent:
                raise OSError("port not found")
            device = FakeSerial(**kwargs)
            self.devices.append(device)
            return device

        def sleep(seconds):
            self.clock.now += seconds

        self.transport = ReconnectingSerialTransport(
            SerialTransport("TEST", serial_factory=factory), clock=self.clock, sleep=sleep)
        self.transport.open()
        self.frame = p.encode_frame(p.MsgType.START, 1, 123, p.pack_u32(5))

    def drop(self):
        self.devices[-1].broken = True
        self.assertIsNone(self.transport.receive(0))
        self.assertFalse(self.transport.is_open())

    def test_factory_is_opt_in_and_closed(self):
        for value in (None, "", "false", "1", "yes", "true", " TRUE "):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ["SERIAL_AUTO_RECONNECT"] = value
                transport = create_transport("COM99", 57600)
                expected = ReconnectingSerialTransport if value in ("true", " TRUE ") else SerialTransport
                self.assertIs(type(transport), expected)
                self.assertFalse(transport.is_open())
                self.assertIsInstance(transport, Transport)

    def test_read_drop_and_same_port_recovery(self):
        self.drop()
        self.clock.now = 1
        self.assertIsNone(self.transport.receive(0))
        self.assertTrue(self.transport.is_open())
        self.devices[-1].rx.extend(self.frame)
        self.assertEqual(self.transport.receive(0), self.frame)
        self.assertEqual(self.attempts, [(0, "TEST"), (1, "TEST")])
        self.assertEqual(self.transport.stats()["reconnects"], 1)
        self.assertIn("read failure", self.transport.stats()["last_error"])

    def test_failed_partial_write_is_never_replayed(self):
        self.devices[0].short = True
        with self.assertRaisesRegex(TransportError, "controller state unknown"):
            self.transport.send(self.frame)
        self.assertEqual(self.devices[0].writes, [self.frame])
        self.clock.now = 1
        self.transport.receive(0)
        self.assertEqual(self.devices[1].writes, [])
        new_frame = p.encode_frame(p.MsgType.GET_STATUS, 0, 123)
        self.transport.send(new_frame)
        self.assertEqual(self.devices[1].writes, [new_frame])

    def test_write_exception_is_reported_without_replay(self):
        with patch.object(self.devices[0], "write", side_effect=OSError("device removed")) as write:
            with self.assertRaisesRegex(TransportError, "write failure"):
                self.transport.send(self.frame)
            write.assert_called_once_with(self.frame)
        self.clock.now = 1
        self.transport.receive(0)
        self.assertEqual(self.devices[1].writes, [])

    def test_absent_for_several_attempts_then_returns(self):
        self.drop()
        self.absent = True
        for now in (1, 2, 3):
            self.clock.now = now
            self.assertIsNone(self.transport.receive(0))
            with self.assertRaisesRegex(TransportError, "TEST.*Last error: PORT_MISSING"):
                self.transport.send(self.frame)
        self.absent = False
        self.clock.now = 4
        self.transport.receive(0)
        self.assertTrue(self.transport.is_open())
        self.assertEqual(self.attempts, [(n, "TEST") for n in range(5)])
        self.assertEqual(self.devices[-1].writes, [])
        self.assertEqual(self.transport.stats()["reconnects"], 1)

    def test_all_call_types_share_rate_limit_and_health_never_opens(self):
        self.drop()
        self.absent = True
        for now in (0, 0.5, 0.999, 1, 1.5, 1.999, 2):
            self.clock.now = now
            self.transport.receive(0)
            with self.assertRaises(TransportError):
                self.transport.send(self.frame)
            with self.assertRaises(TransportError):
                self.transport.open()
            self.assertFalse(self.transport.is_open())
            self.transport.stats()
        self.assertEqual(self.attempts, [(0, "TEST"), (1, "TEST"), (2, "TEST")])
        self.clock.now = 20
        self.transport.is_open()
        self.assertEqual(len(self.attempts), 3)

    def test_send_can_reopen_but_only_sends_current_call(self):
        self.drop()
        with self.assertRaises(TransportError):
            self.transport.send(self.frame)
        self.clock.now = 1
        query = p.encode_frame(p.MsgType.GET_STATUS, 0, 123)
        self.transport.send(query)
        self.assertEqual(self.devices[-1].writes, [query])

    def test_shutdown_cancels_recovery_until_explicit_open(self):
        self.drop()
        self.transport.close()
        self.transport.close()
        self.clock.now = 10
        self.assertIsNone(self.transport.receive(0))
        with self.assertRaisesRegex(TransportError, "closed"):
            self.transport.send(self.frame)
        self.assertEqual(len(self.attempts), 1)
        self.transport.open()
        self.assertTrue(self.transport.is_open())

    def test_initial_missing_port_raises_and_does_not_enable_recovery(self):
        self.transport.close()
        self.absent = True
        with self.assertRaisesRegex(TransportError, "PORT_MISSING"):
            self.transport.open()
        self.absent = False
        self.clock.now = 10
        self.transport.receive(0)
        self.assertFalse(self.transport.is_open())
        self.assertEqual(len(self.attempts), 2)

    def test_partial_old_input_is_discarded(self):
        self.devices[0].rx.extend(self.frame[:8])
        self.transport.receive(0)
        self.drop()
        self.clock.now = 1
        self.transport.receive(0)
        self.devices[1].rx.extend(self.frame[8:])
        self.assertIsNone(self.transport.receive(0))
        self.devices[1].rx.extend(self.frame)
        self.assertEqual(self.transport.receive(0), self.frame)

    def test_closed_device_detected_without_io_exception(self):
        self.devices[0].close()
        self.assertFalse(self.transport.is_open())
        self.transport.receive(0)
        self.clock.now = 1
        self.transport.receive(0)
        self.assertTrue(self.transport.is_open())

    def test_down_receive_wait_is_bounded_and_invalid_timeouts_rejected(self):
        self.drop()
        self.transport.receive(0.05)
        self.assertEqual(self.clock.now, 0.05)
        self.transport.receive(100)
        self.assertEqual(self.clock.now, 1)
        for invalid in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.transport.receive(invalid)


if __name__ == "__main__":
    unittest.main()
