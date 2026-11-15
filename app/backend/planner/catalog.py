"""Build an offline, bounded-search catalogue for every ordered planet pair.

No absence-of-route claim extends beyond the recorded grid and vehicle.
Existing Earth/Mars plans are reused byte-for-byte, never regenerated here.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from ..ephemeris.cache import EphemerisCache, EphemerisSource, EphemerisUnavailable
from ..ephemeris.horizons import HorizonsClient, HorizonsError, PLANET_IDS
from ..physics.burns import Vehicle, BurnModelError, DEMO_VEHICLE_LABEL
from ..runtime.stores import load_validators
from .demo import PLANS_DIR, SEARCH_DIR, load_demo_plan, plan_pair
from .plan import PlanRejected, TickMap, verify_plan, presentation_plan
from .search import GridSpec, NoFeasibleRoute


def pair_grid(origin: str, destination: str) -> GridSpec:
    # Explicit search design, not a physical transfer prediction. Wide bounds
    # for outer planets; NASA states and Lambert decide whether any arc works.
    furthest = max(int(origin), int(destination))
    low, high = ((60, 420) if furthest <= 499 else
                 (300, 3000) if furthest == 599 else
                 (600, 8000) if furthest == 699 else
                 (1500, 20000) if furthest == 799 else (2000, 40000))
    return GridSpec(departure_step_days=73, n_departures=6,
                    tof_min_days=low, tof_step_days=(high-low)/7, n_durations=8)


DEMO_VEHICLE = Vehicle(label=DEMO_VEHICLE_LABEL, isp_s=900.0)


def build_catalog(live=False, demo=False, output_path=None, presentation=False, fetch_pairs=None):
    cache = EphemerisCache()
    validator = load_validators()["mission_plan"]
    client = HorizonsClient() if live else None
    vehicle = DEMO_VEHICLE if demo else Vehicle()
    catalog_path = Path(output_path) if output_path is not None else SEARCH_DIR / "planet_pairs.json"
    manifest = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"version": 1, "expected_pairs": 56}
    records_key, complete_key = ("demo_pairs", "demo_complete") if demo else ("pairs", "complete")
    records = []
    fetch_pairs = set(fetch_pairs) if fetch_pairs is not None else None
    for origin in PLANET_IDS:
        for destination in PLANET_IDS:
            if origin == destination:
                continue
            grid = pair_grid(origin, destination)
            record = {"origin_body_id": origin, "destination_body_id": destination,
                      "grid": asdict(grid), "vehicle": asdict(vehicle),
                      "position_reference": "NASA planet centres, not system barycentres",
                      "scope": "bounded grid only; not a global feasibility conclusion"}
            print(f"Searching {origin}->{destination}", flush=True)
            try:
                if not demo and (origin, destination) == ("399", "499"):
                    plans = [load_demo_plan(o) for o in ("least_fuel", "earliest_arrival")]
                    record["grid"] = plans[0]["grid"]
                else:
                    if live and (fetch_pairs is None or f"{origin}:{destination}" in fetch_pairs):
                        plan_pair(EphemerisSource(cache, client), grid, vehicle,
                                  origin_body_id=origin, destination_body_id=destination)
                    plans = plan_pair(EphemerisSource(cache), grid, vehicle,
                                      origin_body_id=origin, destination_body_id=destination)["plans"]
                if presentation:
                    plans = [presentation_plan(p) for p in plans]
                for plan in plans:
                    validator.validate(plan)
                    errors = verify_plan(plan)
                    if errors:
                        raise PlanRejected("; ".join(errors))
                    if presentation or demo or (origin, destination) != ("399", "499"):
                        variant = ("_demo" if demo else "") + ("_presentation" if presentation else "")
                        name = f"mission_plan_{origin}_{destination}{variant}_{plan['objectives_won'][0]}.json"
                        (PLANS_DIR / name).write_text(json.dumps(plan, indent=1)+"\n", encoding="utf-8")
                record.update(status="validated", objectives={
                    objective: plan["plan_id"] for plan in plans for objective in plan["objectives_won"]})
            except (NoFeasibleRoute, EphemerisUnavailable, HorizonsError, PlanRejected, BurnModelError) as error:
                # Distinguish incomplete data/numerical rejection from a searched
                # grid with no vehicle-feasible cell. Never manufacture a plan.
                status = "no_feasible_route" if isinstance(error, NoFeasibleRoute) else "unavailable"
                record.update(status=status, reason_code=getattr(error, "code", type(error).__name__),
                              reason=str(error))
                if isinstance(error, NoFeasibleRoute):
                    record["rejection_counts"] = getattr(error, "rejection_counts", {})
            records.append(record)
            print(f"  {record['status']}", flush=True)
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            manifest.update({complete_key: len(records) == 56, records_key: records})
            manifest["presentation_max_seconds"] = TickMap().end_tick / 100
            catalog_path.write_text(json.dumps(manifest, indent=1)+"\n", encoding="utf-8")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Build the separate opt-in 900 s vehicle records")
    parser.add_argument("--output", type=Path, help="Write a separate manifest for independent qualification")
    parser.add_argument("--presentation", action="store_true", help="Apply the section 19 demo timing")
    parser.add_argument("--fetch-pair", action="append", help="Limit live fetches to origin:destination (repeatable)")
    args = parser.parse_args()
    build_catalog(args.live, args.demo, args.output, args.presentation, args.fetch_pair)
