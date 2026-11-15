"""Normalized microvolt samples; synthetic labels stay outside decoder inputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import time
import numpy as np


@dataclass(frozen=True)
class DeviceInfo:
    name: str = "synthetic-ssvep"
    version: str = "1"
    device: str = "deterministic two-channel generator"
    source: str = "synthetic"
    nominal_rate_hz: float = 250.0
    effective_rate_hz: float = 250.0
    channels: tuple[str, ...] = ("synthetic-O1", "synthetic-O2")
    units: str = "uV"
    clock: str = "sample counter"


@dataclass(frozen=True)
class SampleBatch:
    batch_id: int
    samples_uv: np.ndarray  # channel-major float64; only EEG channels
    sample_indices: np.ndarray
    sample_rate_hz: float
    received_at: float
    source: str
    valid: bool = True


class Acquisition(Protocol):
    def start(self, config: dict) -> DeviceInfo: ...
    def read_batch(self) -> SampleBatch: ...
    def stop(self) -> None: ...


class SyntheticAdapter:
    """Fixed-seed samples, not canned decisions. No target field leaves this adapter."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.running = False

    def start(self, config: dict) -> DeviceInfo:
        self.rate = float(config.get("sample_rate_hz", 250))
        if not np.isfinite(self.rate) or not 100 <= self.rate <= 1000:
            raise ValueError("sample rate must be 100..1000 Hz")
        self.frequency = config.get("frequency_hz", 10.0)
        self.noise = float(config.get("noise_uv", 3.0))
        self.fault = config.get("fault")
        self.rng = np.random.default_rng(config.get("seed", 7))
        self.index = self.batch_id = 0
        self.size = max(1, round(self.rate / 10))
        self.running = True
        return DeviceInfo(effective_rate_hz=self.rate)

    def read_batch(self) -> SampleBatch:
        if not self.running:
            raise RuntimeError("adapter stopped/disconnected")
        indices = np.arange(self.index, self.index + self.size)
        t = indices / self.rate
        samples = self.rng.normal(0, self.noise, (2, self.size))
        if self.frequency is not None:
            for channel, phase in enumerate((0.0, 0.7)):
                samples[channel] += 18 * np.sin(2*np.pi*self.frequency*t + phase)
                samples[channel] += 6 * np.sin(4*np.pi*self.frequency*t + phase)
        samples += 2 * np.sin(2*np.pi*60*t)
        if self.fault == "flatline":
            samples[:] = 0
        elif self.fault == "clipped":
            samples[:] = 1000 * np.sign(samples)
        elif self.fault == "nonfinite":
            samples[0, 0] = np.nan
        self.index += self.size + (1 if self.fault == "gap" else 0)
        self.batch_id += 1
        return SampleBatch(self.batch_id, samples.astype(np.float64), indices,
                           self.rate, self.clock(), "synthetic")

    def stop(self) -> None:
        self.running = False
