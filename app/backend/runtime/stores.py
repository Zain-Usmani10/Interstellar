"""Settings, the plan store, the planet-info provider and the small SQLite mission record."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

APP_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = APP_DIR.parent
CONTRACTS = APP_DIR / "contracts"
CONTRACTS_VERSION = "1.3.0"
PLANET_IDS = ("399", "499")


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_dev_origin: str = "http://localhost:5173"
    transport_mode: str = "simulator"            # "simulator" or "fpga"
    serial_port: str = ""
    serial_baud: int = 115200
    brain_enabled: bool = False
    sim_speed: float = 1.0
    link_delay_demo: bool = False                # wrap the transport in DelayTransport (plan section 10)
    db_path: str = str(APP_DIR / "artifacts" / "runtime" / "interstellar.sqlite3")
    plans_dir: str = str(APP_DIR / "data" / "plans")
    auto_blackout: bool = False                  # every flight gets a blackout window (plan 18.5)
    fleet_path: str = ""                         # empty = fleet.json next to the mission database
    extra_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        """Environment variables win over the repo's .env file; both are optional."""
        env = {**_read_dotenv(REPO_DIR / ".env"), **os.environ}
        s = cls()
        s.host = env.get("API_HOST", s.host)
        s.port = int(env.get("API_PORT", s.port))
        s.frontend_dev_origin = env.get("FRONTEND_DEV_ORIGIN", s.frontend_dev_origin)
        s.transport_mode = env.get("TRANSPORT_MODE", s.transport_mode).lower()
        s.serial_port = env.get("SERIAL_PORT", "")
        s.serial_baud = int(env.get("SERIAL_BAUD", s.serial_baud))
        s.brain_enabled = env.get("BRAIN_ENABLED", "false").lower() == "true"
        s.sim_speed = float(env.get("SIM_SPEED", s.sim_speed))
        # On unless switched off: the demo shows the shuttle flying without the control station.
        s.auto_blackout = env.get("AUTO_BLACKOUT", "true").lower() == "true"
        s.link_delay_demo = env.get("LINK_DELAY_DEMO", "false").lower() == "true"
        s.db_path = env.get("INTERSTELLAR_DB", s.db_path)
        return s


def load_validators() -> dict[str, Draft202012Validator]:
    """One validator per contract schema, keyed by short name ('mission_plan', ...)."""
    schemas = [json.loads(f.read_text(encoding="utf-8")) for f in (CONTRACTS / "schemas").glob("*.json")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    return {s["$id"].rsplit("/", 1)[1].removesuffix(".schema.json"): Draft202012Validator(s, registry=registry)
            for s in schemas}


def fixture(name: str) -> dict:
    return json.loads((CONTRACTS / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def plan_digest(plan: dict) -> str:
    body = {k: v for k, v in plan.items() if k != "plan_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PlanStore:
    """Immutable plans by id. Only plans that pass the schema and their own SHA-256 get in."""

    def __init__(self, validators: dict, plans_dir: str | None = None):
        self._validator = validators["mission_plan"]
        self._plans: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.rejected: list[dict] = []
        self.add(fixture("mission_plan_earth_mars"))          # synthetic mock, labelled as such
        if plans_dir and Path(plans_dir).is_dir():
            for path in sorted(Path(plans_dir).glob("*.json")):
                try:
                    self.add(json.loads(path.read_text(encoding="utf-8")))
                except ValueError as err:
                    self.rejected.append({"file": path.name, "error": str(err)})

    def add(self, plan: dict) -> str:
        errors = list(self._validator.iter_errors(plan))
        if errors:
            raise ValueError(f"plan fails schema: {errors[0].message}")
        if plan_digest(plan) != plan["plan_sha256"]:
            raise ValueError("plan_sha256 does not match the plan contents")
        with self._lock:
            self._plans[plan["plan_id"]] = plan
        return plan["plan_id"]

    def get(self, plan_id: str) -> dict | None:
        return self._plans.get(plan_id)

    def summaries(self) -> list[dict]:
        return [{"plan_id": pl["plan_id"], "objectives_won": pl["objectives_won"],
                 "origin_body_id": pl["origin_body_id"], "destination_body_id": pl["destination_body_id"],
                 "data_mode": pl["data_mode"], "departure": pl["departure"], "arrival": pl["arrival"],
                 "dv_total_km_s": pl["dv"]["dv_total_km_s"],
                 "propellant_required_kg": pl["masses"]["propellant_required_kg"]}
                for pl in self._plans.values()]

    def data_modes(self) -> list[str]:
        return sorted({pl["data_mode"] for pl in self._plans.values()})


def planet_info(body_id: str, scene_epoch_jd_tdb: float | None, validators: dict) -> dict:
    """PlanetInfo from the NASA owner's adapter when it exists, else the labelled mock fixture.

    Adapter contract: app.backend.planet_data.get_planet_info(body_id: str,
    scene_epoch_jd_tdb: float | None) -> dict valid against planet_info.schema.json.
    An adapter failure falls back to the fixture so planet selection keeps working.
    """
    try:
        from app.backend.planet_data import get_planet_info      # type: ignore[import-not-found]
        info = get_planet_info(body_id, scene_epoch_jd_tdb)
        if validators["planet_info"].is_valid(info):
            return info
    except Exception:                                            # noqa: BLE001 - any adapter failure
        pass
    return fixture(f"planet_info_{body_id}")


class MissionDb:
    """Remembers the wire ids of the active mission so a backend restart can reconcile."""

    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("""CREATE TABLE IF NOT EXISTS mission (
            mission_uuid TEXT PRIMARY KEY, plan_id TEXT, controller_source TEXT,
            wire_session INTEGER, wire_mission INTEGER, plan_crc16 INTEGER, next_seq INTEGER,
            last_state TEXT, updated_utc TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self._db.commit()

    def save(self, record: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO mission (mission_uuid, plan_id, controller_source, wire_session,"
                " wire_mission, plan_crc16, next_seq, last_state) VALUES (?,?,?,?,?,?,?,?)",
                (record["mission_uuid"], record["plan_id"], record["controller_source"],
                 record["wire_session"], record["wire_mission"], record["plan_crc16"],
                 record["next_seq"], record["last_state"]))
            self._db.commit()

    def latest(self) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT mission_uuid, plan_id, controller_source, wire_session, wire_mission,"
                " plan_crc16, next_seq, last_state FROM mission ORDER BY updated_utc DESC, rowid DESC LIMIT 1"
            ).fetchone()
        keys = ("mission_uuid", "plan_id", "controller_source", "wire_session", "wire_mission",
                "plan_crc16", "next_seq", "last_state")
        return dict(zip(keys, row)) if row else None

    def close(self) -> None:
        self._db.close()
