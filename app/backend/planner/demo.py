"""One-call planning pipeline and the command that (re)builds the checked-in demo plans.

    python -m app.backend.planner.demo           # offline: NASA cache only, fails if data is missing
    python -m app.backend.planner.demo --live    # fetch missing NASA data first (one request at a time)

Output: app/data/plans/mission_plan_earth_mars_<objective>.json   (only MissionPlans live in that folder)
        app/data/search/grid_earth_mars.json, app/data/search/index.json
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from ..ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache, EphemerisSource
from ..ephemeris.horizons import HorizonsClient
from ..physics.burns import Vehicle
from .plan import TickMap, build_plan, verify_plan
from .search import Constants, GridSpec, SearchCancelled, grid_summary, run_grid, select_winners

PLANS_DIR = Path(__file__).resolve().parents[2] / "data" / "plans"
SEARCH_DIR = Path(__file__).resolve().parents[2] / "data" / "search"


def plan_earth_mars(source: EphemerisSource, grid: GridSpec = GridSpec(), vehicle: Vehicle = Vehicle(),
                    ticks: TickMap = TickMap(), progress=lambda fraction: None, cancelled=lambda: False) -> dict:
    """Search the grid and return {'plans': [MissionPlan, ...], 'grid': summary}.

    One plan per distinct winner. If the same route wins both objectives there is one plan that says so.
    """
    constants = Constants.from_source(source)
    cells = run_grid(source, grid, vehicle, constants, lambda f: progress(0.8 * f), cancelled)
    winners = select_winners(cells)
    n_feasible = sum(c.feasible for c in cells)
    grid_files = set(source.files_used)          # NASA replies the search itself read
    plans, seen = [], []
    for objective, cell in winners.items():
        if any(cell is s for s in seen):
            continue
        seen.append(cell)
        source.files_used = set(grid_files)      # each plan lists the search data plus only its own planet tracks
        won = [name for name, w in winners.items() if w is cell]
        plans.append(build_plan(cell, won, grid, n_feasible, vehicle, constants, source, ticks))
        progress(0.8 + 0.2 * len(plans) / len(set(map(id, winners.values()))))
    return {"plans": plans, "grid": grid_summary(cells, grid, winners)}


def _days_between(start_utc: str, end_utc: str) -> float:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(end_utc, fmt) - datetime.strptime(start_utc, fmt)).total_seconds() / 86400.0


def run_search(params: dict, progress=lambda fraction: None, cancelled=lambda: False) -> list[dict]:
    """Backend hook (app/contracts/api_v1.md): validated planning-job body in, MissionPlan dicts out.

    params: {departure_start_utc, departure_end_utc, tof_min_days, tof_max_days, n_departures, n_durations, vehicle?}
    Uses the NASA cache only unless INTERSTELLAR_NASA_LIVE=1 is set; offline requests outside the cache
    raise EPHEMERIS_UNAVAILABLE. A cancelled search returns no plans.
    """
    n_dep, n_dur = int(params["n_departures"]), int(params["n_durations"])
    span = _days_between(params["departure_start_utc"], params["departure_end_utc"])
    tof_span = float(params["tof_max_days"]) - float(params["tof_min_days"])
    if span < 0 or tof_span < 0:
        raise ValueError("end of a search range is before its start")
    grid = GridSpec(
        departure_start_utc=params["departure_start_utc"],
        departure_step_days=span / (n_dep - 1) if n_dep > 1 and span > 0 else 1.0,
        n_departures=n_dep if span > 0 else 1,
        tof_min_days=float(params["tof_min_days"]),
        tof_step_days=tof_span / (n_dur - 1) if n_dur > 1 and tof_span > 0 else 1.0,
        n_durations=n_dur if tof_span > 0 else 1,
    )
    fields = ("dry_mass_kg", "payload_mass_kg", "isp_s", "propellant_capacity_kg")
    vehicle = Vehicle(**{k: float(v) for k, v in (params.get("vehicle") or {}).items() if k in fields})
    client = HorizonsClient() if os.environ.get("INTERSTELLAR_NASA_LIVE") == "1" else None
    source = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR), client)
    try:
        return plan_earth_mars(source, grid, vehicle, progress=progress, cancelled=cancelled)["plans"]
    except SearchCancelled:
        return []


def load_demo_plan(objective: str = "least_fuel", plans_dir: Path = PLANS_DIR, search_dir: Path = SEARCH_DIR) -> dict:
    """Load a checked-in validated plan and re-verify its digest and gates before handing it out."""
    index = json.loads((search_dir / "index.json").read_text(encoding="utf-8"))
    plan = json.loads((plans_dir / index["objectives"][objective]).read_text(encoding="utf-8"))
    problems = verify_plan(plan)
    if problems:
        raise ValueError("stored plan failed verification: " + "; ".join(problems))
    return plan


def write_demo_plans(result: dict, plans_dir: Path = PLANS_DIR, search_dir: Path = SEARCH_DIR) -> dict:
    plans_dir.mkdir(parents=True, exist_ok=True)
    search_dir.mkdir(parents=True, exist_ok=True)
    index = {"objectives": {}, "grid": "grid_earth_mars.json"}
    for plan in result["plans"]:
        name = f"mission_plan_earth_mars_{plan['objectives_won'][0]}.json"
        (plans_dir / name).write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")
        for objective in plan["objectives_won"]:
            index["objectives"][objective] = name
    (search_dir / index["grid"]).write_text(json.dumps(result["grid"], indent=1) + "\n", encoding="utf-8")
    (search_dir / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="fetch missing NASA/JPL Horizons data into the cache first")
    args = parser.parse_args()
    if args.live:
        live = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR), HorizonsClient())
        plan_earth_mars(live)
        print(f"NASA requests made: {live.client.request_count}")
    # Always build the stored plans from the cache alone, so they are honestly labelled nasa_cached
    # and anyone can reproduce them with no network.
    result = plan_earth_mars(EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR)))
    write_demo_plans(result)
    for plan in result["plans"]:
        print(f"{'+'.join(plan['objectives_won']):30s} depart {plan['departure']['utc']}  arrive {plan['arrival']['utc']}  "
              f"dv {plan['dv']['dv_total_km_s']:.3f} km/s  propellant {plan['masses']['propellant_required_kg']:.1f} kg  "
              f"residual {plan['residuals']['position_km']:.2e} km  [{plan['data_mode']}]")


if __name__ == "__main__":
    main()
