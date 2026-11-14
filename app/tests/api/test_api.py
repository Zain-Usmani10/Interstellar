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
    assert client.post("/api/v1/planning/jobs", json=body, headers=operator(app)).status_code == 503
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
    sent_before = client.get("/api/v1/health").json()["transport"]["stats"]["frames_sent"]
    session, headers = register(client)
    assert client.post("/api/v1/input/intents", json=intent(session), headers=headers).json()["accepted"]
    assert client.get("/api/v1/health").json()["transport"]["stats"]["frames_sent"] == sent_before
    assert app.state.runtime._mission is None


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
