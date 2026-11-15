from dataclasses import replace
import uuid

import numpy as np
import pytest
from app.brain.acquisition import SyntheticAdapter
from app.brain.decoder import DecoderConfig, cca_scores
from app.brain.selection import SelectionGate


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def advance(self, duration=0.1): self.now += duration


def context():
    return dict(schema_version=1, context_id=str(uuid.uuid4()), revision=0,
                input_session_id=str(uuid.uuid4()), capability="planet_explore", screen="planet_choice",
                selected_body_id=None, allowed_targets=["planet.399", "planet.499"], enabled=True, expires_in_ms=10000)


def stimulus(gate, n):
    return dict(context_id=gate.context["context_id"], context_revision=gate.context["revision"],
                sequence=n, active=True, visible=True, focused=True, frame_count=n+1, dropped_frames=0,
                largest_frame_gap_ms=17, effective_frequencies_hz=[10, 15])


def setup(frequency=10, rate=250, fault=None):
    clock = Clock()
    adapter = SyntheticAdapter(clock)
    adapter.start(dict(frequency_hz=frequency, sample_rate_hz=rate, fault=fault))
    gate = SelectionGate(DecoderConfig(sample_rate_hz=rate), clock=clock)
    gate.configure(context(), ["planet.399", "planet.499"], [10, 15])
    return clock, adapter, gate


def run(clock, adapter, gate, count=60):
    intents = []
    for n in range(count):
        clock.advance(adapter.size/adapter.rate)
        gate.stimulus(stimulus(gate, n))
        intent = gate.feed(adapter.read_batch())
        if intent: intents.append(intent)
    return intents


@pytest.mark.parametrize("rate", [250, 244.14])
@pytest.mark.parametrize("frequency,target", [(10, "planet.399"), (15, "planet.499")])
def test_samples_select_target_once(rate, frequency, target):
    clock, adapter, gate = setup(frequency, rate)
    intents = run(clock, adapter, gate)
    assert len(intents) == 1 and intents[0]["target_id"] == target
    assert intents[0]["source"] == "synthetic"
    gate.configure(gate.context, gate.targets, gate.frequencies)
    assert gate.state == "DECISION_SENT"


@pytest.mark.parametrize("fault", ["gap", "clipped", "flatline", "nonfinite"])
def test_corrupt_samples_disarm(fault):
    clock, adapter, gate = setup(fault=fault)
    assert run(clock, adapter, gate) == []
    assert gate.state == "WAIT_RELEASE"


def test_noise_no_decision():
    clock, adapter, gate = setup(frequency=None)
    assert run(clock, adapter, gate) == []


@pytest.mark.parametrize("field,value", [("visible", False), ("focused", False), ("active", False),
                                        ("dropped_frames", 1), ("largest_frame_gap_ms", 70), ("context_revision", 99)])
def test_stimulus_fault_requires_explicit_rearm(field, value):
    clock, adapter, gate = setup()
    message = stimulus(gate, 0)
    message[field] = value
    gate.stimulus(message)
    assert run(clock, adapter, gate) == []
    assert gate.state == "WAIT_RELEASE"


def test_stimulus_timeout_and_context_change_clear_samples():
    clock, adapter, gate = setup()
    run(clock, adapter, gate, 20)
    assert gate.decoder.samples.size
    clock.advance(0.6)
    assert not gate.active()
    assert not gate.decoder.samples.size
    gate.context_update({**gate.context, "revision": 1})
    assert gate.feed(adapter.read_batch()) is None
    assert gate.state == "WAIT_RELEASE"


@pytest.mark.parametrize("change", [{"source": "live_eeg"}, {"sample_rate_hz": 244.14}, {"received_at": -10}])
def test_source_rate_and_stale_batch(change):
    clock, adapter, gate = setup()
    gate.stimulus(stimulus(gate, 0))
    clock.advance(0.6)
    gate.stimulus(stimulus(gate, 1))
    assert gate.feed(replace(adapter.read_batch(), **change)) is None
    assert gate.state == "WAIT_RELEASE"


def test_cca_matches_independent_covariance_eigenvalue():
    rng = np.random.default_rng(14)
    t = np.arange(500)/250
    x = rng.normal(size=(500, 2)) + np.sin(2*np.pi*10*t)[:, None]
    y = np.column_stack([f(2*np.pi*h*10*t) for h in (1, 2) for f in (np.sin, np.cos)])
    x -= x.mean(axis=0)
    y -= y.mean(axis=0)
    matrix = np.linalg.solve(x.T@x, x.T@y) @ np.linalg.solve(y.T@y, y.T@x)
    reference = np.sqrt(np.linalg.eigvals(matrix).real.max())
    assert cca_scores(x.T, 250, (10, 15))[0] == pytest.approx(reference, abs=1e-10)


def test_stopped_adapter_never_falls_back():
    _, adapter, _ = setup()
    adapter.stop()
    with pytest.raises(RuntimeError): adapter.read_batch()


def test_mission_target_cannot_be_configured():
    _, _, gate = setup()
    with pytest.raises(ValueError):
        gate.configure({**gate.context, "allowed_targets": ["mission.request_start", "planet.399"]},
                       ["mission.request_start", "planet.399"], [10, 15])
