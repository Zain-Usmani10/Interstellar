"""HTTP/WebSocket tests against the SIMULATED CONTROLLER. No hardware, no NASA requests."""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.runtime.sim_controller import SimulatedController, SimulatorTransport
from app.backend.runtime.stores import Settings, fixture, load_validators

VALIDATORS = load_validators()
PLAN_ID = fixture("mission_plan_earth_mars")["plan_id"]
EVIDENCE = fixture("selection_intent_synthetic")["evidence"]


class FakeClock:
    def __init__(self):
        self.now = 50.0

    def __call__(self):
        return self.now


def make_client(tmp_path, brain_enabled=False):
    clock = FakeClock()
    settings = Settings(db_path=str(tmp_path / "test.sqlite3"), plans_dir=str(tmp_path / "plans"),
                        brain_enabled=brain_enabled)
    app = create_app(settings, SimulatorTransport(SimulatedController(clock=clock)))
    return TestClient(app), app, clock


@pytest.fixture
def ctx(tmp_path):
    client, app, clock = make_client(tmp_path)
    with client:
        yield client, app, clock


@pytest.fixture
def brain_ctx(tmp_path):
    client, app, clock = make_client(tmp_path, brain_enabled=True)
    with client:
        yield client, app, clock


def operator(app):
    return {"X-Operator-Token": app.state.operator_token}


def wait_for(client, mission_id, predicate, timeout=3.0):
    """Poll the mission until the snapshot (built only from controller telemetry) satisfies predicate."""
    deadline = time.monotonic() + timeout
    while True:
        snap = client.get(f"/api/v1/missions/{mission_id}").json()
        if predicate(snap) or time.monotonic() > deadline:
            return snap
        time.sleep(0.05)


def command(client, app, mission_id, name):
    return client.post(f"/api/v1/missions/{mission_id}/commands", json={"command": name}, headers=operator(app)).json()


def new_mission(client, app):
    response = client.post("/api/v1/missions", json={"plan_id": PLAN_ID}, headers=operator(app))
    assert response.status_code == 201
    return response.json()["mission_id"]


def register(client, source="mouse"):
    response = client.post("/api/v1/input/sessions", json={"source": source, "adapter": {"name": "test"}})
    assert response.status_code == 201, response.text
    body = response.json()
    return body, {"X-Input-Token": body["token"]}


def intent(session, target="planet.499", source="mouse", **changes):
    context = session["context"]
    body = {"schema_version": 1, "event_id": str(uuid.uuid4()), "input_session_id": session["input_session_id"],
            "context_id": context["context_id"], "context_revision": context["revision"],
            "target_id": target, "source": source}
    if source in ("synthetic", "replay", "live_eeg"):
        body["evidence"] = dict(EVIDENCE)
    body.update(changes)
    return body


def heartbeat(client, session, headers, **changes):
    context = client.get("/api/v1/input/context", headers=headers).json()
    body = {"context_id": context["context_id"], "context_revision": context["revision"],
            "source_state": "ready", "acquisition_age_ms": 20, "stimulus_ready": True}
    body.update(changes)
    response = client.post(f"/api/v1/input/sessions/{session['input_session_id']}/heartbeat", json=body, headers=headers)
    assert response.status_code == 200, response.text
    session["context"] = response.json()
    return session["context"]


# ------------------------------------------------------------------ general, planets, plans

def test_health_labels_the_simulator(ctx):
    client, _, _ = ctx
    body = client.get("/api/v1/health").json()
    assert body["transport"]["controller_label"] == "SIMULATED CONTROLLER"
    assert body["data_mode"] == "synthetic" and body["brain_enabled"] is False


def test_planets_and_info(ctx):
    client, _, _ = ctx
    assert [pl["target_id"] for pl in client.get("/api/v1/planets").json()["planets"]] == ["planet.399", "planet.499"]
    for body_id in ("399", "499"):
        info = client.get(f"/api/v1/planets/{body_id}/info").json()
        assert VALIDATORS["planet_info"].is_valid(info) and info["body_id"] == body_id
    assert client.get("/api/v1/planets/499/info").json()["conditions"]["availability"] == "unavailable"
    assert client.get("/api/v1/planets/299/info").status_code == 404


def test_plans(ctx):
    client, _, _ = ctx
    assert client.get("/api/v1/plans").json()["plans"][0]["plan_id"] == PLAN_ID
    assert VALIDATORS["mission_plan"].is_valid(client.get(f"/api/v1/plans/{PLAN_ID}").json())
    assert client.get("/api/v1/plans/nope").status_code == 404


def test_planning_job_says_unavailable_instead_of_faking(ctx):
    client, app, _ = ctx
    body = {"departure_start_utc": "2026-11-15T00:00:00Z", "departure_end_utc": "2027-02-15T00:00:00Z",
            "tof_min_days": 120, "tof_max_days": 360, "n_departures": 5, "n_durations": 5}
    available = client.get("/api/v1/health").json()["planner_available"]
    # Without the planner module the backend must say so; with it, the job is queued.
    assert client.post("/api/v1/planning/jobs", json=body, headers=operator(app)).status_code == (202 if available else 503)
    assert client.post("/api/v1/planning/jobs", json=dict(body, n_departures=26), headers=operator(app)).status_code == 422


def test_foreign_origin_is_refused(ctx):
    client, _, _ = ctx
    assert client.get("/api/v1/session", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/v1/session", headers={"Origin": "http://localhost:5173"}).status_code == 200


# ------------------------------------------------------------------ missions

def test_nominal_mission_end_to_end(ctx):
    client, app, clock = ctx
    mission_id = new_mission(client, app)
    result = command(client, app, mission_id, "upload")
    assert result["applied"] and result["detail"] == "OK"
    snap = wait_for(client, mission_id, lambda s: s["state"] == "LOADED")
    assert VALIDATORS["mission_snapshot"].is_valid(snap)
    assert snap["spacecraft"]["phase"] == "at_origin" and snap["controller_label"] == "SIMULATED CONTROLLER"

    assert command(client, app, mission_id, "arm")["applied"]
    assert command(client, app, mission_id, "start")["applied"]
    clock.now += 60                                            # 6000 controller ticks
    snap = wait_for(client, mission_id, lambda s: s["executed_mask"] == 1)
    assert snap["state"] == "RUNNING" and snap["spacecraft"]["phase"] == "coast"
    assert snap["departure_executed_tick"] == 10 and snap["link"]["delay_physical_s"] > 0

    clock.now += 70
    snap = wait_for(client, mission_id, lambda s: s["state"] == "COMPLETE")
    assert snap["outcome"] == "captured" and snap["capture_executed_tick"] == 12010
    assert snap["fuel_remaining_g"] == 0 and VALIDATORS["mission_snapshot"].is_valid(snap)


def test_nominal_mission_through_the_delay_layer(tmp_path):
    """Same nominal run with the transport wrapped in DelayTransport: slower, but nothing is lost."""
    from app.backend.transport import DelayTransport
    clock = FakeClock()
    settings = Settings(db_path=str(tmp_path / "test.sqlite3"), plans_dir=str(tmp_path / "plans"))
    app = create_app(settings, DelayTransport(SimulatorTransport(SimulatedController(clock=clock))))
    with TestClient(app) as client:
        mission_id = new_mission(client, app)
        for name in ("upload", "arm", "start"):
            assert command(client, app, mission_id, name)["applied"], name
        clock.now += 60
        snap = wait_for(client, mission_id, lambda s: s["executed_mask"] == 1, timeout=10)
        assert snap["state"] == "RUNNING" and 0.1 <= snap["link"]["delay_demo_s"] <= 3.0
        client.post("/api/v1/sim/faults", json={"kind": "single"}, headers=operator(app))
        clock.now += 70
        snap = wait_for(client, mission_id, lambda s: s["state"] == "COMPLETE", timeout=15)
        assert snap["outcome"] == "captured" and VALIDATORS["mission_snapshot"].is_valid(snap)
        assert snap["faults"]["masked_fault_count"] >= 1


def running_mission(client, app, clock):
    mission_id = new_mission(client, app)
    for name in ("upload", "arm", "start"):
        assert command(client, app, mission_id, name)["applied"], name
    clock.now += 60
    wait_for(client, mission_id, lambda s: s["executed_mask"] == 1)
    return mission_id


def test_upload_sends_trip_days_and_snapshot_counts_down(ctx):
    client, app, clock = ctx
    mission_id = new_mission(client, app)
    assert client.get(f"/api/v1/missions/{mission_id}").json()["trip"] == {"trip_days": None, "days_to_arrival": None}
    assert command(client, app, mission_id, "upload")["applied"]
    snap = wait_for(client, mission_id, lambda s: s["state"] == "LOADED")
    days = snap["trip"]["trip_days"]
    assert days and snap["trip"]["days_to_arrival"] == days and snap["date_utc"].endswith("Z")
    assert app.state.runtime.transport.controller.trip_days == days
    for name in ("arm", "start"):
        command(client, app, mission_id, name)
    clock.now += 60
    snap = wait_for(client, mission_id, lambda s: s["executed_mask"] == 1)
    assert 0 < snap["trip"]["days_to_arrival"] < days and VALIDATORS["mission_snapshot"].is_valid(snap)


def test_blackout_freezes_confirmed_values_and_shows_an_estimate(ctx):
    client, app, clock = ctx
    mission_id = running_mission(client, app, clock)
    assert client.post(f"/api/v1/missions/{mission_id}/commands", json={"command": "blackout_end"},
                       headers=operator(app)).status_code == 409        # nothing to end
    before = command(client, app, mission_id, "blackout_start")["snapshot"]
    assert before["link"]["blackout"] and before["estimate"]["tick"] >= before["tick"]
    sent = app.state.runtime.transport.stats()["frames_sent"]
    clock.now += 5                                                      # the controller keeps flying
    time.sleep(0.8)
    snap = client.get(f"/api/v1/missions/{mission_id}").json()
    assert snap["tick"] == before["tick"] and snap["outcome"] == "pending"   # confirmed values frozen
    assert snap["estimate"]["tick"] > before["estimate"]["tick"]             # only the estimate moves
    assert snap["estimate"]["spacecraft"]["phase"] == "coast" and VALIDATORS["mission_snapshot"].is_valid(snap)
    assert app.state.runtime.transport.stats()["frames_sent"] == sent      # nothing was sent to the shuttle
    refused = client.post(f"/api/v1/missions/{mission_id}/commands", json={"command": "abort"}, headers=operator(app))
    assert refused.status_code == 409 and "no contact" in refused.text

    assert command(client, app, mission_id, "blackout_end")["applied"]
    snap = wait_for(client, mission_id, lambda s: s["reconciliation"] is not None)
    assert not snap["link"]["blackout"] and snap["estimate"] is None and snap["tick"] > before["tick"]
    assert snap["reconciliation"]["blackout_start_tick"] == before["tick"]


def test_fault_during_blackout_is_found_on_sync_not_estimated_away(ctx):
    client, app, clock = ctx
    mission_id = running_mission(client, app, clock)
    command(client, app, mission_id, "blackout_start")
    client.post("/api/v1/sim/faults", json={"kind": "divergence"}, headers=operator(app))   # SAFE, out of contact
    runtime = app.state.runtime
    runtime._blackout["at"] -= 200                       # pretend the blackout has lasted past arrival
    snap = wait_for(client, mission_id, lambda s: s["reconciliation"] is not None)        # contact returns by itself
    assert snap["state"] == "SAFE" and snap["outcome"] != "captured"
    rec = snap["reconciliation"]
    assert not rec["estimate_matched"] and any("Estimate: COMPLETE. Actual: SAFE." in d for d in rec["differences"])
    assert {"event": "state_change", "from": "RUNNING", "to": "SAFE"} in rec["events_during_blackout"]
    assert VALIDATORS["mission_snapshot"].is_valid(snap)


def test_automatic_blackout_once_per_flight(tmp_path):
    clock = FakeClock()
    settings = Settings(db_path=str(tmp_path / "test.sqlite3"), plans_dir=str(tmp_path / "plans"), auto_blackout=True)
    app = create_app(settings, SimulatorTransport(SimulatedController(clock=clock)))
    with TestClient(app) as client:
        mission_id = new_mission(client, app)
        for name in ("upload", "arm", "start"):
            assert command(client, app, mission_id, name)["applied"], name
        snap = client.get(f"/api/v1/missions/{mission_id}").json()
        assert not snap["link"]["blackout"]                              # not before the window
        clock.now += 60                                                  # tick 6000: inside 25 %..85 %
        snap = wait_for(client, mission_id, lambda s: s["link"]["blackout"])
        assert snap["estimate"] is not None and snap["executed_mask"] == 1
        app.state.runtime._blackout["at"] -= 60                          # the estimate passes 85 %
        snap = wait_for(client, mission_id, lambda s: s["reconciliation"] is not None)
        assert not snap["link"]["blackout"] and snap["state"] == "RUNNING"   # back before arrival
        time.sleep(0.4)
        assert not client.get(f"/api/v1/missions/{mission_id}").json()["link"]["blackout"]   # only once
        clock.now += 70
        assert wait_for(client, mission_id, lambda s: s["state"] == "COMPLETE")["outcome"] == "captured"


def test_link_indicator_follows_real_frames(ctx):
    client, app, clock = ctx
    health = lambda: client.get("/api/v1/health").json()["transport"]["link_indicator"]   # noqa: E731
    deadline = time.monotonic() + 3
    while health() != "active" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert health() == "active"                                   # STATUS frames are arriving
    mission_id = running_mission(client, app, clock)
    assert client.get(f"/api/v1/missions/{mission_id}").json()["link"]["indicator"] == "active"
    snap = command(client, app, mission_id, "blackout_start")["snapshot"]
    assert snap["link"]["indicator"] == "inactive" and health() == "inactive"
    runtime = app.state.runtime
    transport = runtime.transport
    original = transport.receive
    transport.receive = lambda timeout_s: (time.sleep(min(timeout_s, 0.01)), None)[1]   # the board cannot be heard
    command(client, app, mission_id, "blackout_end")
    time.sleep(0.6)
    assert health() == "reconnecting"                             # probing, but no valid STATUS yet
    assert client.get(f"/api/v1/missions/{mission_id}").json()["reconciliation"] is None
    transport.receive = original                                   # frames get through again
    snap = wait_for(client, mission_id, lambda s: s["link"]["indicator"] == "active")
    assert snap["reconciliation"] is not None and VALIDATORS["mission_snapshot"].is_valid(snap)


def test_blackout_needs_a_running_mission(ctx):
    client, app, clock = ctx
    mission_id = new_mission(client, app)
    command(client, app, mission_id, "upload")
    response = client.post(f"/api/v1/missions/{mission_id}/commands", json={"command": "blackout_start"},
                           headers=operator(app))
    assert response.status_code == 409


def shuttle(client, shuttle_id):
    return next(s for s in client.get("/api/v1/fleet").json()["shuttles"] if s["id"] == shuttle_id)


def test_fleet_shuttle_moves_only_on_confirmed_events(ctx):
    client, app, clock = ctx
    assert shuttle(client, "earth-standard")["location"] == {"kind": "docked", "body_id": "399"}
    assert shuttle(client, "earth-standard")["label"] == "Standard shuttle"
    mission_id = new_mission(client, app)
    snap = client.get(f"/api/v1/missions/{mission_id}").json()
    assert snap["shuttle_id"] == "earth-standard"
    for name in ("upload", "arm", "start"):
        command(client, app, mission_id, name)
    assert shuttle(client, "earth-standard")["location"]["kind"] == "docked"       # not departed yet
    clock.now += 60
    wait_for(client, mission_id, lambda s: s["executed_mask"] == 1)
    assert shuttle(client, "earth-standard")["location"] == {"kind": "in_flight", "mission_id": mission_id}
    clock.now += 70
    wait_for(client, mission_id, lambda s: s["state"] == "COMPLETE")
    assert shuttle(client, "earth-standard")["location"] == {"kind": "docked", "body_id": "499"}
    command(client, app, mission_id, "clear")
    # The only Standard shuttle that was at Earth is now at Mars: the same route cannot launch again.
    again = client.post("/api/v1/missions", json={"plan_id": PLAN_ID}, headers=operator(app))
    assert again.status_code == 409 and again.json()["detail"] == "NO_SHUTTLE_DOCKED"
    assert client.post("/api/v1/fleet/reset").status_code in (401, 403)             # operator only
    reset = client.post("/api/v1/fleet/reset", headers=operator(app)).json()
    assert next(s for s in reset["shuttles"] if s["id"] == "earth-standard")["location"]["body_id"] == "399"


def test_fleet_shuttle_is_lost_after_safe_in_flight_and_kept_after_early_clear(ctx):
    client, app, clock = ctx
    first = new_mission(client, app)
    command(client, app, first, "upload")
    command(client, app, first, "clear")                                            # never departed
    assert shuttle(client, "earth-standard")["location"] == {"kind": "docked", "body_id": "399"}
    mission_id = running_mission(client, app, clock)
    client.post("/api/v1/sim/faults", json={"kind": "divergence"}, headers=operator(app))
    wait_for(client, mission_id, lambda s: s["state"] == "SAFE")
    assert shuttle(client, "earth-standard")["location"] == {"kind": "lost", "mission_id": mission_id}


def test_fleet_refuses_wrong_class_or_absent_shuttle(ctx):
    client, app, _ = ctx
    for bad in ("earth-long-range", "mars-standard", "no-such-shuttle"):
        response = client.post("/api/v1/missions", json={"plan_id": PLAN_ID, "shuttle_id": bad}, headers=operator(app))
        assert response.status_code == 409 and response.json()["detail"] == "NO_SHUTTLE_DOCKED", bad
    assert client.post("/api/v1/missions", json={"plan_id": PLAN_ID, "shuttle_id": "earth-standard"},
                       headers=operator(app)).status_code == 201


def test_fleet_does_not_move_during_a_blackout(ctx):
    client, app, clock = ctx
    mission_id = running_mission(client, app, clock)
    command(client, app, mission_id, "blackout_start")
    clock.now += 70                                                                  # the controller captures
    time.sleep(0.5)
    assert shuttle(client, "earth-standard")["location"]["kind"] == "in_flight"      # no evidence yet
    command(client, app, mission_id, "blackout_end")
    wait_for(client, mission_id, lambda s: s["state"] == "COMPLETE")
    assert shuttle(client, "earth-standard")["location"] == {"kind": "docked", "body_id": "499"}


def test_planet_positions_for_all_eight_planets(ctx):
    client, _, _ = ctx
    body = client.get("/api/v1/planets/positions", params={"date_utc": "2027-03-01T00:00:00Z"}).json()
    assert [pl["body_id"] for pl in body["planets"]] == ["199", "299", "399", "499", "599", "699", "799", "899"]
    earth = next(pl for pl in body["planets"] if pl["body_id"] == "399")["r_km"]
    assert 1.45e8 < sum(x * x for x in earth) ** 0.5 < 1.53e8                        # about 1 au from the Sun
    same = client.get("/api/v1/planets/positions", params={"jd_tdb": body["epoch_jd_tdb"]}).json()
    assert same["planets"] == body["planets"] and body["data_mode"] == "nasa_cached"
    assert client.get("/api/v1/planets/positions", params={"jd_tdb": 2400000.5}).status_code == 404
    assert client.get("/api/v1/planets/positions").status_code == 422


def test_planet_track_block_matches_single_positions(ctx):
    client, _, _ = ctx
    limits = client.get("/api/v1/planets/positions", params={"date_utc": "2027-03-01T00:00:00Z"}).json()
    start = limits["epoch_jd_tdb"]
    block = client.get("/api/v1/planets/track", params={"start_jd_tdb": start, "end_jd_tdb": start + 30, "step_days": 7.5}).json()
    assert block["epochs_jd_tdb"] == [start, start + 7.5, start + 15, start + 22.5, start + 30]
    assert len(block["planets"]) == 8 and all(len(pl["r_km"]) == 5 for pl in block["planets"])
    assert [pl["r_km"][0] for pl in block["planets"]] == [pl["r_km"] for pl in limits["planets"]]
    assert block["planets"][2]["r_km"][0] != block["planets"][2]["r_km"][4]             # Earth moved
    bad = {"start_jd_tdb": start, "end_jd_tdb": start + 5000, "step_days": 1}
    assert client.get("/api/v1/planets/track", params=bad).status_code in (404, 422)
    assert client.get("/api/v1/planets/track", params={"start_jd_tdb": start, "end_jd_tdb": start + 1, "step_days": 0}).status_code == 422


def test_start_is_refused_until_armed(ctx):
    client, app, _ = ctx
    mission_id = new_mission(client, app)
    assert command(client, app, mission_id, "upload")["applied"]
    result = command(client, app, mission_id, "start")
    assert not result["applied"] and result["detail"] == "BAD_STATE"
    assert wait_for(client, mission_id, lambda s: s["state"] == "LOADED")["state"] == "LOADED"


def test_divergence_after_departure_gives_uncaptured_coast(ctx):
    client, app, clock = ctx
    mission_id = new_mission(client, app)
    for name in ("upload", "arm", "start"):
        assert command(client, app, mission_id, name)["applied"]
    clock.now += 60
    wait_for(client, mission_id, lambda s: s["executed_mask"] == 1)
    assert client.post("/api/v1/sim/faults", json={"kind": "divergence"}, headers=operator(app)).status_code == 200
    clock.now += 100
    snap = wait_for(client, mission_id, lambda s: s["tick"] == 12610)
    assert snap["state"] == "SAFE" and snap["safe_reason"] == "NO_MAJORITY"
    assert snap["outcome"] == "uncaptured" and snap["spacecraft"]["phase"] == "uncaptured_coast"
    assert snap["capture_executed_tick"] is None               # never shown as an arrival


def test_controller_reset_is_reported_as_lost_not_resumed(ctx):
    client, app, clock = ctx
    mission_id = new_mission(client, app)
    for name in ("upload", "arm", "start"):
        assert command(client, app, mission_id, name)["applied"]
    app.state.runtime.transport.controller.reset()             # power cycle / reprogram
    snap = wait_for(client, mission_id, lambda s: s["outcome"] == "lost")
    assert snap["outcome"] == "lost" and snap["failure"]["code"] == "CONTROLLER_LOST_MISSION"
    assert not command(client, app, mission_id, "start")["applied"]


def test_second_mission_needs_clear_first(ctx):
    client, app, _ = ctx
    mission_id = new_mission(client, app)
    assert command(client, app, mission_id, "upload")["applied"]
    wait_for(client, mission_id, lambda s: s["state"] == "LOADED")
    assert client.post("/api/v1/missions", json={"plan_id": PLAN_ID}, headers=operator(app)).status_code == 409
    assert command(client, app, mission_id, "clear")["applied"]
    wait_for(client, mission_id, lambda s: s["state"] == "IDLE")
    second = new_mission(client, app)
    assert command(client, app, second, "upload")["applied"]


def test_mission_routes_need_the_operator_token(ctx):
    client, app, _ = ctx
    assert client.post("/api/v1/missions", json={"plan_id": PLAN_ID}).status_code == 401
    mission_id = new_mission(client, app)
    _, input_headers = register(client)
    # An input-session token (what the EEG extension holds) cannot command the controller.
    for headers in (input_headers, {"X-Operator-Token": input_headers["X-Input-Token"]}):
        response = client.post(f"/api/v1/missions/{mission_id}/commands", json={"command": "upload"}, headers=headers)
        assert response.status_code in (401, 403)
    assert client.get(f"/api/v1/missions/{mission_id}").json()["state"] in ("UNKNOWN", "IDLE")


# ------------------------------------------------------------------ input layer

def test_mouse_selection_opens_planet_and_back(ctx):
    client, _, _ = ctx
    session, headers = register(client)
    result = client.post("/api/v1/input/intents", json=intent(session), headers=headers).json()
    assert result["accepted"] and VALIDATORS["intent_result"].is_valid(result)
    context = client.get("/api/v1/input/context", headers=headers).json()
    assert VALIDATORS["input_context"].is_valid(context)
    assert (context["screen"], context["selected_body_id"]) == ("planet_info", "499")
    assert context["allowed_targets"] == ["planet.more_details", "navigation.back"]
    session["context"] = context
    assert client.post("/api/v1/input/intents", json=intent(session, "navigation.back"), headers=headers).json()["accepted"]
    assert client.get("/api/v1/input/context", headers=headers).json()["screen"] == "planet_choice"


def test_duplicate_stale_and_conflicting_intents(ctx):
    client, _, _ = ctx
    session, headers = register(client)
    first = intent(session)
    accepted = client.post("/api/v1/input/intents", json=first, headers=headers).json()
    assert accepted["accepted"]
    # Exact retry: same answer, applied once.
    assert client.post("/api/v1/input/intents", json=first, headers=headers).json() == accepted
    assert client.get("/api/v1/input/context", headers=headers).json()["revision"] == accepted["new_context_revision"]
    # Same event id, different content.
    conflict = client.post("/api/v1/input/intents", json=dict(first, target_id="planet.399"), headers=headers).json()
    assert conflict["reason"] == "duplicate_event_conflict"
    # A new event still carrying the old revision.
    stale = client.post("/api/v1/input/intents", json=intent(session, "planet.399"), headers=headers).json()
    assert (stale["accepted"], stale["reason"]) == (False, "stale_context")


def test_schema_rejection_and_unavailable_action(ctx):
    client, _, _ = ctx
    session, headers = register(client)
    for bad in (intent(session, "mission.request_start"), intent(session, "planet.299"),
                dict(intent(session), command="START"), {"hello": "world"}):
        response = client.post("/api/v1/input/intents", json=bad, headers=headers)
        assert response.status_code == 422 and response.json()["reason"] == "invalid_schema"
    # Valid target id, but not offered on this screen.
    result = client.post("/api/v1/input/intents", json=intent(session, "navigation.back"), headers=headers).json()
    assert result["reason"] == "action_unavailable"
    assert client.post("/api/v1/input/intents", json=intent(session)).status_code == 401      # no token


def test_core_runs_with_brain_disabled(ctx):
    client, _, _ = ctx
    response = client.post("/api/v1/input/sessions", json={"source": "synthetic", "adapter": {"name": "sim"}})
    assert response.status_code == 403 and response.json()["error"] == "brain_disabled"
    session, headers = register(client, "keyboard")
    assert client.post("/api/v1/input/intents", json=intent(session, source="keyboard"), headers=headers).json()["accepted"]


def test_synthetic_source_needs_fresh_heartbeat(brain_ctx):
    client, app, _ = brain_ctx
    session, headers = register(client, "synthetic")
    no_beat = client.post("/api/v1/input/intents", json=intent(session, source="synthetic"), headers=headers).json()
    assert no_beat["reason"] == "stale_heartbeat"

    heartbeat(client, session, headers)
    bad_quality = intent(session, source="synthetic")
    bad_quality["evidence"]["quality"] = "artifact"
    assert client.post("/api/v1/input/intents", json=bad_quality, headers=headers).json()["reason"] == "invalid_quality"

    ok = client.post("/api/v1/input/intents", json=intent(session, source="synthetic"), headers=headers).json()
    assert ok["accepted"]

    # Heartbeat goes quiet for more than 2 s: the source is no longer trusted.
    heartbeat(client, session, headers)
    inputs = app.state.inputs
    real_clock = inputs._clock
    inputs._clock = lambda: real_clock() + 3.0
    late = client.post("/api/v1/input/intents", json=intent(session, "navigation.back", "synthetic"), headers=headers).json()
    assert late["reason"] == "stale_heartbeat"


def test_ten_synthetic_selections_change_the_panel(brain_ctx):
    client, _, _ = brain_ctx
    session, headers = register(client, "synthetic")
    for i in range(10):
        target = "planet.399" if i % 2 else "planet.499"
        heartbeat(client, session, headers)
        assert client.post("/api/v1/input/intents", json=intent(session, target, "synthetic"), headers=headers).json()["accepted"]
        assert client.get("/api/v1/input/context", headers=headers).json()["selected_body_id"] == target[-3:]
        heartbeat(client, session, headers)
        assert client.post("/api/v1/input/intents", json=intent(session, "navigation.back", "synthetic"), headers=headers).json()["accepted"]


def test_late_eeg_intent_after_mouse_action_is_stale(brain_ctx):
    client, _, _ = brain_ctx
    eeg, eeg_headers = register(client, "synthetic")
    mouse, mouse_headers = register(client)
    heartbeat(client, eeg, eeg_headers)
    pending = intent(eeg, "planet.399", "synthetic")           # decided on the old context
    assert client.post("/api/v1/input/intents", json=intent(mouse, "planet.499"), headers=mouse_headers).json()["accepted"]
    late = client.post("/api/v1/input/intents", json=pending, headers=eeg_headers).json()
    assert (late["accepted"], late["reason"]) == (False, "stale_context")
    assert client.get("/api/v1/input/context", headers=eeg_headers).json()["selected_body_id"] == "499"


def test_source_must_match_registration(brain_ctx):
    client, _, _ = brain_ctx
    session, headers = register(client, "synthetic")
    heartbeat(client, session, headers)
    disguised = intent(session, source="live_eeg")             # a synthetic source may not call itself live
    assert client.post("/api/v1/input/intents", json=disguised, headers=headers).json()["reason"] == "source_mismatch"


def test_selection_never_touches_the_controller(ctx):
    client, app, _ = ctx
    controller = app.state.runtime.transport.controller
    session, headers = register(client)
    assert client.post("/api/v1/input/intents", json=intent(session), headers=headers).json()["accepted"]
    # Only the read-only keep-alive may reach the controller: no session, no command, no plan.
    assert controller.session == 0 and controller._last_seq == 0 and controller.plan is None
    assert controller.state == 0 and app.state.runtime._mission is None    # 0 = IDLE


def test_deleted_session_is_inactive(ctx):
    client, _, _ = ctx
    session, headers = register(client)
    assert client.delete(f"/api/v1/input/sessions/{session['input_session_id']}", headers=headers).status_code == 204
    assert client.post("/api/v1/input/intents", json=intent(session), headers=headers).status_code == 401


def test_websocket_sends_hello_then_selection(ctx):
    client, _, _ = ctx
    session, headers = register(client)
    with client.websocket_connect("/api/v1/events") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["data"]["controller_label"] == "SIMULATED CONTROLLER"
        assert client.post("/api/v1/input/intents", json=intent(session), headers=headers).json()["accepted"]
        event = ws.receive_json()
        assert event["type"] == "selection" and event["data"]["selected_body_id"] == "499"
        assert event["server_seq"] > hello["server_seq"]
