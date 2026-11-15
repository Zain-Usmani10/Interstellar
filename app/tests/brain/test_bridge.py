import asyncio
import json
import time

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.backend.api.app import create_app
from app.backend.runtime.stores import Settings
from app.brain.client import CoreClient
from app.brain import service


def test_loopback_bridge_origin_auth_and_decoded_ack(monkeypatch):
    backend = create_app(Settings(brain_enabled=True, db_path=":memory:", plans_dir=""))

    class InProcessCore(CoreClient):
        def __init__(self, _):
            super().__init__(transport=httpx.ASGITransport(app=backend))

        async def events(self):
            # EventHub is the actual backend stream; ASGITransport covers HTTP only.
            queue, _ = backend.state.hub.subscribe()
            try:
                while True:
                    yield await queue.get()
            finally:
                backend.state.hub.unsubscribe(queue)

    monkeypatch.setattr(service, "CoreClient", InProcessCore)

    async def scenario():
        origin = "http://localhost:5173"
        bridge = service.Bridge("http://127.0.0.1:8000", "test-only-token", origin)
        async with serve(bridge.connection, "127.0.0.1", 0, origins=[origin], max_size=8192) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            with pytest.raises(InvalidStatus):
                async with connect(url, origin="https://untrusted.invalid", proxy=None): pass
            async with connect(url, origin=origin, proxy=None) as ws:
                await ws.send(json.dumps({"token": "wrong"}))
                with pytest.raises(ConnectionClosed): await ws.recv()
            await asyncio.sleep(0.05)
            async with connect(url, origin=origin, proxy=None) as ws:
                await ws.send(json.dumps({"token": "test-only-token"}))
                status = json.loads(await ws.recv())
                assert status["source"] == "synthetic"
                context = status["context"]
                await ws.send(json.dumps({"type": "configure", "schema_version": 1,
                    "input_session_id": context["input_session_id"], "context_id": context["context_id"],
                    "context_revision": context["revision"], "targets": context["allowed_targets"],
                    "frequencies_hz": [10, 15], "synthetic_frequency_hz": 15}))

                async def frames():
                    for n in range(80):
                        await ws.send(json.dumps({"type": "stimulus_state", "schema_version": 1,
                            "context_id": context["context_id"], "context_revision": context["revision"],
                            "sequence": n, "active": True, "visible": True, "focused": True,
                            "frame_count": n*6+1, "dropped_frames": 0, "largest_frame_gap_ms": 17,
                            "effective_frequencies_hz": [10, 15]}))
                        await asyncio.sleep(0.1)
                sender = asyncio.create_task(frames())
                async def receive_decision():
                    async for raw in ws:
                        message = json.loads(raw)
                        if message["type"] == "decision_result":
                            assert message["result"]["accepted"], message
                            assert backend.state.inputs.selected_body_id == "499"
                            return
                    raise AssertionError("bridge closed before a core decision")

                try:
                    await asyncio.wait_for(receive_decision(), timeout=8)
                finally:
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
            await asyncio.sleep(0.1)
            assert not bridge.connected
            assert not backend.state.inputs._sessions
    asyncio.run(scenario())


def test_schema_rejects_mission_targets_and_unknown_fields():
    configure = {"type": "configure", "schema_version": 1, "input_session_id": "test",
                 "context_id": "test", "context_revision": 0,
                 "targets": ["planet.399", "mission.request_start"], "frequencies_hz": [10, 15],
                 "synthetic_frequency_hz": 10}
    assert not service.VALIDATOR.is_valid(configure)
    assert not service.VALIDATOR.is_valid({"type": "stop", "schema_version": 1, "token": "unexpected"})
