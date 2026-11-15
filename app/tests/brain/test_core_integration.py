"""Actual leader API + canonical schemas, with synthetic samples and simulator only."""
import asyncio
import copy
import uuid

import httpx
from fastapi.testclient import TestClient
import pytest

from app.backend.api.app import create_app
from app.backend.runtime.stores import Settings, load_validators
from app.brain.acquisition import DeviceInfo, SyntheticAdapter
from app.brain.client import CoreClient
from app.brain.selection import SelectionGate
from test_selection import Clock, stimulus


@pytest.fixture
def backend():
    return create_app(Settings(brain_enabled=True, db_path=":memory:", plans_dir=""))


def test_ten_repeatable_decoded_selections_and_rejections(backend):
    validators = load_validators()
    with TestClient(backend) as http:
        session = http.post("/api/v1/input/sessions", json={"source": "synthetic", "adapter": {"name": "test", "version": "1", "device": "synthetic"}}).json()
        headers = {"X-Input-Token": session["token"]}
        operator = http.post("/api/v1/input/sessions", json={"source": "mouse", "adapter": {"name": "test operator"}}).json()
        clock = Clock()
        gate = SelectionGate(clock=clock)
        for trial in range(10):
            expected = "399" if trial % 2 == 0 else "499"
            context = http.get("/api/v1/input/context", headers=headers).json()
            gate.configure(context, context["allowed_targets"], (10, 15))
            adapter = SyntheticAdapter(clock)
            adapter.start({"frequency_hz": 10 if expected == "399" else 15, "seed": trial})
            intent = None
            for n in range(60):
                clock.advance()
                gate.stimulus(stimulus(gate, n))
                if n % 5 == 0:
                    beat = gate.heartbeat()
                    validators["input_heartbeat"].validate(beat)
                    gate.context_update(http.post(f"/api/v1/input/sessions/{session['input_session_id']}/heartbeat", headers=headers, json=beat).json())
                intent = gate.feed(adapter.read_batch())
                if intent: break
            adapter.stop()
            assert intent is not None and intent["target_id"] == f"planet.{expected}"
            validators["selection_intent"].validate(intent)
            result = http.post("/api/v1/input/intents", headers=headers, json=intent).json()
            assert result["accepted"], result
            # Exact retry applies once; mutation under the same event ID is a conflict.
            assert http.post("/api/v1/input/intents", headers=headers, json=intent).json() == result
            conflict = {**intent, "target_id": "planet.499" if expected == "399" else "planet.399"}
            assert http.post("/api/v1/input/intents", headers=headers, json=conflict).json()["reason"] == "duplicate_event_conflict"
            stale = {**intent, "event_id": str(uuid.uuid4())}
            assert http.post("/api/v1/input/intents", headers=headers, json=stale).json()["reason"] == "stale_context"
            current = http.get("/api/v1/input/context", headers=headers).json()
            assert current["selected_body_id"] == expected and current["screen"] == "planet_info"
            card = http.get(f"/api/v1/planets/{expected}/info").json()
            assert card["body_id"] == expected
            validators["planet_info"].validate(card)
            # Assisted rearm: ordinary operator back, explicitly not claimed as EEG.
            back = dict(schema_version=1, event_id=str(uuid.uuid4()), input_session_id=operator["input_session_id"],
                        context_id=current["context_id"], context_revision=current["revision"], source="mouse", target_id="navigation.back")
            assert http.post("/api/v1/input/intents", headers={"X-Input-Token": operator["token"]}, json=back).json()["accepted"]
        # No plan created or mission command available through extension credentials.
        plan = http.get("/api/v1/plans").json()["plans"][0]["plan_id"]
        assert http.post("/api/v1/missions", headers={"X-Operator-Token": session["token"]}, json={"plan_id": plan}).status_code == 403
        assert backend.state.inputs.selected_body_id is None
        assert backend.state.runtime._mission is None
        assert http.delete(f"/api/v1/input/sessions/{session['input_session_id']}", headers=headers).status_code == 204
        assert http.get("/api/v1/input/context", headers=headers).status_code == 401


def test_client_register_heartbeat_delete_and_route_isolation(backend):
    async def scenario():
        core = CoreClient(transport=httpx.ASGITransport(app=backend))
        context = await core.register(DeviceInfo())
        gate = SelectionGate()
        gate.context_update(context)
        assert (await core.heartbeat(gate.heartbeat()))["revision"] == context["revision"]
        assert (await core.context())["input_session_id"] == context["input_session_id"]
        with pytest.raises(ValueError): await core._request("POST", "/api/v1/missions")
        await core.close()
        assert core.session is None
    asyncio.run(scenario())


def test_core_operates_with_brain_disabled():
    backend = create_app(Settings(brain_enabled=False, db_path=":memory:", plans_dir=""))
    with TestClient(backend) as http:
        assert http.get("/api/v1/health").status_code == 200
        assert http.get("/api/v1/planets/399/info").status_code == 200
        assert http.post("/api/v1/input/sessions", json={"source": "synthetic", "adapter": {"name": "test"}}).status_code == 403
        assert http.post("/api/v1/input/sessions", json={"source": "mouse", "adapter": {"name": "test"}}).status_code == 201


def test_mouse_action_invalidates_pending_decision(backend):
    from test_selection import setup, run
    with TestClient(backend) as http:
        registration = {"source": "synthetic", "adapter": {"name": "test"}}
        session = http.post("/api/v1/input/sessions", json=registration).json()
        headers = {"X-Input-Token": session["token"]}
        clock, adapter, gate = setup()
        gate.configure(session["context"], ["planet.399", "planet.499"], (10, 15))
        beat = {"context_id": gate.context["context_id"], "context_revision": gate.context["revision"],
                "source_state": "ready", "acquisition_age_ms": 0, "stimulus_ready": True}
        http.post(f"/api/v1/input/sessions/{session['input_session_id']}/heartbeat", headers=headers, json=beat)
        intent = run(clock, adapter, gate)[0]
        mouse = http.post("/api/v1/input/sessions", json={**registration, "source": "mouse"}).json()
        ordinary = copy.deepcopy(intent)
        ordinary.update(source="mouse", input_session_id=mouse["input_session_id"], event_id=str(uuid.uuid4()))
        assert http.post("/api/v1/input/intents", headers={"X-Input-Token": mouse["token"]}, json=ordinary).json()["accepted"]
        assert http.post("/api/v1/input/intents", headers=headers, json=intent).json()["reason"] == "stale_context"
