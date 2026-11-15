"""Loopback synthetic demonstration bridge. Live/replay adapters are not enabled."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import secrets
import time

from jsonschema import Draft202012Validator
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .acquisition import SyntheticAdapter
from .client import CoreClient
from .selection import LABELS, SelectionGate

SCHEMA = json.loads((Path(__file__).parent / "contracts/stimulus_v1.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


class Bridge:
    def __init__(self, core_url, token, origin, clock=time.monotonic):
        self.core_url, self.token, self.origin = core_url, token, origin
        self.clock = clock
        self.token_expires = clock() + 600
        self.connected = False

    async def connection(self, ws):
        if self.connected or self.clock() >= self.token_expires:
            await ws.close(1008, "busy or launch token expired")
            return
        self.connected = True
        adapter = SyntheticAdapter()
        core = CoreClient(self.core_url)
        gate = SelectionGate()
        try:
            auth = json.loads(await asyncio.wait_for(ws.recv(), 3))
            if not isinstance(auth, dict) or not secrets.compare_digest(str(auth.get("token", "")), self.token):
                await ws.close(1008, "invalid launch token")
                return
            info = adapter.start({"frequency_hz": 10})
            gate.context_update(await core.register(info))
            await self.status(ws, gate)
            tasks = [asyncio.create_task(self.receive(ws, gate, adapter)),
                     asyncio.create_task(self.run(ws, gate, adapter, core)),
                     asyncio.create_task(self.events(ws, gate, core))]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                gate.stop("disconnected")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (ConnectionClosed, asyncio.TimeoutError):
            pass
        except Exception as error:
            # Never log tokens or raw samples; surface failure without changing source mode.
            print(f"Brain connection stopped: {type(error).__name__}", flush=True)
            await ws.close(1011, "brain connection stopped; reconnect and rearm")
        finally:
            gate.stop()
            adapter.stop()
            try:
                await core.close()
            except Exception:
                pass  # core expires unreachable session within its heartbeat timeout
            self.connected = False

    async def status(self, ws, gate):
        await ws.send(json.dumps({"type": "status", "schema_version": 1, "source": gate.source,
                                  "label": LABELS[gate.source], "state": gate.state, "reason": gate.reason,
                                  "scores": gate.scores, "context": gate.context}))

    async def receive(self, ws, gate, adapter):
        async for raw in ws:
            message = json.loads(raw)
            if not VALIDATOR.is_valid(message):
                gate.stop("invalid_message")
                await self.status(ws, gate)
                continue
            kind = message["type"]
            if kind == "stop":
                gate.stop("operator_stop")
            elif kind == "configure":
                context = gate.context
                if (message["input_session_id"] != context["input_session_id"]
                        or message["context_id"] != context["context_id"]
                        or message["context_revision"] != context["revision"]):
                    gate.stop("context_mismatch")
                else:
                    adapter.stop()
                    adapter.start({"frequency_hz": message["synthetic_frequency_hz"]})
                    gate.configure(context, message["targets"], message["frequencies_hz"])
            elif kind == "stimulus_state":
                gate.stimulus(message)
            await self.status(ws, gate)

    async def events(self, ws, gate, core):
        async for event in core.events():
            if event.get("type") in ("hello", "selection", "transport"):
                gate.stop("core_event_rearm")
                gate.context_update(await core.context())
                await self.status(ws, gate)

    async def run(self, ws, gate, adapter, core):
        next_sample = next_beat = time.monotonic()
        while True:
            now = time.monotonic()
            if now >= next_beat:
                # Fresh core context is checked before consuming more evidence.
                context = await core.heartbeat(gate.heartbeat())
                gate.context_update(context)
                next_beat = now + 0.5
            if now >= next_sample:
                # A delayed loop must never compress missing wall time into fresh samples.
                if now-next_sample > 0.25:
                    gate.stop("acquisition_stall")
                intent = gate.feed(adapter.read_batch())
                next_sample = now + adapter.size/adapter.rate
                if intent is not None:
                    result = await core.submit(intent)
                    await ws.send(json.dumps({"type": "decision_result", "schema_version": 1,
                                              "event_id": intent["event_id"], "result": result}))
                    gate.context_update(await core.context())
                await self.status(ws, gate)
            await asyncio.sleep(0.01)


async def main():
    parser = argparse.ArgumentParser(description="Synthetic EEG only; no flashing or live headset")
    parser.add_argument("--core", default="http://127.0.0.1:8000")
    parser.add_argument("--origin", default="http://localhost:5173")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    bridge = Bridge(args.core, token, args.origin)
    print(LABELS["synthetic"], flush=True)
    print(f"Loopback ws://127.0.0.1:{args.port}; origin {args.origin}", flush=True)
    print(f"Launch token (valid 10 minutes; enter in optional widget): {token}", flush=True)
    async with serve(bridge.connection, "127.0.0.1", args.port, origins=[args.origin],
                     max_size=8192, max_queue=8, ping_interval=10):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
