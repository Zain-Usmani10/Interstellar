"""Turn a winning grid cell into the immutable, validated MissionPlan (contracts schema v1).

A plan is only produced if an independent numerical integration of the coast lands on the destination's
NASA position within 10 km and matches the Lambert arrival velocity within 1e-5 km/s.
These are consistency checks of our simplified Sun-only model, not real-world accuracy claims.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass

import numpy as np

from ..ephemeris.cache import EphemerisSource
from ..ephemeris.horizons import FRAME, BODY_NAMES, canonical_epoch
from ..ephemeris.interp import hermite_state
from ..ephemeris.timeconv import jd_tdb_to_utc
from ..physics.burns import G0_M_S2, Vehicle, parking_radius_km
from ..physics.twobody import propagate
from .search import DESTINATION_ID, ORIGIN_ID, Cell, Constants, GridSpec, validate_pair

MODEL_VERSION = "two-body-lambert-v1"
SCHEMA_VERSION = 1
POSITION_LIMIT_KM = 10.0
VELOCITY_LIMIT_KM_S = 1e-5
INTERPOLATION_LIMIT_KM = 10.0
NOMINAL_SAMPLES = 512
UNCAPTURED_SAMPLES = 33
MAX_END_TICK = 360000
_PLAN_NAMESPACE = uuid.UUID("6f1c2a54-9d0e-4b7a-8a53-1e2f7c9b4d10")


class PlanRejected(Exception):
    """The candidate failed a numerical gate and must not become a mission-ready plan."""
    code = "PLAN_REJECTED"


@dataclass(frozen=True)
class TickMap:
    """Board time. The FPGA counts 100 ticks per real second; the flight is compressed to fit a demo."""
    departure_tick: int = 10
    arrival_tick: int = 12010          # about two minutes of real time after departure
    end_tick: int = 12610              # six more real seconds: room to show a missed capture

    def __post_init__(self):
        if not 0 < self.departure_tick < self.arrival_tick < self.end_tick <= MAX_END_TICK:
            raise ValueError("need 0 < departure_tick < arrival_tick < end_tick <= 360000")

    def seconds_per_tick(self, tof_s: float) -> float:
        return tof_s / (self.arrival_tick - self.departure_tick)

    def epoch_jd_tdb(self, tick: int, departure_jd_tdb: float, tof_s: float) -> float:
        return departure_jd_tdb + (tick - self.departure_tick) * self.seconds_per_tick(tof_s) / 86400.0


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def plan_digest(plan: dict) -> str:
    """SHA-256 of the plan without its own digest field (definition from the contract schema)."""
    body = {k: v for k, v in plan.items() if k != "plan_sha256"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _vec(x) -> list[float]:
    return [float(c) for c in x]


def _sample(coast, t0_jd: float, n: int) -> list[dict]:
    out = []
    for t in np.linspace(0.0, coast.duration_s, n):
        r, v = coast.state(float(t))
        out.append({"jd_tdb": t0_jd + float(t) / 86400.0, "r_km": _vec(r), "v_km_s": _vec(v)})
    return out


def _body_track(source: EphemerisSource, body_id: str, start_jd: float, end_jd: float, exact: list[float], spacing=1.0) -> tuple[list[dict], dict]:
    """NASA nodes covering the run and a held-out midpoint accuracy check."""
    first = math.floor(start_jd - 0.5) + 0.5            # TDB midnight at or before the start
    last = math.ceil(end_jd - 0.5) + 0.5
    nodes = [first + d * spacing for d in range(int(round((last - first) / spacing)) + 1)]
    epochs = sorted({canonical_epoch(e) for e in nodes + exact})
    states = [{"jd_tdb": s.jd_tdb, "r_km": list(s.r_km), "v_km_s": list(s.v_km_s)} for s in source.states(body_id, epochs)]

    # Held-out check: ask NASA for noon states we did NOT use as nodes and compare with our interpolation.
    picks = sorted({int(i) for i in np.linspace(0, len(nodes) - 2, 12)})
    held_out = source.states(body_id, [nodes[i] + spacing / 2 for i in picks])
    errors = [float(np.linalg.norm(hermite_state(states, h.jd_tdb)[0] - np.array(h.r_km))) for h in held_out]
    check = {"n_held_out": len(errors), "max_error_km": max(errors)}
    return states, check


def build_plan(cell: Cell, objectives_won: list[str], grid: GridSpec, n_feasible: int, vehicle: Vehicle,
               constants: Constants, source: EphemerisSource, ticks: TickMap = TickMap(),
               origin_body_id=ORIGIN_ID, destination_body_id=DESTINATION_ID) -> dict:
    """Validate one candidate and assemble its MissionPlan. Raises PlanRejected if a gate fails."""
    validate_pair(origin_body_id, destination_body_id)
    if not (cell.status == "ok" and cell.feasible):
        raise PlanRejected(f"PLAN_REJECTED: candidate is not a feasible solved cell ({cell.status})")
    v = cell.vectors
    tof_s = (cell.arrival_jd_tdb - cell.departure_jd_tdb) * 86400.0
    mu = constants.mu_sun

    # 1. Independent check: integrate the coast from Earth with the Lambert velocity; do we reach Mars?
    coast = propagate(mu, v["origin_r"], v["lambert_v1"], tof_s)
    r_end, v_end = coast.state(tof_s)
    position_residual = float(np.linalg.norm(r_end - np.array(v["destination_r"])))
    velocity_residual = float(np.linalg.norm(v_end - v["lambert_v2"]))
    tighter = propagate(mu, v["origin_r"], v["lambert_v1"], tof_s, rtol=1e-12)     # convergence: tighter tolerance agrees
    convergence_km = float(np.linalg.norm(tighter.state(tof_s)[0] - r_end))
    energy0, h0 = coast.specific_energy(0.0), coast.angular_momentum(0.0)
    energy_drift = abs(coast.specific_energy(tof_s) - energy0) / abs(energy0)
    momentum_drift = float(np.linalg.norm(coast.angular_momentum(tof_s) - h0) / np.linalg.norm(h0))

    # 2. If the capture burn never happens the ship keeps coasting: integrate on to the end of the run.
    end_jd = ticks.epoch_jd_tdb(ticks.end_tick, cell.departure_jd_tdb, tof_s)
    start_jd = ticks.epoch_jd_tdb(0, cell.departure_jd_tdb, tof_s)
    uncaptured = propagate(mu, r_end, v_end, (end_jd - cell.arrival_jd_tdb) * 86400.0)
    min_radius = min(coast.min_radius_km(), uncaptured.min_radius_km())

    passed = (position_residual < POSITION_LIMIT_KM and velocity_residual < VELOCITY_LIMIT_KM_S
              and convergence_km < POSITION_LIMIT_KM and min_radius > constants.radius_sun_km)
    if not passed:
        raise PlanRejected(f"PLAN_REJECTED: residuals {position_residual:.3g} km / {velocity_residual:.3g} km/s, "
                           f"convergence {convergence_km:.3g} km, min radius {min_radius:.3g} km")

    # 3. Both planets over the whole run (before departure .. after a missed capture), from NASA.
    # Mercury's rapid motion fails the daily-node gate; sample more densely,
    # retaining the same independent midpoint error limit.
    spacing = 0.5 if "199" in (origin_body_id, destination_body_id) else 1.0
    bodies, interpolation = [], {"method": "cubic_hermite", "node_spacing_days": spacing, "limit_km": INTERPOLATION_LIMIT_KM}
    for body_id in (origin_body_id, destination_body_id):
        name = BODY_NAMES[body_id]
        states, check = _body_track(source, body_id, start_jd, end_jd, [cell.departure_jd_tdb, cell.arrival_jd_tdb], spacing)
        if check["max_error_km"] >= INTERPOLATION_LIMIT_KM:
            raise PlanRejected(f"PLAN_REJECTED: {name} interpolation error {check['max_error_km']:.3g} km")
        bodies.append({"body_id": body_id, "name": name, "states": states})
        interpolation[name.lower()] = check

    p = cell.propellant
    plan = {
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "data_mode": source.data_mode,
        "origin_body_id": origin_body_id,
        "destination_body_id": destination_body_id,
        "objectives_won": list(objectives_won),
        "departure": {"utc": jd_tdb_to_utc(cell.departure_jd_tdb), "jd_tdb": cell.departure_jd_tdb},
        "arrival": {"utc": jd_tdb_to_utc(cell.arrival_jd_tdb), "jd_tdb": cell.arrival_jd_tdb},
        "tof_s": tof_s,
        "frame": dict(FRAME),
        "constants": {
            "mu_sun_km3_s2": constants.mu_sun,
            "mu_origin_km3_s2": constants.mu_origin,
            "mu_destination_km3_s2": constants.mu_destination,
            "g0_m_s2": G0_M_S2,
            "radius_sun_km": constants.radius_sun_km,
            "radius_origin_km": constants.radius_origin_km,
            "radius_destination_km": constants.radius_destination_km,
            "source": "GM and volumetric mean radius as printed in the NASA/JPL Horizons object-data pages of "
                      f"bodies 10, {origin_body_id} and {destination_body_id} (body GM, not planet-system GM); see provenance.sources. "
                      "g0 is the defined standard gravity.",
        },
        "boundary": {
            "origin_r_km": _vec(v["origin_r"]), "origin_v_km_s": _vec(v["origin_v"]),
            "destination_r_km": _vec(v["destination_r"]), "destination_v_km_s": _vec(v["destination_v"]),
            "lambert_v1_km_s": _vec(v["lambert_v1"]), "lambert_v2_km_s": _vec(v["lambert_v2"]),
        },
        "dv": {
            "v_inf_depart_km_s": cell.v_inf_depart, "v_inf_arrive_km_s": cell.v_inf_arrive,
            "r_park_origin_km": parking_radius_km(constants.mu_origin, constants.radius_origin_km),
            "r_park_destination_km": parking_radius_km(constants.mu_destination, constants.radius_destination_km),
            "dv_depart_km_s": cell.dv_depart, "dv_capture_km_s": cell.dv_capture, "dv_total_km_s": cell.dv_total,
        },
        "vehicle": asdict(vehicle),
        "masses": {
            "m_final_kg": p.m_final_kg, "propellant_required_kg": p.required_kg,
            "departure_propellant_kg": p.departure_kg, "capture_propellant_kg": p.capture_kg,
        },
        "wire": {"initial_fuel_g": p.initial_g, "departure_fuel_g": p.departure_g, "capture_fuel_g": p.capture_g},
        "ticks": {
            "tick_hz": 100, "departure_tick": ticks.departure_tick, "arrival_tick": ticks.arrival_tick,
            "end_tick": ticks.end_tick, "seconds_per_tick": ticks.seconds_per_tick(tof_s),
        },
        "residuals": {
            "position_km": position_residual, "velocity_km_s": velocity_residual,
            "min_heliocentric_radius_km": min_radius, "passed": True,
            "position_limit_km": POSITION_LIMIT_KM, "velocity_limit_km_s": VELOCITY_LIMIT_KM_S,
            "tolerance_convergence_km": convergence_km,
            "relative_energy_drift": energy_drift, "relative_angular_momentum_drift": momentum_drift,
            "method": "SciPy DOP853, rtol 1e-10, atol 1e-3 km / 1e-9 km/s, compared with the Lambert target",
        },
        "grid": {
            "departure_start_utc": grid.departure_start_utc,
            "departure_end_utc": jd_tdb_to_utc(grid.departure_epochs()[-1]),
            "tof_min_days": grid.tof_min_days, "tof_max_days": grid.tof_max_days,
            "n_departures": grid.n_departures, "n_durations": grid.n_durations, "n_feasible": n_feasible,
            "departure_step_days": grid.departure_step_days, "tof_step_days": grid.tof_step_days,
            "label": "best within this grid",
        },
        "nominal_path": _sample(coast, cell.departure_jd_tdb, NOMINAL_SAMPLES),
        "uncaptured_coast_path": _sample(uncaptured, cell.arrival_jd_tdb, UNCAPTURED_SAMPLES),
        "bodies": bodies,
        "body_interpolation": interpolation,
        "run_interval": {"start_jd_tdb": start_jd, "end_jd_tdb": end_jd,
                         "real_demo_seconds": ticks.end_tick / 100.0, "simulated_flight_days": tof_s / 86400.0},
        "provenance": {
            "sources": source.sources(),
            "notes": "Planet positions/velocities and GM values are NASA/JPL Horizons data read from the local "
                     "verified cache (data_mode says cached or live). The transfer arc, burns and propellant are "
                     "computed by this project with a simplified model: Sun-only two-body coast, zero-revolution "
                     "prograde Lambert arc, impulsive burns from circular 12-hour parking orbits, no launch, "
                     "atmosphere, third bodies or finite burns. NASA did not compute or certify this route. "
                     "Lambert solver: lamberthub 1.0.0 izzo2015 (GPL-3.0).",
        },
    }
    # The id is derived from the full contents, so two plans that differ anywhere (even in the last
    # float digit on another machine) can never share an id.
    plan["plan_id"] = str(uuid.uuid5(_PLAN_NAMESPACE, plan_digest(plan)))
    plan["plan_sha256"] = plan_digest(plan)
    return plan


def presentation_plan(plan: dict) -> dict:
    """Halve board duration without changing physical epochs, paths or fuel.

    Return a new immutable identity; never mutate the legacy source plan.
    """
    errors = verify_plan(plan)
    if errors:
        raise PlanRejected("; ".join(errors))
    result = deepcopy(plan)
    for key in ("departure_tick", "arrival_tick", "end_tick"):
        if result["ticks"][key] % 2:
            raise PlanRejected("presentation conversion requires even source ticks")
        result["ticks"][key] //= 2
    result["ticks"]["seconds_per_tick"] *= 2
    result["run_interval"]["real_demo_seconds"] /= 2
    result.pop("plan_id")
    result.pop("plan_sha256")
    result["plan_id"] = str(uuid.uuid5(_PLAN_NAMESPACE, plan_digest(result)))
    result["plan_sha256"] = plan_digest(result)
    return result


def verify_plan(plan: dict) -> list[str]:
    """Re-check a stored plan without the network. Returns a list of problems (empty = good)."""
    problems = []
    if plan.get("plan_sha256") != plan_digest(plan):
        problems.append("plan_sha256 does not match the plan contents (edited after validation?)")
    res, t, w = plan["residuals"], plan["ticks"], plan["wire"]
    if not (res["passed"] and res["position_km"] < POSITION_LIMIT_KM and res["velocity_km_s"] < VELOCITY_LIMIT_KM_S):
        problems.append("propagation residuals are outside the mission-ready limits")
    if not 0 < t["departure_tick"] < t["arrival_tick"] < t["end_tick"] <= MAX_END_TICK:
        problems.append("tick ordering is invalid")
    if w["initial_fuel_g"] != w["departure_fuel_g"] + w["capture_fuel_g"] or min(w.values()) < 1:
        problems.append("integer fuel ledger is inconsistent")
    if w["initial_fuel_g"] > plan["vehicle"]["propellant_capacity_kg"] * 1000:
        problems.append("loaded propellant exceeds the tank capacity")
    start, end = plan["run_interval"]["start_jd_tdb"], plan["run_interval"]["end_jd_tdb"]
    for body in plan["bodies"]:
        times = [s["jd_tdb"] for s in body["states"]]
        if times != sorted(set(times)) or times[0] > start or times[-1] < end:
            problems.append(f"{body['name']} states do not cover the whole run interval in order")
    return problems
