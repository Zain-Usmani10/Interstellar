"""Presentation timing keeps the physics unchanged and fits the two-minute slot."""
import pytest

from app.backend.planner.demo import load_demo_plan
from app.backend.planner.plan import presentation_plan, verify_plan
from app.backend.runtime.sim_controller import SimulatedController
from app.backend.runtime.stores import load_validators
from app.contracts import protocol_v1 as p


def test_presentation_preserves_epochs_physics_and_original_identity():
    original = load_demo_plan("least_fuel")
    identity = original["plan_id"], original["plan_sha256"]
    fast = presentation_plan(original)
    load_validators()["mission_plan"].validate(fast)
    assert not verify_plan(fast)
    assert (original["plan_id"], original["plan_sha256"]) == identity
    assert fast["plan_id"] != original["plan_id"]
    assert fast["run_interval"]["real_demo_seconds"] == 63.05
    for key in ("nominal_path", "uncaptured_coast_path", "bodies", "wire", "residuals", "masses"):
        assert fast[key] == original[key]
    for tick in (0, 10, 6000, 12010, 12610):
        before = (tick-original["ticks"]["departure_tick"])*original["ticks"]["seconds_per_tick"]
        after = (tick/2-fast["ticks"]["departure_tick"])*fast["ticks"]["seconds_per_tick"]
        assert after == before


@pytest.mark.parametrize("miss_capture", [False, True])
def test_protocol_controller_finishes_within_presentation(miss_capture):
    now = [0.0]
    sim = SimulatedController(clock=lambda: now[0])
    plan = presentation_plan(load_demo_plan("least_fuel"))
    t, w = plan["ticks"], plan["wire"]
    wire = p.Plan(1, t["departure_tick"], t["arrival_tick"], t["end_tick"],
                  w["initial_fuel_g"], w["departure_fuel_g"], w["capture_fuel_g"])
    commands = [(p.MsgType.OPEN_SESSION, p.pack_u32(123)), (p.MsgType.LOAD_PLAN, wire.pack()),
                (p.MsgType.COMMIT_PLAN, p.pack_commit(1, wire.crc16())),
                (p.MsgType.ARM, p.pack_u32(1)), (p.MsgType.START, p.pack_u32(1))]
    for seq, (kind, payload) in enumerate(commands):
        session = 0 if kind == p.MsgType.OPEN_SESSION else 123
        ack = p.Ack.unpack(p.decode_frame(sim.handle(p.encode_frame(kind, seq, session, payload))).payload)
        assert ack.result == p.Result.APPLIED
    now[0] = 1.0
    if miss_capture:
        sim.inject_divergence()
    now[0] = 63.06
    status = p.Status.unpack(p.decode_frame(sim.status_frame()).payload)
    assert status.tick == (6305 if miss_capture else 6005)
    assert status.executed_mask == (1 if miss_capture else 3)
    assert status.state == (p.State.SAFE if miss_capture else p.State.COMPLETE)
