"""Reproducible synthetic engineering evaluation, never a human accuracy report."""
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import uuid

import numpy as np
from .acquisition import SyntheticAdapter
from .decoder import DecoderConfig
from .selection import SelectionGate, LABELS


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


def trial(frequency, rate, seed, duration=8):
    clock = Clock()
    adapter = SyntheticAdapter(clock)
    info = adapter.start({"frequency_hz": frequency, "sample_rate_hz": rate, "seed": seed})
    gate = SelectionGate(DecoderConfig(sample_rate_hz=rate), clock=clock)
    context = {"schema_version": 1, "context_id": str(uuid.uuid4()), "revision": 0,
               "input_session_id": str(uuid.uuid4()), "enabled": True, "expires_in_ms": 10000,
               "allowed_targets": ["planet.399", "planet.499"]}
    gate.configure(context, context["allowed_targets"], (10, 15))
    try:
        for n in range(int(duration*rate/adapter.size)):
            clock.now += adapter.size/rate
            if n % 5 == 0: gate.context_update(context)
            gate.stimulus({"context_id": context["context_id"], "context_revision": 0,
                           "sequence": n, "frame_count": n+1, "dropped_frames": 0,
                           "active": True, "visible": True, "focused": True,
                           "largest_frame_gap_ms": 17, "effective_frequencies_hz": [10, 15]})
            intent = gate.feed(adapter.read_batch())
            if intent:
                return intent, clock.now, info
        return None, clock.now, info
    finally:
        adapter.stop()


def evaluate(trials=10, rate=250, seed=19):
    cues = [10 if i % 2 == 0 else 15 for i in range(trials)]
    np.random.default_rng(seed).shuffle(cues)
    correct = wrong = missing = 0
    latencies = []
    counts = []
    for number, cue in enumerate(cues):
        intent, elapsed, info = trial(cue, rate, seed+number)
        if intent is None:
            missing += 1
        else:
            expected = "planet.399" if cue == 10 else "planet.499"
            correct += intent["target_id"] == expected
            wrong += intent["target_id"] != expected
            latencies.append(elapsed)
            counts.append(intent["evidence"]["sample_count"])
    idle, _, _ = trial(None, rate, seed+trials, duration=120)
    return {"label": LABELS["synthetic"], "source": "synthetic", "seed": seed,
            "device": asdict(info), "decoder": asdict(DecoderConfig(sample_rate_hz=rate)),
            "trials": trials, "correct": correct, "wrong": wrong, "no_decision": missing,
            "window_sample_counts": counts, "median_selection_source_s": float(np.median(latencies)) if latencies else None,
            "p90_selection_source_s": float(np.percentile(latencies, 90)) if latencies else None,
            "idle_duration_source_s": 120, "idle_selections": int(idle is not None),
            "limits": "Generated microvolt signals and simulated clock/frame reports; no live/replay EEG, monitor calibration, or human accuracy evidence. Operator rearm between trials."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=float, default=250)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.trials <= 1000:
        parser.error("trials must be 1..1000")
    report = json.dumps(evaluate(args.trials, args.rate), indent=2)
    if args.output: args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
