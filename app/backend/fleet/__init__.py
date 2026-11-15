"""Single-runtime fleet bookkeeping. Only reconciled board evidence moves ships.

No API, serial access, timers, or estimates are accepted here. The runtime must
validate STATUS session/mission correlation before calling confirm_status().
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

BODY_IDS = {str(i) for i in range(199, 900, 100)}
CLASSES = {"standard", "long_range"}
INITIAL_FLEET = Path(__file__).with_name("initial_fleet.json")


class FleetError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class FleetStore:
    """One instance per backend process, one backend process per file.

    Mutations atomically replace a JSON snapshot before changing memory. A
    failed write leaves both the previous file and the in-memory state intact.
    Missing files initialize the fleet; corrupt files fail closed, never reset.
    """

    def __init__(self, path: str | Path, initial_path: str | Path = INITIAL_FLEET):
        self.path = Path(path)
        self.initial_path = Path(initial_path)
        self._lock = RLock()
        if self.path.exists():
            self._state = json.loads(self.path.read_text(encoding="utf-8"))
            self._validate(self._state)
        else:
            self._commit(self._initial())

    def _initial(self) -> dict:
        ships = json.loads(self.initial_path.read_text(encoding="utf-8"))
        return {"version": 1, "active_mission_id": None, "missions": {},
                "shuttles": [{"id": s["id"], "name": s["name"], "class": s["class"],
                              "location": {"kind": "docked", "body_id": s["body_id"]}}
                             for s in ships]}

    @staticmethod
    def _validate(data: dict) -> None:
        def require(condition: bool) -> None:
            if not condition:
                raise FleetError("INVALID_FLEET_STATE")

        try:
            require(data["version"] == 1)
            ships = data["shuttles"]
            require(isinstance(ships, list) and ships)
            ids = set()
            for s in ships:
                require(isinstance(s["id"], str) and s["id"] and s["id"] not in ids)
                ids.add(s["id"])
                require(isinstance(s["name"], str) and s["name"] and s["class"] in CLASSES)
                loc = s["location"]
                if loc["kind"] == "docked":
                    require(set(loc) == {"kind", "body_id"} and loc["body_id"] in BODY_IDS)
                else:
                    require(loc["kind"] in {"in_flight", "lost"})
                    require(set(loc) == {"kind", "mission_id"})
                    require(loc["mission_id"] in data["missions"])
                    require(data["missions"][loc["mission_id"]]["shuttle_id"] == s["id"])
            active = []
            for mid, m in data["missions"].items():
                require(isinstance(mid, str) and mid and m["shuttle_id"] in ids)
                require(m["origin_body_id"] in BODY_IDS and m["destination_body_id"] in BODY_IDS)
                require(m["origin_body_id"] != m["destination_body_id"])
                require(type(m["departed"]) is bool and type(m["finished"]) is bool)
                if not m["finished"]:
                    active.append(mid)
            require(active == ([] if data["active_mission_id"] is None else [data["active_mission_id"]]))
        except (AssertionError, KeyError, TypeError, AttributeError) as exc:
            raise FleetError("INVALID_FLEET_STATE") from exc

    def _commit(self, state: dict) -> None:
        self._validate(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=self.path.name + ".", suffix=".tmp", delete=False) as f:
                temporary = f.name
                json.dump(state, f, indent=2, allow_nan=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
            self._state = state
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def bind_mission(self, mission_id: str, shuttle_id: str, origin_body_id: str,
                     destination_body_id: str, vehicle_class: str) -> dict:
        """Reserve a docked ship at mission creation; reservation does not move it."""
        with self._lock:
            if not isinstance(mission_id, str) or not mission_id:
                raise FleetError("INVALID_MISSION_ID")
            if mission_id in self._state["missions"]:
                raise FleetError("MISSION_ALREADY_BOUND")
            if self._state["active_mission_id"] is not None:
                raise FleetError("MISSION_ACTIVE")
            if destination_body_id not in BODY_IDS or destination_body_id == origin_body_id:
                raise FleetError("INVALID_DESTINATION")
            ship = next((s for s in self._state["shuttles"] if s["id"] == shuttle_id), None)
            if (ship is None or ship["class"] != vehicle_class or
                    ship["location"] != {"kind": "docked", "body_id": origin_body_id}):
                raise FleetError("NO_SHUTTLE_DOCKED")
            state = self.snapshot()
            state["missions"][mission_id] = {"shuttle_id": shuttle_id, "origin_body_id": origin_body_id,
                "destination_body_id": destination_body_id, "departed": False, "finished": False}
            state["active_mission_id"] = mission_id
            self._commit(state)
            return self.snapshot()

    def confirm_status(self, mission_id: str, state: str, executed_mask: int) -> dict:
        """Apply a correlated, confirmed STATUS (never an estimated snapshot).

        Repeated terminal evidence is a no-op. Departure evidence is sticky:
        later zero masks cannot send a departed ship back to its origin.
        COMPLETE requires both burns. SAFE before departure keeps the binding
        until an explicit abort/clear, permitting the runtime to reconcile it.
        """
        if state not in {"LOADED", "ARMED", "RUNNING", "SAFE", "COMPLETE", "ABORTED"}:
            raise FleetError("INVALID_BOARD_STATE")
        if type(executed_mask) is not int or executed_mask not in (0, 1, 3):
            raise FleetError("INVALID_EXECUTED_MASK")
        if state == "COMPLETE" and executed_mask != 3:
            raise FleetError("CAPTURE_NOT_CONFIRMED")
        with self._lock:
            data = self.snapshot()
            if mission_id not in data["missions"]:
                raise FleetError("UNKNOWN_MISSION")
            mission = data["missions"][mission_id]
            if mission["finished"]:
                return data
            ship = next(s for s in data["shuttles"] if s["id"] == mission["shuttle_id"])
            mission["departed"] |= bool(executed_mask & 1)
            if mission["departed"]:
                ship["location"] = {"kind": "in_flight", "mission_id": mission_id}
            if state == "COMPLETE":
                ship["location"] = {"kind": "docked", "body_id": mission["destination_body_id"]}
                mission["finished"] = True
            elif state in {"SAFE", "ABORTED"} and mission["departed"]:
                ship["location"] = {"kind": "lost", "mission_id": mission_id}
                mission["finished"] = True
            elif state == "ABORTED":
                mission["finished"] = True
            if mission["finished"]:
                data["active_mission_id"] = None
            self._commit(data)
            return self.snapshot()

    def confirm_clear(self, mission_id: str) -> dict:
        """Call only after a confirmed CLEAR, retaining prior departure evidence.

        After departure CLEAR cannot recover a ship: it remains lost. Before
        departure it releases the reservation and leaves the ship docked.
        """
        return self.confirm_status(mission_id, "ABORTED", 0)

    def reset(self) -> dict:
        """Explicit operator reset, never automatic recovery from corrupt data.

        Caller must first stop/clear the controller and serialize mission actions.
        """
        with self._lock:
            self._commit(self._initial())
            return self.snapshot()
