"""Simulated controller vs protocol v1. Software only: says nothing about the real FPGA."""
from pathlib import Path

import pytest

from app.backend.runtime.link import Link, LinkError
from app.backend.runtime.sim_controller import SimulatedController, SimulatorTransport
from app.contracts import protocol_v1 as p

FRAMES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "frames"
T, S, D = p.MsgType, p.State, p.Detail
SESSION, MISSION = 0x1A2B3C4D, 0x00C0FFEE


def golden(name: str) -> bytes:
    return (FRAMES / f"{name}.bin").read_bytes()


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def ticks(self, count: int) -> None:
        self.now += count / 100.0


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def sim(clock):
    return SimulatedController(clock=clock)


def status(sim) -> p.Status:
    return p.Status.unpack(p.decode_frame(sim.status_frame()).payload)


def ack(reply: bytes) -> p.Ack:
    return p.Ack.unpack(p.decode_frame(reply).payload)


def run_to_armed(sim):
    for name in ("03_open_session", "06_load_plan", "08_commit_plan", "11_arm"):
        assert ack(sim.handle(golden(name))).result == p.Result.APPLIED


def run_to_running(sim):
    run_to_armed(sim)
    assert ack(sim.handle(golden("13_start"))).result == p.Result.APPLIED


def test_replies_match_golden_frames_byte_for_byte(sim):
    assert sim.handle(golden("01_discover")) == golden("02_status_after_reset")
    for request, reply in (("03_open_session", "04_ack_open_session"), ("06_load_plan", "07_ack_load_plan"),
                           ("08_commit_plan", "09_ack_commit_plan"), ("11_arm", "12_ack_arm"),
                           ("13_start", "14_ack_start")):
        assert sim.handle(golden(request)) == golden(reply), request


def test_full_nominal_mission(sim, clock):
    run_to_running(sim)
    plan = p.Plan.unpack(p.decode_frame(golden("06_load_plan")).payload)
    clock.ticks(5)
    assert status(sim).executed_mask == 0
    clock.ticks(6000)
    st = status(sim)
    assert (st.state, st.executed_mask, st.departure_executed_tick) == (S.RUNNING, 1, plan.departure_tick)
    assert st.fuel_remaining_g == plan.initial_fuel_g - plan.departure_fuel_g
    clock.ticks(7000)
    st = status(sim)
    assert (st.state, st.executed_mask, st.capture_executed_tick) == (S.COMPLETE, 3, plan.arrival_tick)
    assert st.tick == plan.arrival_tick and st.fuel_remaining_g == 0
    clock.ticks(5000)
    assert status(sim).tick == plan.arrival_tick          # COMPLETE stops the clock


def test_exact_retry_is_not_applied_twice(sim, clock):
    run_to_armed(sim)
    first = sim.handle(golden("13_start"))
    clock.ticks(300)
    assert sim.handle(golden("13_start")) == first        # cached ACK, clock not restarted
    assert status(sim).tick == 300


def test_sequence_conflict_and_stale(sim):
    run_to_armed(sim)                                     # last sequence is 3 (ARM)
    conflict = p.encode_frame(T.START, 3, SESSION, p.pack_u32(MISSION))
    assert ack(sim.handle(conflict)).detail == D.SEQ_CONFLICT
    stale = p.encode_frame(T.START, 2, SESSION, p.pack_u32(MISSION))
    assert ack(sim.handle(stale)).detail == D.STALE_SEQ
    assert status(sim).state == S.ARMED
    assert ack(sim.handle(golden("13_start"))).result == p.Result.APPLIED   # sequence 4 still free


def test_bad_session_reports_the_real_session(sim):
    run_to_armed(sim)
    reply = p.decode_frame(sim.handle(p.encode_frame(T.START, 4, 0xDEADBEEF, p.pack_u32(MISSION))))
    assert p.Ack.unpack(reply.payload).detail == D.BAD_SESSION and reply.session_id == SESSION
    assert status(sim).state == S.ARMED


def test_guards(sim):
    sim.handle(golden("03_open_session"))
    sim.handle(golden("06_load_plan"))
    bad_crc = p.encode_frame(T.COMMIT_PLAN, 2, SESSION, p.pack_commit(MISSION, 0x1234))
    assert ack(sim.handle(bad_crc)).detail == D.BAD_PLAN_CRC
    assert status(sim).state == S.IDLE                    # an uncommitted plan cannot be armed
    arm = p.encode_frame(T.ARM, 3, SESSION, p.pack_u32(MISSION))
    assert ack(sim.handle(arm)).detail == D.BAD_STATE
    commit = p.encode_frame(T.COMMIT_PLAN, 4, SESSION, p.pack_commit(MISSION, p.Plan.unpack(
        p.decode_frame(golden("06_load_plan")).payload).crc16()))
    assert ack(sim.handle(commit)).result == p.Result.APPLIED
    start = p.encode_frame(T.START, 5, SESSION, p.pack_u32(MISSION))
    assert ack(sim.handle(start)).detail == D.BAD_STATE   # START while LOADED
    wrong = p.encode_frame(T.ARM, 6, SESSION, p.pack_u32(MISSION + 1))
    assert ack(sim.handle(wrong)).detail == D.BAD_MISSION


def test_invalid_plan_is_not_staged(sim):
    sim.handle(golden("03_open_session"))
    bad = p.Plan(MISSION, 20, 20, 30, 10, 5, 5)
    assert ack(sim.handle(p.encode_frame(T.LOAD_PLAN, 1, SESSION, bad.pack()))).detail == D.BAD_PLAN
    commit = p.encode_frame(T.COMMIT_PLAN, 2, SESSION, p.pack_commit(MISSION, bad.crc16()))
    assert ack(sim.handle(commit)).detail == D.BAD_MISSION


@pytest.mark.parametrize("name", ["40_invalid_bad_crc", "41_invalid_bad_version", "42_invalid_oversize_length",
                                  "43_invalid_wrong_length_for_type", "44_invalid_unknown_type"])
def test_invalid_frames_are_counted_and_ignored(sim, name):
    run_to_armed(sim)
    assert sim.handle(golden(name)) is None
    st = status(sim)
    assert st.rx_error_count == 1 and st.state == S.ARMED


def test_single_fault_is_masked_and_mission_completes(sim, clock):
    run_to_running(sim)
    clock.ticks(6000)
    sim.inject_single()
    clock.ticks(7000)
    st = status(sim)
    assert (st.state, st.masked_fault_count, st.executed_mask) == (S.COMPLETE, 1, 3)


def test_divergence_after_departure_inhibits_capture_but_clock_runs(sim, clock):
    run_to_running(sim)
    plan = p.Plan.unpack(p.decode_frame(golden("06_load_plan")).payload)
    clock.ticks(6000)
    sim.inject_divergence()
    clock.ticks(20000)
    st = status(sim)
    assert (st.state, st.safe_reason, st.no_majority_count) == (S.SAFE, p.SafeReason.NO_MAJORITY, 1)
    assert st.executed_mask == 1 and st.capture_executed_tick == p.UNSET_TICK
    assert st.tick == plan.end_tick                        # uncaptured coast runs to end_tick
    assert st.fuel_remaining_g == plan.initial_fuel_g - plan.departure_fuel_g


def test_divergence_before_start_does_not_start_the_clock(sim, clock):
    run_to_armed(sim)
    sim.inject_divergence()
    clock.ticks(500)
    st = status(sim)
    assert (st.state, st.tick, st.executed_mask) == (S.SAFE, 0, 0)
    assert ack(sim.handle(golden("13_start"))).detail == D.BAD_STATE


def test_abort_then_clear(sim, clock):
    sim2 = sim
    run_to_running(sim2)
    clock.ticks(100)
    clear_running = p.encode_frame(T.CLEAR, 5, SESSION, p.pack_u32(MISSION))
    assert ack(sim2.handle(clear_running)).detail == D.BAD_STATE          # no CLEAR while RUNNING
    abort = p.encode_frame(T.ABORT, 6, SESSION, p.pack_u32(MISSION))
    assert ack(sim2.handle(abort)).result == p.Result.APPLIED
    clock.ticks(20000)
    st = status(sim2)
    assert st.state == S.ABORTED and st.executed_mask == 1                # departed, never captured
    clear = p.encode_frame(T.CLEAR, 7, SESSION, p.pack_u32(MISSION))
    assert ack(sim2.handle(clear)).result == p.Result.APPLIED
    assert status(sim2).state == S.IDLE and status(sim2).mission_id == 0


def test_reset_forgets_everything_and_old_start_cannot_resume(sim, clock):
    run_to_running(sim)
    sim.reset()
    reply = p.decode_frame(sim.handle(golden("13_start")))
    assert p.Ack.unpack(reply.payload).detail == D.BAD_SESSION and reply.session_id == 0
    assert status(sim).state == S.IDLE


def test_open_session_only_while_idle(sim):
    run_to_armed(sim)
    takeover = p.encode_frame(T.OPEN_SESSION, 0, 0, p.pack_u32(0x55555555))
    assert ack(sim.handle(takeover)).detail == D.BAD_STATE


def test_link_round_trip_and_timeout(sim):
    transport = SimulatorTransport(sim)
    transport.open()
    seen = []
    link = Link(transport, lambda session, st: seen.append(st), retry_timeout_s=0.05)
    assert link.read_status()[1].state == S.IDLE
    assert link.open_session().result == p.Result.APPLIED and link.session_id != 0
    plan = p.Plan(7, 10, 20, 30, 300, 200, 100)
    assert link.mutate(T.LOAD_PLAN, plan.pack()).plan_crc16 == plan.crc16()
    assert link.mutate(T.COMMIT_PLAN, p.pack_commit(7, plan.crc16())).result == p.Result.APPLIED
    assert link.mutate(T.START, p.pack_u32(7)).detail == D.BAD_STATE       # rejected, sequence consumed
    assert link.mutate(T.ARM, p.pack_u32(7)).result == p.Result.APPLIED
    assert seen                                                            # telemetry reached the callback

    sim.handle = lambda data: None                                         # board stops answering
    with pytest.raises(LinkError):
        link.mutate(T.START, p.pack_u32(7))


class ForgingTransport(SimulatorTransport):
    """Puts a wrong ACK in front of every real reply, like stale traffic from another session/mission."""

    def __init__(self, sim, forge):
        super().__init__(sim)
        self.forge = forge

    def send(self, frame: bytes) -> None:
        fake = self.forge(p.decode_frame(frame))
        if fake:
            self._rx.append(fake)
        super().send(frame)


def test_link_ignores_ack_for_another_session_or_mission(sim):
    def forge(request):
        if request.msg_type not in p.MUTATION_TYPES:
            return None
        wrong_mission = p.Ack(request.msg_type, p.Result.REJECTED, D.BAD_STATE, 999, 0, 0)
        return p.encode_frame(T.ACK, request.sequence, request.session_id, wrong_mission.pack())

    transport = ForgingTransport(sim, forge)
    transport.open()
    link = Link(transport, lambda session, st: None, retry_timeout_s=0.05)
    link.open_session()
    plan = p.Plan(7, 10, 20, 30, 300, 200, 100)
    assert link.mutate(T.LOAD_PLAN, plan.pack()).result == p.Result.APPLIED      # forged NACK skipped

    transport.forge = lambda request: (p.encode_frame(T.ACK, request.sequence, 0x0BADBEEF, p.Ack(
        request.msg_type, p.Result.REJECTED, D.BAD_STATE, 7, 0, 0).pack())
        if request.msg_type in p.MUTATION_TYPES else None)
    assert link.mutate(T.COMMIT_PLAN, p.pack_commit(7, plan.crc16())).result == p.Result.APPLIED


def test_link_reports_bad_session_and_uses_transport_timeout(sim):
    transport = SimulatorTransport(sim)
    transport.open()
    link = Link(transport, lambda session, st: None, retry_timeout_s=0.05)
    link.open_session()
    sim.reset()                                                # board forgets our session
    ack = link.mutate(T.ARM, p.pack_u32(7))
    assert ack.detail == D.BAD_SESSION and link.next_seq == 1  # answered, sequence not consumed
    transport.retry_timeout_s = 6.5                            # what a DelayTransport would publish
    assert link.retry_timeout_s == 6.5
