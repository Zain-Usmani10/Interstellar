"""The sole artificial-delay layer; pumped by the runtime's single transport worker."""
from __future__ import annotations

import math
import time
from collections import deque

from app.contracts.protocol_v1 import MsgType
from app.contracts.transport import TransportError
from .codec import decode_frame


class DelayTransport:
    def __init__(self, inner, delay_s=0.1, *, max_delay_s=3.0, clock=time.monotonic):
        if not math.isfinite(max_delay_s) or max_delay_s < 0:
            raise ValueError("max_delay_s must be finite and nonnegative")
        self.inner, self.delay_s, self.max_delay_s = inner, delay_s, max_delay_s
        self.controller_source = inner.controller_source
        self.retry_timeout_s = 0.5 + 2 * max_delay_s
        self._clock = clock
        self._tx, self._rx = deque(), deque()
        self._coalesced = 0

    def open(self):
        if not self.is_open():
            self._tx.clear()
            self._rx.clear()
            self.inner.open()

    def close(self):
        self._tx.clear()
        self._rx.clear()
        self.inner.close()

    def is_open(self):
        return self.inner.is_open()

    def _enqueue(self, queue, raw):
        frame = decode_frame(raw)
        delay = self.delay_s() if callable(self.delay_s) else self.delay_s
        if not math.isfinite(delay) or not 0 <= delay <= self.max_delay_s:
            raise TransportError("delay is outside the configured bound")
        if len(queue) >= 128:
            if frame.msg_type == MsgType.STATUS:
                for i, (_, old) in enumerate(queue):
                    if decode_frame(old).msg_type == MsgType.STATUS:
                        del queue[i]
                        self._coalesced += 1
                        break
                else:
                    raise TransportError("delay queue full; no telemetry can be coalesced")
            else:
                raise TransportError("delay queue full; command/ACK cannot be dropped")
        release = max(self._clock() + delay, queue[-1][0] if queue else 0)
        queue.append((release, raw))

    def send(self, frame):
        if not self.is_open():
            raise TransportError("transport closed")
        try:
            self._enqueue(self._tx, frame)
        except TransportError:
            self.close()
            raise

    def receive(self, timeout_s):
        if not self.is_open():
            raise TransportError("transport closed")
        if not math.isfinite(timeout_s) or timeout_s < 0:
            raise ValueError("timeout must be finite and nonnegative")
        deadline = self._clock() + timeout_s
        try:
            while True:
                now = self._clock()
                while self._tx and self._tx[0][0] <= now:
                    self.inner.send(self._tx.popleft()[1])
                if self._rx and self._rx[0][0] <= now:
                    return self._rx.popleft()[1]
                wake = min(deadline, now + 0.05,
                           self._tx[0][0] if self._tx else deadline,
                           self._rx[0][0] if self._rx else deadline)
                raw = self.inner.receive(max(0, wake - now))
                if raw is not None:
                    self._enqueue(self._rx, raw)
                if self._clock() >= deadline:
                    if self._rx and self._rx[0][0] <= self._clock():
                        return self._rx.popleft()[1]
                    return None
        except TransportError:
            self.close()
            raise

    def stats(self):
        return {**self.inner.stats(), "delay_tx_queued": len(self._tx),
                "delay_rx_queued": len(self._rx), "telemetry_coalesced": self._coalesced,
                "max_demo_one_way_delay_s": self.max_delay_s}
