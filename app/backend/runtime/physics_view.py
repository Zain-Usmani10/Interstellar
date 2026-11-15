"""Turn board evidence (tick, executed events) into what the browser draws.

No orbital mechanics is solved here. The planner already stored sampled states in the
MissionPlan; this module only interpolates them at the epoch the board reports and decides
which phase the evidence supports. It never extrapolates outside the stored samples.
"""
from __future__ import annotations

import math

from app.contracts import protocol_v1 as p

C_KM_S = 299792.458


def epoch_jd_tdb(plan: dict, tick: int) -> float:
    ticks = plan["ticks"]
    return plan["departure"]["jd_tdb"] + (tick - ticks["departure_tick"]) * ticks["seconds_per_tick"] / 86400.0


def interpolate(states: list[dict], jd: float) -> tuple[list[float], list[float]] | None:
    """Cubic Hermite interpolation of position/velocity samples. None outside the samples."""
    if not states or jd < states[0]["jd_tdb"] - 1e-9 or jd > states[-1]["jd_tdb"] + 1e-9:
        return None
    lo, hi = 0, len(states) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if states[mid]["jd_tdb"] <= jd:
            lo = mid
        else:
            hi = mid
    a, b = states[lo], states[hi]
    h = (b["jd_tdb"] - a["jd_tdb"]) * 86400.0           # seconds, because velocity is km/s
    if h <= 0:
        return list(a["r_km"]), list(a["v_km_s"])
    s = min(1.0, max(0.0, (jd - a["jd_tdb"]) * 86400.0 / h))
    h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
    h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
    d00, d10 = (6 * s**2 - 6 * s) / h, 3 * s**2 - 4 * s + 1
    d01, d11 = (-6 * s**2 + 6 * s) / h, 3 * s**2 - 2 * s
    r = [h00 * a["r_km"][i] + h10 * h * a["v_km_s"][i] + h01 * b["r_km"][i] + h11 * h * b["v_km_s"][i]
         for i in range(3)]
    v = [d00 * a["r_km"][i] + d10 * a["v_km_s"][i] + d01 * b["r_km"][i] + d11 * b["v_km_s"][i]
         for i in range(3)]
    return r, v


def body_states(plan: dict, body_id: str) -> list[dict]:
    return next(b["states"] for b in plan["bodies"] if b["body_id"] == body_id)


def reconstruct(plan: dict, status: p.Status) -> dict:
    """Spacecraft phase/position, planet positions, outcome and light-time for one STATUS."""
    ticks = plan["ticks"]
    jd = epoch_jd_tdb(plan, status.tick)
    origin = interpolate(body_states(plan, plan["origin_body_id"]), jd)
    destination = interpolate(body_states(plan, plan["destination_body_id"]), jd)
    departed = bool(status.executed_mask & p.MASK_DEPARTURE)
    captured = bool(status.executed_mask & p.MASK_CAPTURE)
    failure = None
    outcome = "pending"
    craft = None

    if departed and status.departure_executed_tick != ticks["departure_tick"]:
        phase, outcome = "unknown", "plan_invalid"
        failure = {"code": "DEPARTURE_TICK_MISMATCH",
                   "message": "The controller departed at a tick that differs from the validated plan."}
    elif captured:
        if status.capture_executed_tick == ticks["arrival_tick"]:
            phase, outcome, craft = "captured", "captured", destination
        else:
            phase, outcome = "unknown", "plan_invalid"
            failure = {"code": "CAPTURE_TICK_MISMATCH",
                       "message": "The controller captured at a tick that differs from the validated plan."}
    elif not departed:
        phase, craft = "at_origin", origin
    elif status.tick <= ticks["arrival_tick"]:
        phase, craft = "coast", interpolate(plan["nominal_path"], jd)
    else:
        # Past the arrival tick with no capture event: the craft keeps coasting around the Sun.
        phase, outcome = "uncaptured_coast", "uncaptured"
        craft = interpolate(plan["uncaptured_coast_path"], jd)

    if status.state == p.State.ABORTED and outcome != "plan_invalid":
        outcome = "aborted"
    if craft is None and phase != "unknown":
        failure = failure or {"code": "EPOCH_OUTSIDE_PLAN_SAMPLES",
                              "message": "No stored state covers this epoch; position not shown."}

    delay = None
    if craft and origin:
        delay = math.dist(craft[0], origin[0]) / C_KM_S
    return {
        "epoch_jd_tdb": jd,
        "spacecraft": {"phase": phase, "r_km": craft[0] if craft else None,
                       "v_km_s": craft[1] if craft else None},
        "planets": [{"body_id": bid, "r_km": st[0]}
                    for bid, st in ((plan["origin_body_id"], origin), (plan["destination_body_id"], destination))
                    if st],
        "outcome": outcome,
        "failure": failure,
        "delay_physical_s": delay,
    }
