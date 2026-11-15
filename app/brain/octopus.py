"""Octopus 16 acquisition qualification; no core API calls or selection dispatch."""
from __future__ import annotations

import argparse
import asyncio
import json
import queue
import threading
import time

import numpy as np

from .acquisition import DeviceInfo, SampleBatch

SERVICE = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
NOTIFY = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
UV_PER_COUNT = 1.2 / 4 / 8388607 * 1_000_000


def decode_notification(data: bytes) -> list[tuple[int, np.ndarray]]:
    """Strict whole notifications: reject tails/corruption, never silently resync."""
    if not data or len(data) % 51:
        raise ValueError("notification must contain complete 51-byte packets")
    decoded = []
    for offset in range(0, len(data), 51):
        packet = data[offset:offset + 51]
        if packet[0] != 0xA0 or packet[-1] != 0xC0:
            raise ValueError("invalid Octopus packet markers")
        values = [int.from_bytes(packet[2 + ch*3:5 + ch*3], "big", signed=True)
                  for ch in range(16)]
        if any(value in (-8388608, 8388607) for value in values):
            raise ValueError("ADC rail saturation")
        decoded.append((packet[1], np.asarray(values, dtype=np.float64) * UV_PER_COUNT))
    return decoded


class OctopusStream:
    """Normalize selected channels and fail closed on loss, duplicates or restart.

    Packet counters cannot detect loss of exactly 256 samples; receive-time stall
    checking is also required. Reconnect creates a new stream/calibration boundary.
    """

    def __init__(self, channels=(0, 1), rate_hz=250.0, clock=time.monotonic):
        if (not channels or len(set(channels)) != len(channels)
                or any(type(ch) is not int or not 0 <= ch < 16 for ch in channels)):
            raise ValueError("select unique zero-based EEG channels 0..15")
        if not np.isfinite(rate_hz) or not 200 <= rate_hz <= 300:
            raise ValueError("configured measured rate must be 200..300 Hz")
        self.channels, self.rate, self.clock = tuple(channels), rate_hz, clock
        self.counter = None
        self.last_time = None
        self.index = self.batch_id = 0
        self.failed = False

    def ingest(self, data: bytes) -> SampleBatch:
        if self.failed:
            raise RuntimeError("stream invalidated; reconnect and recalibrate")
        now = self.clock()
        try:
            if self.last_time is not None and now - self.last_time > 0.5:
                raise ValueError("stale acquisition")
            packets = decode_notification(data)
            previous = self.counter
            for counter, _ in packets:
                if previous is not None and counter != (previous + 1) % 256:
                    raise ValueError("packet loss, duplicate or device restart")
                previous = counter
        except ValueError:
            self.failed = True
            raise
        values = np.stack([values for _, values in packets], axis=1)[list(self.channels)]
        indices = np.arange(self.index, self.index + len(packets))
        self.index += len(packets)
        self.batch_id += 1
        self.counter, self.last_time = previous, now
        return SampleBatch(self.batch_id, values, indices, self.rate, now, "live_eeg")


class OctopusAdapter:
    """Blocking Acquisition boundary; BLE runs on its own event-loop thread.

    Call read_batch off the UI/heartbeat event loop. No automatic reconnect,
    resampling, recording, or synthetic fallback. A failure invalidates the
    entire run, including any queued samples.
    """

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.thread = None
        self.running = False

    def start(self, config: dict) -> DeviceInfo:
        if self.thread is not None:
            raise RuntimeError("stop the previous acquisition before starting")
        address = config.get("address")
        if not isinstance(address, str) or not address.strip():
            raise ValueError("exact verified BLE address/identifier required")
        self.stream = OctopusStream(config.get("channels", (0, 1)),
                                    config.get("sample_rate_hz", 250.0), self.clock)
        self.rate = self.stream.rate
        self.size = round(self.rate / 10)
        self.queue = queue.Queue(maxsize=128)
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.failure = None
        self.loop = self.task = None
        self.batch_id = 0
        self.running = True
        self.thread = threading.Thread(target=self._worker, args=(address,), daemon=True)
        self.thread.start()
        if not self.ready.wait(15) or self.failure:
            reason = self.failure or "device connection timed out"
            self.stop()
            raise RuntimeError(reason)
        return DeviceInfo(name="octopus-16", version="1", device="Octopus 16 BLE",
                          source="live_eeg", nominal_rate_hz=250,
                          effective_rate_hz=self.rate,
                          channels=tuple(f"CH{ch+1}" for ch in self.stream.channels),
                          units="uV", clock="unwrapped 8-bit sample counter; host monotonic receive")

    def _receive(self, _sender, payload):
        if self.failure or self.stopping.is_set():
            return
        try:
            self.queue.put_nowait(self.stream.ingest(bytes(payload)))
        except (ValueError, RuntimeError, queue.Full):
            self.failure = "invalid, discontinuous or overflowing acquisition"

    def _disconnected(self, _client):
        if not self.stopping.is_set():
            self.failure = "device disconnected"

    async def _connect(self, address):
        # Lazy optional import keeps the synthetic environment independent.
        from bleak import BleakClient, BleakScanner

        self.loop = asyncio.get_running_loop()
        self.task = asyncio.current_task()
        device = await BleakScanner.find_device_by_address(address, timeout=10)
        if device is None:
            raise RuntimeError("specified device unavailable")
        async with BleakClient(device, disconnected_callback=self._disconnected) as client:
            if client.services.get_service(SERVICE) is None:
                raise RuntimeError("expected Octopus service missing")
            await client.start_notify(NOTIFY, self._receive)
            started = self.clock()
            self.ready.set()
            try:
                while not self.stopping.is_set() and not self.failure:
                    last = self.stream.last_time
                    if self.clock() - (started if last is None else last) > 0.5:
                        self.failure = "no fresh samples"
                        break
                    await asyncio.sleep(0.02)
            finally:
                if client.is_connected:
                    await client.stop_notify(NOTIFY)

    def _worker(self, address):
        try:
            asyncio.run(self._connect(address))
        except asyncio.CancelledError:
            pass
        except Exception as error:
            # Exception messages from third-party drivers may include device IDs.
            self.failure = f"BLE acquisition failed ({type(error).__name__})"
        finally:
            self.ready.set()

    def read_batch(self) -> SampleBatch:
        if not self.running:
            raise RuntimeError("acquisition stopped")
        batches, count = [], 0
        deadline = self.clock() + 0.5
        while count < self.size:
            if self.failure:
                raise RuntimeError(self.failure)
            remaining = deadline - self.clock()
            if remaining <= 0:
                self.failure = "sample batch timed out"
                raise RuntimeError(self.failure)
            try:
                batch = self.queue.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if not 0 <= self.clock() - batch.received_at <= 0.5:
                self.failure = "queued samples are stale"
                raise RuntimeError(self.failure)
            batches.append(batch)
            count += batch.samples_uv.shape[1]
        if self.failure:
            raise RuntimeError(self.failure)
        self.batch_id += 1
        return SampleBatch(self.batch_id,
                           np.concatenate([batch.samples_uv for batch in batches], axis=1),
                           np.concatenate([batch.sample_indices for batch in batches]),
                           self.rate, batches[-1].received_at, "live_eeg")

    def stop(self):
        self.running = False
        if self.thread is None:
            return
        self.stopping.set()
        if self.loop is not None and self.task is not None and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass  # loop closed between check and scheduling
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("BLE worker has not stopped; restart the process")
        self.thread = None


def qualify(address: str, seconds: float, rate: float) -> None:
    adapter = OctopusAdapter()
    count, first, last, first_count = 0, None, None, 0
    try:
        adapter.start({"address": address, "channels": tuple(range(16)), "sample_rate_hz": rate})
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            batch = adapter.read_batch()
            count += len(batch.sample_indices)
            if first is None:
                first, first_count = batch.received_at, count
            last = batch.received_at
    finally:
        adapter.stop()
    span = 0 if first is None or last is None else last - first
    print(json.dumps({"source": "live_eeg", "samples": count,
                      "receive_span_seconds": span,
                      "observed_delivery_rate_hz": None if span <= 0 else (count-first_count)/span,
                      "configured_rate_hz": rate,
                      "note": "BLE arrival estimate, not ADC clock certification or EEG accuracy"}))


async def scan():
    """List candidates only; never connect to an automatically chosen device."""
    from bleak import BleakScanner
    devices = await BleakScanner.discover(timeout=8, return_adv=True)
    candidates = []
    for device, advertisement in devices.values():
        name = advertisement.local_name or device.name or ''
        if SERVICE in [uuid.lower() for uuid in (advertisement.service_uuids or [])] or name.lower().startswith('octopus'):
            candidates.append({'name': name, 'address': device.address})
    print(json.dumps({'octopus_candidates': candidates, 'note': 'Verify the label before using --address.'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--address", help="exact verified BLE address/identifier")
    mode.add_argument("--scan", action="store_true", help="list Octopus BLE candidates without connecting")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--rate", type=float, default=250)
    args = parser.parse_args()
    if args.scan:
        asyncio.run(scan())
        return
    if not 2 <= args.seconds <= 300:
        parser.error("seconds must be 2..300")
    OctopusStream(rate_hz=args.rate)  # validate before connecting
    qualify(args.address, args.seconds, args.rate)


if __name__ == "__main__":
    main()
