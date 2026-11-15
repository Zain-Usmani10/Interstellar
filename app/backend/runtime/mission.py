"""Mission runtime: the single owner of the transport.

One worker thread owns the Transport and the Link. Everything that touches the controller
goes through its bounded job queue, so there is exactly one serial owner and one mutation at
a time. Between jobs the worker reads telemetry and publishes MissionSnapshots.

The snapshot only ever reflects what the controller reported. If telemetry stops, the last
state is kept and marked stale; nothing is advanced on the backend's own clock.

Shuttle / CCS storyline (plan section 18): the worker sends a GET_STATUS keep-alive, and an
operator can start a blackout. During a blackout nothing is sent, received frames are
discarded, and the snapshot carries a separate, labelled `estimate` next to the last received
values. When contact returns the first STATUS replaces the estimate and a `reconciliation`
record says what happened out of contact.
"""
from __future__ import annotations

import dataclasses
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
from app.backend.ephemeris.timeconv import jd_tdb_to_utc

from .physics_view import reconstruct
from .stores import MissionDb, PlanStore

T = p.MsgType
STALE_AFTER_S = 1.0
KEEPALIVE_S = 0.5            # the board calls the link lost after 2 s without a valid frame
ESTIMATE_PUBLISH_S = 0.1     # how often the estimate is republished during a blackout
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
        self._delay_physical_s: float | None = None   # last geometric Earth-spacecraft light time
        self._delayed = hasattr(transport, "max_delay_s")   # True when wrapped in a DelayTransport
        if self._delayed:
            transport.delay_s = self._demo_delay        # read each time a frame enters the delay queue
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
        self._blackout: dict | None = None         # {status, at}: last telemetry when contact was cut
        self._reconcile: dict | None = None        # set when a blackout ends, used by the next STATUS
        self._reconciliation: dict | None = None   # last 'while out of contact' report
        self._last_keepalive = 0.0
        self._last_estimate = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="transport-worker", daemon=True)

    def _demo_delay(self) -> float:
        """One-way demo delay: physical light time compressed 300x, clamped to 0.1..3.0 s."""
        return min(3.0, max(0.1, (self._delay_physical_s or 0.0) / 300.0))

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
                         "trip_days": p.trip_days_from_tof(plan["tof_s"]), "trip_days_set": True,
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
                    self._keepalive()
                except TransportError as err:
                    self._link_error = str(err)
                    time.sleep(0.2)
                self._tick_blackout()
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

    def _keepalive(self) -> None:
        """GET_STATUS every 0.5 s so the shuttle knows the CCS is there. Silent during a blackout."""
        now = time.monotonic()
        if self._blackout is not None or now - self._last_keepalive < KEEPALIVE_S or not self.transport.is_open():
            return
        self._last_keepalive = now
        self.transport.send(p.encode_frame(T.GET_STATUS, 0, self.link.session_id))

    def _on_status(self, board_session: int, status: p.Status) -> None:
        """Called on the worker thread for every STATUS frame."""
        with self._lock:
            if self._blackout is not None:
                return                             # out of contact: received frames are discarded
            if self._reconcile is not None:
                self._reconciliation = self._reconcile_with(status)
                self._reconcile = None
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

    # ------------------------------------------------------------ blackout, estimate, sync

    def _estimate(self) -> tuple[p.Status, list[str]]:
        """Dead reckoning from the last telemetry: what the shuttle is expected to be doing now.

        Ticks are assumed to run at 100 Hz since the last STATUS. Burns that the plan schedules
        before the estimated tick are listed as expected, never as done. Caller holds the lock.
        """
        last: p.Status = self._blackout["status"]
        ticks, wire = self._mission["plan"]["ticks"], self._mission["plan"]["wire"]
        tick = min(ticks["end_tick"], last.tick + int((time.monotonic() - self._blackout["at"]) * p.TICK_HZ))
        est, expected = last, []
        if last.state == p.State.RUNNING:
            if not est.executed_mask & p.MASK_DEPARTURE and tick >= ticks["departure_tick"]:
                expected.append("departure")
                est = dataclasses.replace(est, executed_mask=est.executed_mask | p.MASK_DEPARTURE,
                                          fuel_remaining_g=est.fuel_remaining_g - wire["departure_fuel_g"],
                                          departure_executed_tick=ticks["departure_tick"])
            if est.executed_mask == p.MASK_DEPARTURE and tick >= ticks["arrival_tick"]:
                expected.append("capture")
                tick = ticks["arrival_tick"]              # the board stops its clock at capture
                est = dataclasses.replace(est, executed_mask=est.executed_mask | p.MASK_CAPTURE,
                                          fuel_remaining_g=est.fuel_remaining_g - wire["capture_fuel_g"],
                                          capture_executed_tick=tick, state=p.State.COMPLETE)
        return dataclasses.replace(est, tick=tick), expected

    def _estimate_block(self) -> dict:
        """The `estimate` object of the snapshot. Caller holds the lock."""
        est, expected = self._estimate()
        mission = self._mission
        view = reconstruct(mission["plan"], est)
        phase = view["spacecraft"]["phase"]
        ticks = mission["plan"]["ticks"]
        return {"tick": est.tick, "epoch_jd_tdb": view["epoch_jd_tdb"], "date_utc": jd_tdb_to_utc(view["epoch_jd_tdb"]),
                "days_to_arrival": (p.days_to_arrival(est.tick, ticks["departure_tick"], ticks["arrival_tick"],
                                                      mission["trip_days"]) if mission.get("trip_days_set") else None),
                "spacecraft": {"phase": "capture_expected" if phase == "captured" else phase,
                               "r_km": view["spacecraft"]["r_km"]},
                "fuel_remaining_g": est.fuel_remaining_g, "expected_events": expected}

    def _tick_blackout(self) -> None:
        """Worker thread: republish the moving estimate, and restore contact at the planned arrival."""
        with self._lock:
            if self._blackout is None or self._mission is None:
                return
            est, _ = self._estimate()
            arrived = est.tick >= self._mission["plan"]["ticks"]["arrival_tick"]
            due = time.monotonic() - self._last_estimate >= ESTIMATE_PUBLISH_S
        if arrived:
            self._end_blackout()
        elif due:
            self._last_estimate = time.monotonic()
            self._publish()

    def _end_blackout(self) -> None:
        with self._lock:
            if self._blackout is None:
                return
            est, expected = self._estimate()
            self._reconcile = {"start": self._blackout["status"], "estimate": est, "expected": expected}
            self._blackout = None
            self._last_keepalive = 0.0                 # ask for a STATUS straight away
        self.hub.publish("transport", {"transport_state": "reacquiring", "detail": "blackout ended; waiting for telemetry"})
        self._publish()

    def _reconcile_with(self, truth: p.Status) -> dict:
        """Compare the first STATUS after a blackout with the estimate. Caller holds the lock."""
        start, est = self._reconcile["start"], self._reconcile["estimate"]
        events = []
        for bit, name, tick in ((p.MASK_DEPARTURE, "departure", truth.departure_executed_tick),
                                (p.MASK_CAPTURE, "capture", truth.capture_executed_tick)):
            if truth.executed_mask & bit and not start.executed_mask & bit:
                events.append({"event": f"{name}_burn", "tick": tick})
        if truth.state != start.state:
            events.append({"event": "state_change", "from": p.State(start.state).name,
                           "to": p.State(truth.state).name})
        if truth.masked_fault_count > start.masked_fault_count:
            events.append({"event": "masked_fault", "count": truth.masked_fault_count - start.masked_fault_count})
        if truth.no_majority_count > start.no_majority_count:
            events.append({"event": "no_majority", "count": truth.no_majority_count - start.no_majority_count})
        differences = []
        if truth.state != est.state:
            differences.append(f"Estimate: {p.State(est.state).name}. Actual: {p.State(truth.state).name}.")
        for bit, name in ((p.MASK_DEPARTURE, "departure"), (p.MASK_CAPTURE, "capture")):
            if bool(est.executed_mask & bit) != bool(truth.executed_mask & bit):
                differences.append(f"Estimate expected the {name} burn; it did not happen." if est.executed_mask & bit
                                   else f"The {name} burn happened; the estimate did not expect it yet.")
        if truth.fuel_remaining_g != est.fuel_remaining_g:
            differences.append(f"Fuel: estimate {est.fuel_remaining_g} g, actual {truth.fuel_remaining_g} g.")
        return {"blackout_start_tick": start.tick, "blackout_end_tick": truth.tick,
                "events_during_blackout": events, "estimate_matched": not differences, "differences": differences}

    def _blackout_command(self, mission_uuid: str, name: str) -> dict:
        with self._lock:
            status, mission = self._status, self._mission
            if name == "blackout_start":
                if self._blackout is not None:
                    raise ValueError("a blackout is already active")
                ours = (status is not None and not self._lost and mission.get("uploaded")
                        and status.mission_id == mission["wire_mission"])
                if not ours or status.state != p.State.RUNNING or self._status_at is None:
                    raise ValueError("a blackout can start only while the mission is RUNNING")
                self._blackout = {"status": status, "at": self._status_at}
                self._reconcile = self._reconciliation = None
            elif self._blackout is None:
                raise ValueError("no blackout is active")
        if name == "blackout_end":
            self._end_blackout()
        self._publish()
        return {"command": name, "applied": True, "detail": "OK", "snapshot": self.snapshot(mission_uuid)}

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
                     # Applied only when the transport is wrapped in a DelayTransport (LINK_DELAY_DEMO).
                     "delay_demo_s": self._demo_delay() if self._delayed else None,
                     "delay_physical_s": None, "blackout": self._blackout is not None},
            "trip": {"trip_days": mission["trip_days"] if mission.get("trip_days_set") else None,
                     "days_to_arrival": None},
            "estimate": None, "reconciliation": self._reconciliation, "date_utc": None,
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
        self._delay_physical_s = snapshot["link"]["delay_physical_s"] = view.pop("delay_physical_s")
        if self._delayed:
            snapshot["link"]["delay_demo_s"] = self._demo_delay()
        failure = view.pop("failure")
        snapshot.update(view)
        snapshot["failure"] = snapshot["failure"] or failure
        snapshot["date_utc"] = jd_tdb_to_utc(snapshot["epoch_jd_tdb"])
        ticks = plan["ticks"]
        if mission.get("trip_days_set"):
            snapshot["trip"]["days_to_arrival"] = p.days_to_arrival(
                status.tick, ticks["departure_tick"], ticks["arrival_tick"], mission["trip_days"])
        if self._blackout is not None:
            # Top-level fields stay at the last received values; only `estimate` moves.
            snapshot["estimate"] = self._estimate_block()
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
            self._blackout = self._reconcile = self._reconciliation = None
            self._mission = {"uuid": str(uuid.uuid4()), "plan": plan, "wire": wire,
                             "trip_days": p.trip_days_from_tof(plan["tof_s"]), "trip_days_set": False,
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
        if name in ("blackout_start", "blackout_end"):
            return self._blackout_command(mission_uuid, name)
        if self._blackout is not None:
            raise ValueError("no contact: a blackout is active; commands cannot reach the shuttle")
        if "wire" not in mission and name == "upload":
            raise ValueError("this mission was restored after a restart; it cannot be uploaded again")
        job = (lambda: self._upload(mission)) if name == "upload" else (lambda: self._simple(mission, name))
        try:
            # Worst case: upload = status + open + load + commit + trip days, each up to `attempts` timeouts.
            budget = 5 * self.link.attempts * self.link.retry_timeout_s + 5
            applied, detail = self._submit(job).result(timeout=budget)
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
        """OPEN_SESSION if the board has no session of ours, then LOAD_PLAN, COMMIT_PLAN, SET_TRIP_DAYS."""
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
            # Display only: lets the shuttle count down days to arrival (plan section 18.3).
            # A controller build without this message discards it: the plan is still loaded, only
            # the shuttle's days display stays unset.
            try:
                days = self.link.mutate(T.SET_TRIP_DAYS, p.pack_trip_days(wire.mission_id, mission["trip_days"]))
                mission["trip_days_set"] = days.result == p.Result.APPLIED
            except LinkError:
                mission["trip_days_set"] = False
        return ack.result == p.Result.APPLIED, p.Detail(ack.detail).name

    def _simple(self, mission: dict, name: str) -> tuple[bool, str]:
        ack = self.link.mutate(COMMANDS[name], p.pack_u32(mission["wire_mission"]))
        if name == "clear" and ack.result == p.Result.APPLIED:
            mission["cleared"] = True
            mission["uploaded"] = False
        return ack.result == p.Result.APPLIED, p.Detail(ack.detail).name

    def inject_fault(self, kind: str) -> None:
        """Simulator only. The real board is faulted with its physical switches."""
        inner = getattr(self.transport, "inner", self.transport)   # look through a DelayTransport
        controller = getattr(inner, "controller", None)
        if self.transport.controller_source != "simulator" or controller is None:
            raise PermissionError("fault injection over the API exists only for the simulated controller")
        controller.inject_single() if kind == "single" else controller.inject_divergence()
