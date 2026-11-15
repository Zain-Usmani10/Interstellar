"""Single-owner USB serial transport. Command acknowledgments belong to runtime.Link."""
from __future__ import annotations

import math
import time
from collections import deque

from app.contracts.transport import TransportError
from .codec import StreamParser, decode_frame


class SerialTransport:
    controller_source = "fpga"

    def __init__(self, port: str, baud: int = 115200, *, serial_factory=None):
        self.port, self.baud = port, baud
        self._factory = serial_factory
        self._serial = None
        self._parser = StreamParser()
        self._ready = deque()
        self._sent = self._received = 0

    def open(self):
        if self.is_open():
            return
        self._ready.clear()
        self._parser = StreamParser()
        try:
            factory = self._factory
            if factory is None:
                import serial
                factory = serial.Serial
            self._serial = factory(port=self.port, baudrate=self.baud, bytesize=8,
                                   parity="N", stopbits=1, timeout=0, write_timeout=0.5,
                                   xonxoff=False, rtscts=False, dsrdtr=False)
            self._serial.reset_input_buffer()
        except Exception as exc:
            self.close()
            message = str(exc).lower()
            missing = any(word in message for word in ('cannot find', 'not found', 'no such file'))
            busy = any(word in message for word in ('access is denied', 'permission', 'busy'))
            code = 'PORT_MISSING' if missing else 'PORT_BUSY' if busy else 'PORT_OPEN_FAILED'
            hint = 'Check cable and COM number.' if missing else 'Close Serial Monitor and other serial owners; check permissions.' if busy else 'Check device and driver.'
            raise TransportError(f"{code}: {self.port}. {hint} ({exc})") from exc

    def close(self):
        device, self._serial = self._serial, None
        self._ready.clear()
        self._parser = StreamParser()
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

    def is_open(self):
        return self._serial is not None and self._serial.is_open

    def _require_open(self):
        if not self.is_open():
            raise TransportError("serial port is closed")

    def send(self, frame: bytes):
        self._require_open()
        decode_frame(frame)
        try:
            # Partial writes are ambiguous: close and reconcile, never silently replay here.
            if self._serial.write(frame) != len(frame):
                raise OSError("partial serial write; controller state unknown")
            self._sent += 1
        except Exception as exc:
            self.close()
            raise TransportError(f"SERIAL_IO_FAILED: {self.port} closed after write failure; controller state unknown. Reconnect and reconcile STATUS. ({exc})") from exc

    def receive(self, timeout_s: float):
        self._require_open()
        if not math.isfinite(timeout_s) or timeout_s < 0:
            raise ValueError("timeout must be finite and nonnegative")
        deadline = time.monotonic() + timeout_s
        try:
            while True:
                if self._ready:
                    self._received += 1
                    return self._ready.popleft()
                remaining = max(0, deadline - time.monotonic())
                self._serial.timeout = min(0.05, remaining)
                # A bounded read produces fewer than 128 minimum-size frames.
                chunk = self._serial.read(min(1024, max(1, self._serial.in_waiting)))
                self._ready.extend(self._parser.feed(chunk, time.monotonic()))
                if not self._ready and time.monotonic() >= deadline:
                    return None
        except Exception as exc:
            self.close()
            raise TransportError(f"SERIAL_IO_FAILED: {self.port} closed after read failure. Reconnect and reconcile STATUS. ({exc})") from exc

    def stats(self):
        return {"frames_sent": self._sent, "frames_received": self._received,
                "rx_errors": sum(self._parser.errors.values()),
                "parser_errors": dict(self._parser.errors), "queued_rx": len(self._ready)}
