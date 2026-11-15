"""Offline catalogue coverage, integrity and generic pair boundaries."""
import json

import pytest
import numpy as np

from app.backend.ephemeris.horizons import PLANET_IDS, build_vector_request
from app.backend.planner.demo import PLANS_DIR, SEARCH_DIR, load_demo_plan, run_search
from app.backend.planner.plan import verify_plan
from app.backend.planner.search import validate_pair
from app.backend.runtime.stores import load_validators
from app.backend.ephemeris.cache import EphemerisCache, EphemerisSource
from app.backend.planner.catalog import pair_grid
from app.backend.planner.search import Constants, run_grid
from app.backend.physics.burns import Vehicle
from app.backend.physics.twobody import propagate


@pytest.mark.parametrize("body", PLANET_IDS)
def test_all_planet_centres_supported(body):
    assert build_vector_request(body, [2461359.5])["COMMAND"] == f"'{body}'"


@pytest.mark.parametrize("pair", [("399", "399"), ("999", "399"), ("3", "499")])
def test_invalid_pairs_refused(pair):
    with pytest.raises(ValueError):
        validate_pair(*pair)


def test_original_earth_mars_identities_unchanged():
    expected = {
        "least_fuel": ("a3d74b41-a59e-587b-9454-4d1c8695b100", "808801a450cb2845b6692dd511ff1acb655599a5282e421c4dfa877d57a51ac0"),
        "earliest_arrival": ("f4f9cac8-e8be-5e07-9a0c-0987815d937b", "5e70bbb7a82d54db4ebbba6b6322cf1c5baf332fa7d222fcfe9e3a8a012c6d39"),
    }
    for objective, identity in expected.items():
        plan = load_demo_plan(objective)
        assert (plan["plan_id"], plan["plan_sha256"]) == identity


def test_catalog_all_56_pairs_and_valid_plans():
    catalog = json.loads((SEARCH_DIR / "planet_pairs.json").read_text())
    assert catalog["complete"]
    pairs = {(r["origin_body_id"], r["destination_body_id"]): r for r in catalog["pairs"]}
    assert len(catalog["pairs"]) == len(pairs) == 56
    assert set(pairs) == {(a, b) for a in PLANET_IDS for b in PLANET_IDS if a != b}
    plans = {p["plan_id"]: p for path in PLANS_DIR.glob("*.json") for p in [json.loads(path.read_text())]}
    validator = load_validators()["mission_plan"]
    for pair, row in pairs.items():
        if row["status"] != "validated":
            assert row["status"] in ("no_feasible_route", "unavailable")
            assert row["reason"] and row["reason_code"]
            if row["status"] == "no_feasible_route":
                assert sum(row["rejection_counts"].values()) == row["grid"]["n_departures"] * row["grid"]["n_durations"]
            continue
        assert set(row["objectives"]) == {"least_fuel", "earliest_arrival"}
        modes = set()
        for objective, plan_id in row["objectives"].items():
            plan = plans[plan_id]
            validator.validate(plan)
            assert not verify_plan(plan)
            assert (plan["origin_body_id"], plan["destination_body_id"]) == pair
            assert objective in plan["objectives_won"]
            coast = propagate(plan["constants"]["mu_sun_km3_s2"],
                              plan["boundary"]["origin_r_km"],
                              plan["boundary"]["lambert_v1_km_s"], plan["tof_s"])
            r, v = coast.state(plan["tof_s"])
            assert np.linalg.norm(r - plan["boundary"]["destination_r_km"]) < 10
            assert np.linalg.norm(v - plan["boundary"]["lambert_v2_km_s"]) < 1e-5
            modes.add(plan["data_mode"])
        assert modes == {"nasa_cached"}


@pytest.mark.parametrize("pair", [("299", "399"), ("499", "399"), ("399", "599"), ("199", "899")])
def test_representative_pairs_have_explicit_outcomes(pair):
    rows = json.loads((SEARCH_DIR / "planet_pairs.json").read_text())["pairs"]
    row = next(r for r in rows if (r["origin_body_id"], r["destination_body_id"]) == pair)
    if pair in (("299", "399"), ("499", "399")):
        assert row["status"] == "validated"
    else:
        assert row["status"] in ("validated", "no_feasible_route", "unavailable")
    source = EphemerisSource(EphemerisCache())
    constants = Constants.from_source(source, *pair)
    cells = run_grid(source, pair_grid(*pair), Vehicle(), constants,
                     origin_body_id=pair[0], destination_body_id=pair[1])
    assert any(c.feasible for c in cells) == (row["status"] == "validated")


def test_run_search_uses_requested_pair_offline(monkeypatch):
    monkeypatch.delenv("INTERSTELLAR_NASA_LIVE", raising=False)
    plans = run_search({"origin_body_id": "299", "destination_body_id": "399",
                        "departure_start_utc": "2026-11-15T00:00:00Z",
                        "departure_end_utc": "2027-11-15T00:00:00Z",
                        "n_departures": 6, "n_durations": 8,
                        "tof_min_days": 60, "tof_max_days": 420})
    assert plans
    assert all(p["origin_body_id"] == "299" and p["destination_body_id"] == "399"
               and p["data_mode"] == "nasa_cached" for p in plans)
