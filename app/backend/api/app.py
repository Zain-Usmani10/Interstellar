"""FastAPI application: HTTP routes and the WebSocket event stream (see app/contracts/api_v1.md).

Run:  python -m app.backend.api          (one process, no reload, no extra workers:
                                          this process is the only owner of the serial port)
"""
from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.backend.runtime.events import EventHub
from app.backend.runtime.inputs import InputError, InputManager
from app.backend.runtime.jobs import JobManager, PlannerUnavailable
from app.backend.runtime.mission import MissionBusy, MissionRuntime
from app.backend.runtime.sim_controller import SimulatedController, SimulatorTransport
from app.backend.runtime.stores import (APP_DIR, CONTRACTS_VERSION, PLANET_IDS, MissionDb, PlanStore,
                                        Settings, fixture, load_validators, planet_info)
from app.contracts.transport import Transport


class AdapterInfo(BaseModel):
    name: str = Field(max_length=80)
    version: str = Field(default="", max_length=40)
    device: str = Field(default="", max_length=120)


class InputSessionRequest(BaseModel):
    source: Literal["mouse", "keyboard", "live_eeg", "replay", "synthetic"]
    adapter: AdapterInfo


class MissionRequest(BaseModel):
    plan_id: str


class CommandRequest(BaseModel):
    command: Literal["upload", "arm", "start", "abort", "clear", "blackout_start", "blackout_end"]


class FaultRequest(BaseModel):
    kind: Literal["single", "divergence"]


class PlanningRequest(BaseModel):
    departure_start_utc: str
    departure_end_utc: str
    tof_min_days: float = Field(gt=0, le=1000)
    tof_max_days: float = Field(gt=0, le=1000)
    n_departures: int = Field(ge=1, le=25)
    n_durations: int = Field(ge=1, le=25)
    vehicle: dict | None = None


def make_transport(settings: Settings) -> Transport:
    inner = _make_inner_transport(settings)
    if not settings.link_delay_demo:
        return inner
    # The one artificial-delay layer (plan section 10). The runtime sets the delay from the geometry.
    from app.backend.transport import DelayTransport
    return DelayTransport(inner)


def _make_inner_transport(settings: Settings) -> Transport:
    if settings.transport_mode == "simulator":
        return SimulatorTransport(SimulatedController(speed=settings.sim_speed))
    if settings.transport_mode == "fpga":
        if not settings.serial_port:
            raise RuntimeError("TRANSPORT_MODE=fpga needs SERIAL_PORT (e.g. COM5) in .env")
        try:
            # Owned by @ANaceri26/codex: returns an object implementing app.contracts.transport.Transport.
            from app.backend.transport import create_transport   # type: ignore[import-not-found]
        except ImportError as err:
            raise RuntimeError("serial transport (app/backend/transport) is not available yet; "
                               "use TRANSPORT_MODE=simulator") from err
        return create_transport(port=settings.serial_port, baud=settings.serial_baud)
    raise RuntimeError(f"unknown TRANSPORT_MODE {settings.transport_mode!r}; use simulator or fpga")


def create_app(settings: Settings | None = None, transport: Transport | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    validators = load_validators()
    hub = EventHub()
    plans = PlanStore(validators, settings.plans_dir)
    inputs = InputManager(hub, validators, settings.brain_enabled)
    runtime = MissionRuntime(transport or make_transport(settings), plans, hub, MissionDb(settings.db_path),
                             on_state_change=lambda: inputs.bump("mission_state"))
    jobs = JobManager(plans, hub)
    operator_token = secrets.token_urlsafe(24)
    origins = {settings.frontend_dev_origin, f"http://{settings.host}:{settings.port}",
               f"http://localhost:{settings.port}", *settings.extra_origins}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runtime.start()
        try:
            yield
        finally:
            jobs.shutdown()
            runtime.stop()

    app = FastAPI(title="Interstellar backend", version=CONTRACTS_VERSION, lifespan=lifespan)
    app.state.operator_token = operator_token
    app.state.runtime, app.state.inputs, app.state.hub = runtime, inputs, hub
    app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def check_origin(request: Request, call_next):
        # Browsers send Origin on cross-site requests; refuse any site that is not our own UI.
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(InputError)
    async def input_error(_: Request, err: InputError):
        return JSONResponse({"error": err.code}, status_code=err.status)

    def require_operator(token: str | None) -> None:
        if not token or not secrets.compare_digest(token, operator_token):
            # An input-session token is recognised and refused: it can never command a mission.
            code = "input_token_not_allowed" if inputs.owns_token(token) else "operator_token_required"
            raise HTTPException(403 if code == "input_token_not_allowed" else 401, code)

    def data_mode() -> str:
        modes = plans.data_modes()
        return modes[0] if len(modes) == 1 else "mixed"

    # ------------------------------------------------------------ general

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "contracts_version": CONTRACTS_VERSION,
                "transport": runtime.transport_info(), "brain_enabled": settings.brain_enabled,
                "data_mode": data_mode(), "planner_available": jobs.available(),
                "rejected_plans": plans.rejected}

    @app.get("/api/v1/session")
    def session():
        """Operator token for our own browser UI (origin already checked by the middleware)."""
        return {"operator_token": operator_token}

    # ------------------------------------------------------------ planets and plans

    @app.get("/api/v1/planets")
    def planets():
        return fixture("planets")

    @app.get("/api/v1/planets/{body_id}/info")
    async def planet(body_id: str, scene_epoch_jd_tdb: float | None = None):
        if body_id not in PLANET_IDS:
            raise HTTPException(404, "unsupported_body")
        # The adapter may fetch from NASA; keep that off the event loop.
        return await asyncio.to_thread(planet_info, body_id, scene_epoch_jd_tdb, validators)

    @app.get("/api/v1/plans")
    def list_plans():
        return {"plans": plans.summaries()}

    @app.get("/api/v1/plans/{plan_id}")
    def get_plan(plan_id: str):
        plan = plans.get(plan_id)
        if plan is None:
            raise HTTPException(404, "unknown_plan")
        return plan

    @app.post("/api/v1/planning/jobs", status_code=202)
    def create_job(body: PlanningRequest, x_operator_token: str | None = Header(default=None)):
        require_operator(x_operator_token)
        if body.tof_min_days > body.tof_max_days:
            raise HTTPException(422, "tof_min_days must not exceed tof_max_days")
        try:
            return jobs.submit(body.model_dump())
        except PlannerUnavailable:
            raise HTTPException(503, "PLANNER_UNAVAILABLE") from None
        except OverflowError:
            raise HTTPException(429, "planning_queue_full") from None

    @app.get("/api/v1/planning/jobs/{job_id}")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "unknown_job")
        return job

    @app.delete("/api/v1/planning/jobs/{job_id}")
    def cancel_job(job_id: str, x_operator_token: str | None = Header(default=None)):
        require_operator(x_operator_token)
        job = jobs.cancel(job_id)
        if job is None:
            raise HTTPException(404, "unknown_job")
        return job

    # ------------------------------------------------------------ missions (operator only)

    @app.post("/api/v1/missions", status_code=201)
    def create_mission(body: MissionRequest, x_operator_token: str | None = Header(default=None)):
        require_operator(x_operator_token)
        try:
            return runtime.create_mission(body.plan_id)
        except KeyError:
            raise HTTPException(404, "unknown_plan") from None
        except MissionBusy as err:
            raise HTTPException(409, str(err)) from None
        except ValueError as err:
            raise HTTPException(422, str(err)) from None

    @app.get("/api/v1/missions/{mission_id}")
    def get_mission(mission_id: str):
        snapshot = runtime.snapshot(mission_id)
        if snapshot is None:
            raise HTTPException(404, "unknown_mission")
        return snapshot

    @app.post("/api/v1/missions/{mission_id}/commands")
    async def mission_command(mission_id: str, body: CommandRequest,
                              x_operator_token: str | None = Header(default=None)):
        require_operator(x_operator_token)
        try:
            # Waits for the controller's ACK on a worker thread; the event loop stays free.
            return await asyncio.to_thread(runtime.command, mission_id, body.command)
        except KeyError:
            raise HTTPException(404, "unknown_mission") from None
        except MissionBusy as err:
            raise HTTPException(429, str(err)) from None
        except ValueError as err:
            raise HTTPException(409, str(err)) from None

    @app.post("/api/v1/sim/faults")
    def sim_fault(body: FaultRequest, x_operator_token: str | None = Header(default=None)):
        require_operator(x_operator_token)
        try:
            runtime.inject_fault(body.kind)
        except PermissionError as err:
            raise HTTPException(409, str(err)) from None
        return {"injected": body.kind, "controller_label": "SIMULATED CONTROLLER"}

    # ------------------------------------------------------------ input (mouse, keyboard, EEG)

    @app.post("/api/v1/input/sessions", status_code=201)
    def input_register(body: InputSessionRequest):
        return inputs.register(body.source, body.adapter.model_dump())

    @app.post("/api/v1/input/sessions/{session_id}/heartbeat")
    async def input_heartbeat(session_id: str, request: Request, x_input_token: str | None = Header(default=None)):
        return inputs.heartbeat(inputs.authenticate(session_id, x_input_token), await request.json())

    @app.delete("/api/v1/input/sessions/{session_id}", status_code=204)
    def input_delete(session_id: str, x_input_token: str | None = Header(default=None)):
        inputs.authenticate(session_id, x_input_token)
        inputs.delete(session_id)
        return Response(status_code=204)

    @app.get("/api/v1/input/context")
    def input_context(x_input_token: str | None = Header(default=None)):
        return inputs.context(inputs.authenticate(None, x_input_token))

    @app.post("/api/v1/input/intents")
    async def input_intent(request: Request, x_input_token: str | None = Header(default=None)):
        session = inputs.authenticate(None, x_input_token)
        try:
            intent = await request.json()
        except ValueError:
            intent = None
        result = inputs.submit(session, intent if isinstance(intent, dict) else {})
        return JSONResponse(result, status_code=422 if result["reason"] == "invalid_schema" else 200)

    # ------------------------------------------------------------ events

    @app.websocket("/api/v1/events")
    async def events(ws: WebSocket):
        origin = ws.headers.get("origin")
        if origin and origin not in origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        queue, current = hub.subscribe()
        try:
            info = runtime.transport_info()
            await ws.send_json({"type": "hello", "server_seq": hub.next_seq(), "data": {
                "contracts_version": CONTRACTS_VERSION, "controller_label": info["controller_label"],
                "data_mode": data_mode(), "selection": inputs.state()}})
            for event in current:                    # full current state before anything incremental
                await ws.send_json(event)
            while True:
                await ws.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.unsubscribe(queue)

    # Demo: serve the built browser app from this same process when it exists.
    dist = APP_DIR / "frontend" / "dist"
    if (dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=Path(dist), html=True), name="frontend")
    return app
