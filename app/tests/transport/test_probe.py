import unittest
from unittest.mock import patch
from app.backend.transport import SerialTransport
from app.backend.transport.codec import StreamParser
from app.contracts import protocol_v1 as p
from app.contracts.transport import TransportError
from app.hardware.xiao.probe import handshake, wait_for, ProbeError
from app.backend.runtime.sim_controller import SimulatorTransport


class ProbeTests(unittest.TestCase):
    def test_missing_and_busy_messages(self):
        for message, expected in [('No such file', 'PORT_MISSING'),
                                  ('Access is denied', 'PORT_BUSY')]:
            with self.subTest(message=message):
                def fail(**kwargs):
                    raise OSError(message)
                with self.assertRaisesRegex(TransportError, expected):
                    SerialTransport('TEST', serial_factory=fail).open()

    def test_parser_distinguishes_version_and_crc(self):
        raw = p.encode_frame(p.MsgType.GET_STATUS, 0, 0)
        parser = StreamParser()
        parser.feed(raw[:2]+b'\x02'+raw[3:], 0)
        parser.feed(raw[:-1]+bytes([raw[-1] ^ 1]), 0)
        self.assertEqual(parser.errors['version'], 1)
        self.assertEqual(parser.errors['crc'], 1)

    def test_session_open_then_existing_session_is_preserved(self):
        transport = SimulatorTransport()
        transport.open()
        try:
            first = handshake(transport, log=lambda *a, **k: None)
            self.assertNotEqual(first, 0)
            self.assertEqual(handshake(transport, log=lambda *a, **k: None), first)
        finally:
            transport.close()

    def test_active_mission_not_taken_over(self):
        transport = SimulatorTransport()
        transport.open()
        transport.controller.state = p.State.RUNNING
        transport.controller.session = 42
        try:
            self.assertEqual(handshake(transport, log=lambda *a, **k: None), 42)
            self.assertEqual(transport.controller.state, p.State.RUNNING)
        finally:
            transport.close()

    def test_timeout_exit_reasons(self):
        class Empty:
            def __init__(self, errors):
                self.errors = errors
            def stats(self):
                return {'parser_errors': self.errors}
        for errors, code in [({}, 4), ({'crc': 1}, 5), ({'version': 1}, 6)]:
            with self.assertRaises(ProbeError) as raised:
                wait_for(Empty(errors), lambda f: True, 0, lambda *a, **k: None)
            self.assertEqual(raised.exception.code, code)


if __name__ == '__main__':
    unittest.main()
