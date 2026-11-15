"""Mission runtime: the single owner of the transport.

One worker thread owns the Transport and the Link. Everything that touches the controller
goes through its bounded job queue, so there is exactly one serial owner and one mutation at
a time. Between jobs the worker reads telemetry and publishes MissionSnapshots.

The snapshot only ever reflects what the controller reported. If telemetry stops, the last
state is kept and marked stale; nothing is advanced on the backend's own clock.
"""
from __future__ import annotations

import queue
import secrets
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Callable

from app.contracts import protocol_v1 as p
from app.contracts.transport import Transport, TransportError

from .events import EventHub
from .link import Link, LinkError
from .physics_view import reconstruct
from .stores import MissionDb, PlanStore

T = p.MsgType
STALE_AFTER_S = 1.0
LABELS = {"fpga": "FPGA", "simulator": "SIMULATED CONTROLLER"}
COMMANDS = {"arm": T.ARM, "start": T.START, "abort": T.ABORT, "clear": T.CLEAR}


class MissionBusy(Exception):
    """Another mission still controls the board, or the job queue is full."""


class MissionRuntime:
    def __init__(self, transport: Transport, plans: PlanStore, hub: EventHub, db: MissionDb,
                 on_state_change: Callable[[], None] | None = None):
        self.transport = transport
        self.plans = plans
        self.hub = hub
        self.db = db
        self.on_state_change = on_state_change or (lambda: None)
        self.link = Link(transport, self._on_status)
        self._jobs: queue.Queue = queue.Queue(maxsize=16)
        self._lock = threading.Lock()              # protects the fields below
        self._mission: dict | None = None          # {uuid, plan, wire_mission, plan_crc16}
        self._status: p.Status | None = None
        self._board_session = 0
        self._status_at: float | None = None       # monotonic receive time of the last STATUS
        self._snapshot: dict | None = None
        self._link_error: str | None = None
        self._lost = False
        self._was_stale = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="transport-worker", daemon=True)

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        self.transport.open()
        self._resume_from_db()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3)
        self.transport.close()

    def _resume_from_db(self) -> None:
        """After a backend restart with a real board, pick the previous session back up.

        The board may have kept running. We restore our ids and sequence counter and let the
        next STATUS decide: matching session/mission resumes, anything else is reported lost.
        A simulator never survives a restart, so there is nothing to resume there.
        """
        record = self.db.latest()
        if not record or self.transport.controller_source != "fpga" or record["controller_source"] != "fpga":
            return
        plan = self.plans.get(record["plan_id"])
        if plan is None or record["last_state"] == "IDLE":
            return
        self._mission = {"uuid": record["mission_uuid"], "plan": plan, "uploaded": True,
                         "wire_mission": record["wire_mission"], "plan_crc16": record["plan_crc16"]}
        self.link.session_id, self.link.next_seq = record["wire_session"], record["next_seq"]

    # ------------------------------------------------------------ worker thread

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job, future = self._jobs.get_nowait()
            except queue.Empty:
                try:
                    self.link.pump(0.05)
                except TransportError as err:
                    self._link_error = str(err)
                    time.sleep(0.2)
                self._check_stale()
                continue
            try:
                future.set_result(job())
            except Exception as err:               # noqa: BLE001 - hand every failure to the caller
                future.set_exception(err)

    def _submit(self, job: Callable) -> Future:
        future: Future = Future()
        try:
            self._jobs.put_nowait((job, future))
        except queue.Full:
            raise MissionBusy("command queue is full") from None
        return future

    def _on_status(self, board_session: int, status: p.Status) -> None:
        """Called on the worker thread for every STATUS frame."""
        with self._lock:
            previous = self._status.state if self._status else None
            self._status, self._board_session = status, board_session
            self._status_at = time.monotonic()
            self._link_error = None
            self._was_stale = False
            mission = self._mission
            if mission and mission.get("uploaded") and (
                    board_session != self.link.session_id or status.mission_id != mission["wire_mission"]):
                self._lost = True                  # board reset/reprogrammed: our mission is gone
        self._publish()
        if previous != status.state:
            self._persist()
            if previous is not None:               # the first STATUS after startup is not a change
                self.on_state_change()

    def _check_stale(self) -> None:
        with self._lock:
            stale = self._status_at is not None and time.monotonic() - self._status_at > STALE_AFTER_S
            changed = stale and not self._was_stale
            self._was_stale = stale
        if changed:
            self._publish()
            self.hub.publish("transport", {"transport_state": "stale",
                                           "detail": "no telemetry; showing the last received state"})

    # ------------------------------------------------------------ snapshots

    def _publish(self) -> None:
        with self._lock:
            if self._mission is None:
                return
            seq = self.hub.next_seq()
            self._snapshot = self._build_snapshot(seq)
            snapshot = self._snapshot
        self.hub.publish("mission_snapshot", snapshot, seq)

    def _build_snapshot(self, seq: int) -> dict:
        mission, status = self._mission, self._status
        plan = mission["plan"]
        source = self.transport.controller_source
        age = None if self._status_at is None else int((time.monotonic() - self._status_at) * 1000)
        if self._link_error:
            transport_state = "error"
        elif age is None:
            transport_state = "unknown"
        else:
            transport_state = "stale" if age > STALE_AFTER_S * 1000 else "connected"
        snapshot = {
            "schema_version": 1, "server_seq": seq, "mission_id": mission["uuid"],
            "plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"],
            "wire": {"session_id": self.link.session_id, "mission_id": mission["wire_mission"],
                     "plan_crc16": mission["plan_crc16"]},
            "controller_source": source, "controller_label": LABELS[source],
            "state": "UNKNOWN", "tick": 0, "executed_mask": 0,
            "departure_executed_tick": None, "capture_executed_tick": None,
            "fuel_remaining_g": 0, "safe_reason": "NONE",
            "faults": {"masked_fault_count": 0, "no_majority_count": 0, "rx_error_count": 0},
            "link": {"transport_state": transport_state, "observed_age_ms": age, "view": "ground_delayed",
                     # No DelayTransport is in the chain yet, so no demo delay is applied.
                     "delay_demo_s": getattr(self.transport, "current_delay_s", None),
                     "delay_physical_s": None},
            "epoch_jd_tdb": None,
            "spacecraft": {"phase": "unknown", "r_km": None, "v_km_s": None},
            "planets": [], "outcome": "pending", "failure": None,
        }
        if self._link_error:
            snapshot["failure"] = {"code": "TRANSPORT_ERROR", "message": self._link_error}
        if status is None:
            return snapshot
        snapshot["faults"] = {"masked_fault_count": status.masked_fault_count,
                              "no_majority_count": status.no_majority_count,
                              "rx_error_count": status.rx_error_count}
        if self._lost:
            snapshot.update(state=p.State(status.state).name, outcome="lost", failure={
                "code": "CONTROLLER_LOST_MISSION",
                "message": "The controller no longer holds this session/mission (reset or reprogrammed). "
                           "Execution is lost; it is not resumed."})
            return snapshot
        ours = status.mission_id == mission["wire_mission"]
        snapshot["state"] = p.State(status.state).name
        if not ours:                                # nothing uploaded yet (or already cleared)
            return snapshot
        unset = lambda tick: None if tick == p.UNSET_TICK else tick   # noqa: E731
        snapshot.update(
            tick=status.tick, executed_mask=status.executed_mask,
            departure_executed_tick=unset(status.departure_executed_tick),
            capture_executed_tick=unset(status.capture_executed_tick),
            fuel_remaining_g=status.fuel_remaining_g,
            safe_reason=p.SafeReason(status.safe_reason).name)
        view = reconstruct(plan, status)
        snapshot["link"]["delay_physical_s"] = view.pop("delay_physical_s")
        failure = view.pop("failure")
        snapshot.update(view)
        snapshot["failure"] = snapshot["failure"] or failure
        return snapshot

    def snapshot(self, mission_uuid: str) -> dict | None:
        with self._lock:
            if self._mission is None or self._mission["uuid"] != mission_uuid:
                return None
            if self._snapshot is None:
                self._snapshot = self._build_snapshot(self.hub.next_seq())
            return self._snapshot

    def _persist(self) -> None:
        with self._lock:
            mission, status = self._mission, self._status
            if mission is None:
                return
            record = {"mission_uuid": mission["uuid"], "plan_id": mission["plan"]["plan_id"],
                      "controller_source": self.transport.controller_source,
                      "wire_session": self.link.session_id, "wire_mission": mission["wire_mission"],
                      "plan_crc16": mission["plan_crc16"], "next_seq": self.link.next_seq,
                      "last_state": p.State(status.state).name if status else "UNKNOWN"}
        self.db.save(record)

    # ------------------------------------------------------------ public operations

    def transport_info(self) -> dict:
        source = self.transport.controller_source
        return {"mode": source, "controller_label": LABELS[source],
                "open": self.transport.is_open(), "stats": self.transport.stats(),
                "link_error": self._link_error}

    def create_mission(self, plan_id: str) -> dict:
        """Bind a validated plan to the controller. Nothing is sent to the board yet."""
        plan = self.plans.get(plan_id)
        if plan is None:
            raise KeyError(plan_id)
        with self._lock:
            status = self._status
            active = (self._mission is not None and not self._lost and status is not None
                      and status.state != p.State.IDLE and self._mission.get("uploaded"))
            if active:
                raise MissionBusy("a mission is already loaded on the controller; clear it first")
            wire = p.Plan(secrets.randbelow(0xFFFFFFFF) + 1, plan["ticks"]["departure_tick"],
                          plan["ticks"]["arrival_tick"], plan["ticks"]["end_tick"],
                          plan["wire"]["initial_fuel_g"], plan["wire"]["departure_fuel_g"],
                          plan["wire"]["capture_fuel_g"])
            if wire.problem():
                raise ValueError(f"plan cannot be sent to the controller: {wire.problem()}")
            self._mission = {"uuid": str(uuid.uuid4()), "plan": plan, "wire": wire,
                             "wire_mission": wire.mission_id, "plan_crc16": wire.crc16()}
            self._lost, self._snapshot = False, None
            mission_uuid = self._mission["uuid"]
        self._persist()
        self._publish()
        return self.snapshot(mission_uuid)

    def command(self, mission_uuid: str, name: str) -> dict:
        """Run one typed command on the worker thread and wait for the controller's answer."""
        with self._lock:
            mission = self._mission
            if mission is None or mission["uuid"] != mission_uuid:
                raise KeyError(mission_uuid)
        if "wire" not in mission and name == "upload":
            raise ValueError("this mission was restored after a restart; it cannot be uploaded again")
        job = (lambda: self._upload(mission)) if name == "upload" else (lambda: self._simple(mission, name))
        try:
            applied, detail = self._submit(job).result(timeout=15)
        except (LinkError, TransportError) as err:
            # A sent command may have been applied. Say so; never assume success.
            self._link_error = f"{name}: {err}"
            self._publish()
            applied, detail = False, "NO_ACK"
        self._persist()
        self._publish()
        return {"command": name, "applied": applied, "detail": detail,
                "snapshot": self.snapshot(mission_uuid)}

    def _upload(self, mission: dict) -> tuple[bool, str]:
        """OPEN_SESSION if the board has no session of ours, then LOAD_PLAN and COMMIT_PLAN."""
        board_session, status = self.link.read_status()
        if board_session == 0 or board_session != self.link.session_id:
            if status.state != p.State.IDLE:
                return False, "BAD_STATE"          # never take over an active mission
            ack = self.link.open_session()
            if ack.result != p.Result.APPLIED:
                return False, p.Detail(ack.detail).name
        wire: p.Plan = mission["wire"]
        ack = self.link.mutate(T.LOAD_PLAN, wire.pack())
        if ack.result == p.Result.APPLIED and ack.plan_crc16 != wire.crc16():
            return False, "BAD_PLAN_CRC"           # the board staged something else
        if ack.result == p.Result.APPLIED:
            ack = self.link.mutate(T.COMMIT_PLAN, p.pack_commit(wire.mission_id, wire.crc16()))
        if ack.result == p.Result.APPLIED:
            mission["uploaded"] = True
            mission.pop("cleared", None)
        return ack.result == p.Result.APPLIED, p.Detail(ack.detail).name

    def _simple(self, mission: dict, name: str) -> tuple[bool, str]:
        ack = self.link.mutate(COMMANDS[name], p.pack_u32(mission["wire_mission"]))
        if name == "clear" and ack.result == p.Result.APPLIED:
            mission["cleared"] = True
            mission["uploaded"] = False
        return ack.result == p.Result.APPLIED, p.Detail(ack.detail).name

    def inject_fault(self, kind: str) -> None:
        """Simulator only. The real board is faulted with its physical switches."""
        controller = getattr(self.transport, "controller", None)
        if self.transport.controller_source != "simulator" or controller is None:
            raise PermissionError("fault injection over the API exists only for the simulated controller")
        controller.inject_single() if kind == "single" else controller.inject_divergence()
