"""Causal 6–40 Hz filtering and rank-aware SVD CCA; scores aren't probabilities."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.signal import butter, sosfilt


@dataclass(frozen=True)
class DecoderConfig:
    sample_rate_hz: float = 250.0
    window_s: float = 2.0
    update_s: float = 0.25
    warmup_s: float = 0.5
    minimum_score: float = 0.80
    minimum_margin: float = 0.20
    stable_updates: int = 3
    maximum_uv: float = 200.0  # synthetic profile only, not a device calibration
    minimum_std_uv: float = 0.1


def orthonormal_basis(matrix: np.ndarray) -> np.ndarray:
    centered = matrix - matrix.mean(axis=0)
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    if not len(singular) or singular[0] < 1e-10:
        return u[:, :0]
    rank = np.count_nonzero(singular > singular[0] * 1e-8)
    return u[:, :rank]


def cca_scores(samples: np.ndarray, rate: float, frequencies: tuple[float, float]) -> tuple[float, float]:
    """Only samples and configured frequencies enter; no ground-truth labels."""
    if samples.ndim != 2 or samples.shape[1] < 8 or not np.isfinite(samples).all():
        raise ValueError("unusable EEG window")
    qx = orthonormal_basis(samples.T)
    if qx.shape[1] == 0:
        raise ValueError("flat window")
    t = np.arange(samples.shape[1]) / rate
    scores = []
    for frequency in frequencies:
        reference = np.column_stack([fn(2*np.pi*frequency*harmonic*t)
                                     for harmonic in (1, 2) for fn in (np.sin, np.cos)])
        qy = orthonormal_basis(reference)
        if qy.shape[1] != 4:
            raise ValueError("rank-deficient reference")
        scores.append(float(np.clip(np.linalg.svd(qx.T @ qy, compute_uv=False)[0], 0, 1)))
    return tuple(scores)


class Decoder:
    def __init__(self, config: DecoderConfig):
        self.config = config
        self.sos = butter(4, (6, 40), fs=config.sample_rate_hz, btype="bandpass", output="sos")
        self.reset()

    def reset(self):
        self.zi = np.zeros((len(self.sos), 2, 2))
        self.samples = np.empty((2, 0))
        self.indices = np.empty(0, dtype=np.int64)
        self.warmup = round(self.config.warmup_s * self.config.sample_rate_hz)
        self.since_update = 0
        self.candidate = None
        self.stability = 0

    def quality(self, samples: np.ndarray) -> str:
        if samples.ndim != 2 or samples.shape[0] != 2 or samples.shape[1] < 2:
            return "channel_count"
        if not np.isfinite(samples).all():
            return "nonfinite"
        if np.max(np.abs(samples)) >= self.config.maximum_uv:
            return "clipped"
        if np.any(samples.std(axis=1) < self.config.minimum_std_uv):
            return "flatline"
        return "valid"

    def feed(self, samples, indices, frequencies):
        filtered, self.zi = sosfilt(self.sos, samples, axis=1, zi=self.zi)
        discard = min(self.warmup, len(indices))
        self.warmup -= discard
        filtered, indices = filtered[:, discard:], indices[discard:]
        size = round(self.config.window_s * self.config.sample_rate_hz)
        self.samples = np.concatenate((self.samples, filtered), axis=1)[:, -size:]
        self.indices = np.concatenate((self.indices, indices))[-size:]
        self.since_update += len(indices)
        if len(self.indices) < size or self.since_update < round(self.config.update_s * self.config.sample_rate_hz):
            return None
        self.since_update = 0
        scores = cca_scores(self.samples, self.config.sample_rate_hz, frequencies)
        winner = int(np.argmax(scores))
        if scores[winner] < self.config.minimum_score or scores[winner] - scores[1-winner] < self.config.minimum_margin:
            self.candidate, self.stability = None, 0
            return {"scores": scores, "winner": None}
        self.stability = self.stability + 1 if winner == self.candidate else 1
        self.candidate = winner
        return {"scores": scores, "winner": winner if self.stability >= self.config.stable_updates else None}
