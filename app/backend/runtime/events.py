"""Event hub: one increasing server sequence, fan-out to WebSocket clients.

Worker threads publish; each WebSocket connection owns a bounded asyncio queue. The latest
event of each type is kept so a client that (re)connects first receives the full current
state before any incremental event.
"""
from __future__ import annotations

import asyncio
import threading


class EventHub:
    QUEUE_SIZE = 256

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._latest: dict[str, dict] = {}
        self._subscribers: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}

    def next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def publish(self, event_type: str, data: dict, seq: int | None = None) -> dict:
        """Send an event to every subscriber. Safe to call from any thread."""
        event = {"type": event_type, "server_seq": seq if seq is not None else self.next_seq(), "data": data}
        with self._lock:
            self._latest[event_type] = event
            subscribers = list(self._subscribers.items())
        for queue, loop in subscribers:
            try:
                loop.call_soon_threadsafe(self._offer, queue, event)
            except RuntimeError:        # that client's loop is gone
                self.unsubscribe(queue)
        return event

    @staticmethod
    def _offer(queue: asyncio.Queue, event: dict) -> None:
        if queue.full():                # slow client: drop its oldest event; snapshots are full state
            queue.get_nowait()
        queue.put_nowait(event)

    def subscribe(self) -> tuple[asyncio.Queue, list[dict]]:
        """Register the calling event loop. Returns (queue, current state to send first)."""
        queue: asyncio.Queue = asyncio.Queue(self.QUEUE_SIZE)
        with self._lock:
            self._subscribers[queue] = asyncio.get_running_loop()
            current = sorted(self._latest.values(), key=lambda e: e["server_seq"])
        return queue, current

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)
