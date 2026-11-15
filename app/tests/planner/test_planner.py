"""Planner tests. Offline: the search runs on the checked-in NASA cache (data_mode nasa_cached)."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from app.backend.ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache, EphemerisSource, EphemerisUnavailable
from app.backend.ephemeris.interp import hermite_state
from app.backend.ephemeris.track_source import TrackSource
from app.backend.physics.burns import Vehicle, propellant_for
from app.backend.physics.twobody import propagate
from app.backend.planner import run_search
from app.backend.planner.demo import PLANS_DIR, SEARCH_DIR, load_demo_plan, plan_earth_mars
from app.backend.planner.plan import PlanRejected, TickMap, build_plan, plan_digest, verify_plan
from app.backend.planner.search import Cell, Constants, GridSpec, NoFeasibleRoute, run_grid, select_winners

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


@pytest.fixture(scope="module")
def track_source():
    return TrackSource()


@pytest.fixture(scope="module")
def offline_result():
    """The full default search, run from the NASA cache only."""
    return plan_earth_mars(EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR)))


def stored_plans() -> list[dict]:
    index = json.loads((SEARCH_DIR / "index.json").read_text(encoding="utf-8"))
    return [load_demo_plan(objective) for objective in index["objectives"]]


# ------------------------------------------------------------------ objective selection

def fake_cell(departure, tof, dv, status="ok") -> Cell:
    cell = Cell(departure, departure + tof, tof, status=status)
    cell.propellant = propellant_for(dv / 2, dv / 2, Vehicle())
    cell.feasible = cell.propellant.feasible and status == "ok"
    return cell


def test_earliest_arrival_is_not_shortest_flight_and_not_least_fuel():
    early_long = fake_cell(100.0, 200.0, 6.0)        # leaves first, arrives day 300
    late_short = fake_cell(250.0, 120.0, 7.0)        # shortest flight, but arrives day 370
    cheapest = fake_cell(180.0, 260.0, 4.5)          # least fuel, arrives day 440
    winners = select_winners([late_short, cheapest, early_long])
    assert winners["earliest_arrival"] is early_long
    assert winners["least_fuel"] is cheapest
    assert min([early_long, late_short, cheapest], key=lambda c: c.tof_days) is late_short


def test_earliest_arrival_tie_is_broken_by_propellant():
    a, b = fake_cell(100.0, 200.0, 6.0), fake_cell(80.0, 220.0, 5.0)     # both arrive day 300
    assert select_winners([a, b])["earliest_arrival"] is b


def test_failed_and_infeasible_cells_can_never_win():
    failed = fake_cell(10.0, 50.0, 0.2, status="lambert_failed: test")   # would be cheapest AND earliest
    too_heavy = fake_cell(20.0, 60.0, 30.0)                              # solved, but does not fit the tank
    unsolved = Cell(5.0, 30.0, 25.0, status="solar_intersection")        # no numbers at all
    good = fake_cell(100.0, 200.0, 6.0)
    assert not too_heavy.feasible
    winners = select_winners([failed, too_heavy, unsolved, good])
    assert winners["least_fuel"] is good and winners["earliest_arrival"] is good
    with pytest.raises(NoFeasibleRoute):
        select_winners([failed, too_heavy, unsolved])


def test_one_route_can_win_both_objectives_and_gets_one_plan():
    source = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR))
    result = plan_earth_mars(source, GridSpec(n_departures=1, tof_min_days=300.0, n_durations=1))
    assert len(result["plans"]) == 1
    assert result["plans"][0]["objectives_won"] == ["least_fuel", "earliest_arrival"]


def test_grid_bounds_are_enforced():
    with pytest.raises(ValueError):
        GridSpec(n_departures=26)
    with pytest.raises(ValueError):
        GridSpec(tof_min_days=0.0)
    with pytest.raises(ValueError):
        GridSpec(departure_step_days=-1.0)


# ------------------------------------------------------------------ the real NASA-backed search

def test_offline_search_reproduces_the_same_request(offline_result):
    repeated = plan_earth_mars(EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR)))
    assert repeated == offline_result
    assert all(not verify_plan(p) for p in repeated['plans'])


def test_search_summary_is_honest_about_the_grid(offline_result):
    grid = offline_result["grid"]
    assert len(grid["cells"]) == grid["n_departures"] * grid["n_durations"] == 600
    assert "within this grid" in grid["label"]
    feasible = [c for c in grid["cells"] if c["feasible"]]
    assert grid["n_feasible"] == len(feasible) > 0
    assert all(c["status"] != "ok" for c in grid["cells"] if not c["feasible"])
    least = min(feasible, key=lambda c: c["propellant_required_kg"])
    earliest = min(feasible, key=lambda c: (c["arrival_jd_tdb"], c["propellant_required_kg"]))
    assert "least_fuel" in least["objectives_won"] and "earliest_arrival" in earliest["objectives_won"]
    assert earliest["arrival_jd_tdb"] < least["arrival_jd_tdb"]
    assert earliest["propellant_required_kg"] > least["propellant_required_kg"]      # arriving sooner costs fuel


def test_dates_outside_the_cache_fail_explicitly():
    source = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR))
    with pytest.raises(EphemerisUnavailable) as err:
        plan_earth_mars(source, GridSpec(departure_start_utc="2028-06-01T00:00:00Z"))
    assert "EPHEMERIS_UNAVAILABLE" in str(err.value)


# ------------------------------------------------------------------ the stored MissionPlans

@pytest.mark.parametrize("plan", stored_plans(), ids=lambda p: "+".join(p["objectives_won"]))
class TestStoredPlan:
    def test_digest_and_gates(self, plan):
        assert verify_plan(plan) == []
        assert plan["plan_sha256"] == plan_digest(plan)
        assert plan["residuals"]["passed"] and plan["residuals"]["position_km"] < 10.0
        assert plan["residuals"]["velocity_km_s"] < 1e-5
        assert plan["residuals"]["min_heliocentric_radius_km"] > plan["constants"]["radius_sun_km"]

    def test_matches_the_contract_schema(self, plan):
        if not SCHEMA_DIR.is_dir():
            pytest.skip("app/contracts/schemas not on this branch yet (lands with contracts v1, PR #9)")
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        schemas = [json.loads(f.read_text(encoding="utf-8")) for f in SCHEMA_DIR.glob("*.json")]
        registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
        schema = next(s for s in schemas if s.get("title") == "MissionPlan")
        errors = [e.message for e in Draft202012Validator(schema, registry=registry).iter_errors(plan)]
        assert errors == []

    def test_independent_repropagation_reaches_mars(self, plan):
        b = plan["boundary"]
        coast = propagate(plan["constants"]["mu_sun_km3_s2"], b["origin_r_km"], b["lambert_v1_km_s"], plan["tof_s"])
        r_end, v_end = coast.state(plan["tof_s"])
        assert np.linalg.norm(r_end - b["destination_r_km"]) < 10.0
        assert np.linalg.norm(v_end - b["lambert_v2_km_s"]) < 1e-5

    def test_boundary_vectors_are_the_cached_nasa_rows(self, plan, track_source):
        earth = track_source.states("399", [plan["departure"]["jd_tdb"]])[0]
        mars = track_source.states("499", [plan["arrival"]["jd_tdb"]])[0]
        assert list(earth.r_km) == plan["boundary"]["origin_r_km"]
        assert list(mars.v_km_s) == plan["boundary"]["destination_v_km_s"]

    def test_tick_mapping_hits_both_boundary_epochs(self, plan):
        t = plan["ticks"]
        ticks = TickMap(t["departure_tick"], t["arrival_tick"], t["end_tick"])
        dep, tof = plan["departure"]["jd_tdb"], plan["tof_s"]
        assert t["seconds_per_tick"] == pytest.approx(tof / (t["arrival_tick"] - t["departure_tick"]))
        assert ticks.epoch_jd_tdb(t["departure_tick"], dep, tof) == dep
        assert ticks.epoch_jd_tdb(t["arrival_tick"], dep, tof) == pytest.approx(plan["arrival"]["jd_tdb"], abs=1e-9)
        assert ticks.epoch_jd_tdb(0, dep, tof) < dep                               # pre-departure ticks are earlier
        assert ticks.epoch_jd_tdb(0, dep, tof) == pytest.approx(plan["run_interval"]["start_jd_tdb"])
        assert ticks.epoch_jd_tdb(t["end_tick"], dep, tof) == pytest.approx(plan["run_interval"]["end_jd_tdb"])

    def test_paths_are_continuous_and_stay_inside_their_intervals(self, plan):
        nominal, coast = plan["nominal_path"], plan["uncaptured_coast_path"]
        assert len(nominal) == 512
        assert nominal[0]["jd_tdb"] == plan["departure"]["jd_tdb"]
        assert nominal[-1]["jd_tdb"] == pytest.approx(plan["arrival"]["jd_tdb"], abs=1e-9)
        assert nominal[0]["r_km"] == plan["boundary"]["origin_r_km"]
        assert np.linalg.norm(np.array(nominal[-1]["r_km"]) - plan["boundary"]["destination_r_km"]) < 10.0
        assert np.allclose(coast[0]["r_km"], nominal[-1]["r_km"], atol=1e-3)       # the coast continues the arc
        assert coast[-1]["jd_tdb"] == pytest.approx(plan["run_interval"]["end_jd_tdb"], abs=1e-9)
        for path in (nominal, coast):
            times = [s["jd_tdb"] for s in path]
            assert times == sorted(times)
        # Without a capture burn the ship flies on past Mars instead of stopping there.
        mars = next(b for b in plan["bodies"] if b["body_id"] == "499")
        mars_at_end, _ = hermite_state(mars["states"], coast[-1]["jd_tdb"])
        assert np.linalg.norm(np.array(coast[-1]["r_km"]) - mars_at_end) > 1e5

    def test_planets_cover_the_whole_run_from_nasa_rows(self, plan, track_source):
        start, end = plan["run_interval"]["start_jd_tdb"], plan["run_interval"]["end_jd_tdb"]
        assert [b["body_id"] for b in plan["bodies"]] == ["399", "499"]
        for body in plan["bodies"]:
            times = [s["jd_tdb"] for s in body["states"]]
            assert times[0] <= start and times[-1] >= end
            assert max(np.diff(times)) <= 1.0 + 1e-9                               # daily nodes, no gaps
            assert plan["departure"]["jd_tdb"] in times and plan["arrival"]["jd_tdb"] in times
            for state in body["states"][::37]:
                row = track_source.states(body["body_id"], [state["jd_tdb"]])[0]
                assert list(row.r_km) == state["r_km"]
            hermite_state(body["states"], start), hermite_state(body["states"], end)   # both ends are inside
        assert plan["body_interpolation"]["earth"]["max_error_km"] < 10.0
        assert plan["body_interpolation"]["mars"]["max_error_km"] < 10.0

    def test_fuel_ledger_and_labels(self, plan):
        w, m = plan["wire"], plan["masses"]
        assert w["initial_fuel_g"] == w["departure_fuel_g"] + w["capture_fuel_g"]
        assert 0 <= w["initial_fuel_g"] - m["propellant_required_kg"] * 1000 < 2
        assert m["propellant_required_kg"] <= plan["vehicle"]["propellant_capacity_kg"]
        assert "not a NASA spacecraft" in plan["vehicle"]["label"]
        assert plan["data_mode"] == "nasa_cached"
        assert plan["dv"]["dv_total_km_s"] == pytest.approx(plan["dv"]["dv_depart_km_s"] + plan["dv"]["dv_capture_km_s"])
        sources = plan["provenance"]["sources"]
        assert sources and all(s["sha256"] and s["retrieved_utc"] and "Horizons" in s["name"] for s in sources)
        assert "NASA did not compute or certify this route" in plan["provenance"]["notes"]


def test_an_edited_plan_is_detected():
    plan = copy.deepcopy(stored_plans()[0])
    plan["wire"]["capture_fuel_g"] -= 1
    problems = verify_plan(plan)
    assert any("plan_sha256" in p for p in problems) and any("ledger" in p for p in problems)


def test_a_route_that_misses_mars_is_never_published():
    source = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR))
    constants, grid, vehicle = Constants.from_source(source), GridSpec(n_departures=1, tof_min_days=300.0, n_durations=1), Vehicle()
    cell = run_grid(source, grid, vehicle, constants)[0]
    assert cell.feasible
    cell.vectors["lambert_v1"] = cell.vectors["lambert_v1"] * 1.0001          # a 0.01 % velocity error
    with pytest.raises(PlanRejected):
        build_plan(cell, ["least_fuel"], grid, 1, vehicle, constants, source)
    infeasible = Cell(cell.departure_jd_tdb, cell.arrival_jd_tdb, 300.0, status="exceeds_propellant_capacity")
    with pytest.raises(PlanRejected):
        build_plan(infeasible, ["least_fuel"], grid, 1, vehicle, constants, source)


@pytest.mark.parametrize("ticks", [(0, 100, 200), (10, 10, 200), (10, 300, 200), (10, 12010, 360001)])
def test_invalid_tick_maps_are_refused(ticks):
    with pytest.raises(ValueError):
        TickMap(*ticks)


# ------------------------------------------------------------------ backend hook

DEMO_PARAMS = {"departure_start_utc": "2026-11-15T00:00:00Z", "departure_end_utc": "2027-02-15T00:00:00Z",
               "tof_min_days": 120, "tof_max_days": 360, "n_departures": 24, "n_durations": 25}


def test_run_search_hook_keeps_the_original_small_request_bounded(offline_result):
    seen = []
    plans = run_search(DEMO_PARAMS, seen.append, lambda: False)
    assert plans == offline_result["plans"]  # same bounded request, distinct from the fine catalogue
    assert seen[-1] == 1.0
    assert all(verify_plan(p) == [] for p in plans)


def test_run_search_hook_recomputes_other_requests_with_progress_and_a_new_id():
    seen = []
    one_cell = dict(DEMO_PARAMS, departure_end_utc=DEMO_PARAMS["departure_start_utc"], n_departures=1,
                    tof_min_days=300, tof_max_days=300, n_durations=1)
    plans = run_search(one_cell, seen.append, lambda: False)
    assert len(plans) == 1 and verify_plan(plans[0]) == []
    assert seen == sorted(seen) and seen[0] == 0.0 and seen[-1] == 1.0
    least_fuel = load_demo_plan("least_fuel")
    assert plans[0]["tof_s"] == 300 * 86400  # requested duration remains authoritative
    assert plans[0]["plan_id"] != least_fuel["plan_id"]  # different grid/epochs have a distinct identity


def test_run_search_hook_stops_when_cancelled_and_passes_the_vehicle_through():
    assert run_search(DEMO_PARAMS, lambda f: None, lambda: True) == []
    tiny_tank = dict(DEMO_PARAMS, vehicle={"propellant_capacity_kg": 100.0})
    with pytest.raises(NoFeasibleRoute):
        run_search(tiny_tank, lambda f: None, lambda: False)


def test_plans_folder_holds_only_mission_plans():
    # The backend loads every *.json in app/data/plans as a MissionPlan.
    for path in PLANS_DIR.glob("*.json"):
        assert "plan_sha256" in json.loads(path.read_text(encoding="utf-8")), path.name
