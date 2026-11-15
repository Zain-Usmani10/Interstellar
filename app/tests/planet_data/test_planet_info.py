"""PlanetInfo tests. Offline: facts and orbital states come from the checked-in NASA cache."""
import json
from pathlib import Path

import numpy as np
import pytest

from app.backend.ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache
from app.backend.physics.twobody import propagate
from app.backend.planet_data import get_planet_info, info
from app.backend.planner.demo import load_demo_plan

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas"
FACTS = json.loads(info.FACTS_FILE.read_text(encoding="utf-8"))
PLAN = load_demo_plan("least_fuel")
DEPARTURE, ARRIVAL = PLAN["departure"]["jd_tdb"], PLAN["arrival"]["jd_tdb"]


def squash(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("body_id", ["399", "499"])
def test_every_fact_is_literally_in_the_cached_nasa_page(body_id):
    entry = FACTS["bodies"][body_id]
    page = json.loads((DEFAULT_CACHE_DIR / entry["source_file"]).read_text(encoding="utf-8"))
    text = squash(json.loads(page["raw_response"])["result"])
    assert len(entry["facts"]) >= 8
    for fact in entry["facts"]:
        assert squash(fact["quote"]) in text, f"{fact['key']}: quote not found in the NASA page"
        digits = fact["quote"].split("=")[-1]
        mantissa = f"{fact['value']:.10g}".split("e")[0].rstrip("0").rstrip(".")
        assert mantissa in digits, f"{fact['key']}: value {fact['value']} does not match the quoted NASA text"


@pytest.mark.parametrize("body_id, name", [("399", "Earth"), ("499", "Mars")])
def test_card_has_sourced_facts_with_units(body_id, name):
    card = get_planet_info(body_id, DEPARTURE)
    assert card["schema_version"] == 1 and card["body_id"] == body_id and card["name"] == name
    keys = [f["key"] for f in card["facts"]]
    assert len(keys) == len(set(keys)) and {"mean_radius", "mass", "mean_temperature", "orbital_period"} <= set(keys)
    for fact in card["facts"]:
        assert fact["unit"] and fact["value"] is not None
        assert fact["source"]["url"].startswith("https://ssd.jpl.nasa.gov") and fact["source"]["sha256"]
        assert fact["source"]["retrieved_utc"] and "Horizons" in fact["source"]["name"]
    temperature = next(f for f in card["facts"] if f["key"] == "mean_temperature")
    assert temperature["unit"] == "K" and "not a current weather reading" in temperature["note"]
    assert "quote" not in card["facts"][0]


@pytest.mark.parametrize("body_id", ["399", "499"])
def test_card_matches_the_contract_schema(body_id):
    if not SCHEMA_DIR.is_dir():
        pytest.skip("app/contracts/schemas not on this branch yet (lands with contracts v1, PR #9)")
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    schemas = [json.loads(f.read_text(encoding="utf-8")) for f in SCHEMA_DIR.glob("*.json")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    validator = Draft202012Validator(next(s for s in schemas if s.get("title") == "PlanetInfo"), registry=registry)
    for epoch in (None, DEPARTURE, DEPARTURE + 0.37, 2440000.5):          # default, exact, interpolated, unavailable
        assert [e.message for e in validator.iter_errors(get_planet_info(body_id, epoch))] == []


def test_orbital_state_at_a_cached_epoch_is_the_exact_nasa_row():
    earth = get_planet_info("399", DEPARTURE)["orbital_state"]
    assert earth["availability"] == "available" and earth["method"] == "exact_cached_nasa_row"
    assert earth["r_km"] == PLAN["boundary"]["origin_r_km"] and earth["v_km_s"] == PLAN["boundary"]["origin_v_km_s"]
    assert earth["epoch_jd_tdb"] == DEPARTURE
    assert earth["frame"] == {"center": "500@10", "ref_system": "ICRF", "ref_plane": "ECLIPTIC", "units": "KM-S", "time_scale": "TDB"}
    assert earth["provenance"]["mode"] == "nasa_cached" and earth["provenance"]["source"]["sha256"]
    assert 0.98 < earth["derived"]["distance_from_sun_au"] < 1.02
    mars = get_planet_info("499", ARRIVAL)["orbital_state"]
    assert mars["r_km"] == PLAN["boundary"]["destination_r_km"]
    assert 1.38 < mars["derived"]["distance_from_sun_au"] < 1.67


def test_orbital_state_between_daily_rows_is_interpolated_and_physically_consistent():
    # Independent check: let Mars coast under the Sun's gravity from the previous NASA row for 0.37 days.
    mars_nodes = next(b for b in PLAN["bodies"] if b["body_id"] == "499")["states"]
    node = mars_nodes[40]
    epoch = node["jd_tdb"] + 0.37
    state = get_planet_info("499", epoch)["orbital_state"]
    assert state["availability"] == "available" and state["method"] == "cubic_hermite_between_cached_nasa_rows"
    coasted, _ = propagate(PLAN["constants"]["mu_sun_km3_s2"], node["r_km"], node["v_km_s"], 0.37 * 86400).state(0.37 * 86400)
    assert np.linalg.norm(np.array(state["r_km"]) - coasted) < 5.0      # km, out of ~2e8 km from the Sun
    assert state["provenance"]["mode"] == "nasa_cached" and state["epoch_jd_tdb"] == epoch


@pytest.mark.parametrize("boundary,offset", [(0, -400.0), (0, -1.0), (1, 400.0)])
def test_orbital_state_outside_the_cache_is_unavailable_not_invented(boundary, offset):
    # New qualified routes extend the cache beyond the original Mars arrival.
    epoch = info._cache().epoch_bounds("499")[boundary] + offset
    card = get_planet_info("499", epoch)
    state = card["orbital_state"]
    assert state["availability"] == "unavailable"
    assert state["r_km"] is None and state["v_km_s"] is None and state["epoch_jd_tdb"] is None
    assert state["provenance"] == {"mode": None, "source": None}
    assert card["facts"] and card["scene_epoch_jd_tdb"] == epoch       # the rest of the card still works


def test_sparse_cached_rows_are_not_interpolated_across_large_gaps():
    # The catalogue expands the cache; choose an actual remaining sparse gap
    # instead of assuming the original Earth/Mars search's last date is sparse.
    cache = info._cache()
    epochs = sorted(row.jd_tdb for (body, _), (row, _) in cache._rows.items() if body == "499")
    left, right = next((a, b) for a, b in zip(epochs, epochs[1:]) if b-a > 2)
    assert get_planet_info("499", left)["orbital_state"]["availability"] == "available"
    assert get_planet_info("499", (left+right)/2)["orbital_state"]["availability"] == "unavailable"


def test_conditions_are_honest_per_planet(monkeypatch):
    monkeypatch.delenv("INTERSTELLAR_EONET_LIVE", raising=False)          # offline: the saved snapshot
    info.eonet.reset_memory()
    earth = get_planet_info("399", DEPARTURE)["conditions"]
    assert earth["scope"] == "earth" and earth["kind"] == "natural_hazard_events"
    assert earth["label"] == "Earth natural hazard events"
    assert earth["availability"] in ("available", "empty") and earth["delivery"] == "cached"
    assert earth["provenance"]["mode"] == "nasa_cached" and "EONET" in earth["provenance"]["source"]["name"]
    assert "not an all-clear" in earth["note"] and "NOT LIVE" in earth["note"]
    mars = get_planet_info("499", DEPARTURE)["conditions"]
    assert mars["scope"] == "mars" and mars["kind"] == "current_weather"
    assert mars["availability"] == "unavailable" and mars["items"] == [] and mars["delivery"] is None
    assert "InSight" in mars["note"] and "2022" in mars["note"]
    assert mars["retrieved_utc"] is None and mars["provenance"] == {"mode": None, "source": None}


def test_a_hazard_data_crash_does_not_break_the_earth_card(monkeypatch):
    def crash():
        raise RuntimeError("boom")
    monkeypatch.setattr(info.eonet, "earth_conditions", crash)
    card = get_planet_info("399", DEPARTURE)
    assert card["conditions"]["availability"] == "error" and card["conditions"]["items"] == []
    assert "not zero hazards" in card["conditions"]["note"]
    assert card["facts"] and card["orbital_state"]["availability"] == "available"


def test_default_epoch_and_bad_input():
    assert get_planet_info("399")["scene_epoch_jd_tdb"] == DEPARTURE
    assert get_planet_info(399, DEPARTURE)["body_id"] == "399"
    for bad in ("299", "earth", ""):
        with pytest.raises(ValueError):
            get_planet_info(bad, DEPARTURE)
    with pytest.raises(ValueError):
        get_planet_info("399", float("nan"))


def test_a_broken_cache_gives_an_error_section_but_the_card_still_opens(monkeypatch, tmp_path):
    def broken():
        raise OSError("disk gone")
    monkeypatch.setattr(info, "_cache", broken)
    card = get_planet_info("399", DEPARTURE)
    assert card["orbital_state"]["availability"] == "error" and card["orbital_state"]["r_km"] is None
    assert card["facts"] == [] and card["name"] == "Earth"
