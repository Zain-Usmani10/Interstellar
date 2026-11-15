"""Opt-in recovery of a previously opened serial port; never stores/replays frames."""
from __future__ import annotations

import math
import time

from app.contracts.transport import TransportError
from .serial_transport import SerialTransport


class ReconnectingSerialTransport:
    controller_source = "fpga"

    def __init__(self, inner: SerialTransport, *, clock=time.monotonic, sleep=time.sleep):
        self.inner = inner
        self._clock, self._sleep = clock, sleep
        self._active = False
        self._down = False
        self._next_attempt = 0.0
        self._reconnects = 0
        self._last_error = None

    def open(self):
        if self._active:
            if not self._ensure_open():
                raise self._unavailable()
            return
        try:
            self.inner.open()
        except TransportError as exc:
            self._last_error = str(exc)
            raise
        self._active = True
        self._down = False

    def close(self):
        # Explicit shutdown cancels recovery until the caller opens us again.
        self._active = False
        self._down = False
        self.inner.close()

    def is_open(self):
        # Observation only: health checks must not acquire a serial port.
        return self.inner.is_open()

    def _failed(self, exc):
        self._last_error = str(exc)
        self.inner.close()
        self._down = True
        self._next_attempt = self._clock() + 1.0

    def _ensure_open(self):
        if not self._active:
            return False
        if self.inner.is_open():
            return True
        if not self._down:
            self._failed(TransportError(f"serial port {self.inner.port} closed unexpectedly"))
        if self._clock() < self._next_attempt:
            return False
        try:
            self.inner.open()
        except TransportError as exc:
            self._failed(exc)
            return False
        self._down = False
        self._reconnects += 1
        return True

    def _unavailable(self):
        if not self._active:
            return TransportError("serial port is closed")
        return TransportError(
            f"SERIAL_RECONNECT_PENDING: {self.inner.port}; retrying the same port "
            f"at most once per second. Check cable and configured COM number. "
            f"Last error: {self._last_error}")

    def send(self, frame: bytes):
        if not self._ensure_open():
            raise self._unavailable()
        try:
            self.inner.send(frame)
        except TransportError as exc:
            self._failed(exc)
            # A partial write may have applied. Never repeat it here.
            raise

    def receive(self, timeout_s: float):
        if not math.isfinite(timeout_s) or timeout_s < 0:
            raise ValueError("timeout must be finite and nonnegative")
        if not self._ensure_open():
            # Avoid spinning the runtime worker while the port is absent.
            if self._active:
                self._sleep(min(timeout_s, max(0, self._next_attempt - self._clock())))
            return None
        try:
            return self.inner.receive(timeout_s)
        except TransportError as exc:
            self._failed(exc)
            return None

    def stats(self):
        return {**self.inner.stats(), "reconnects": self._reconnects,
                "last_error": self._last_error}
