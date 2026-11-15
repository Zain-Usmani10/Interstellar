import json
import math

import numpy as np
import pytest

from app.backend.ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache, EphemerisUnavailable
from app.backend.ephemeris.horizons import PLANET_IDS
from app.backend.ephemeris.planet_tracks import load_tracks, planet_positions, DATA_DIR, TRACK_CACHE_DIR


def test_tracks_cover_every_catalogue_interval_and_all_planets():
    tracks = load_tracks()
    for path in (DATA_DIR / "plans").glob("*.json"):
        plan = json.loads(path.read_text())
        for jd in (plan["run_interval"]["start_jd_tdb"], plan["run_interval"]["end_jd_tdb"]):
            value = planet_positions(jd)
            assert {p["body_id"] for p in value["planets"]} == set(PLANET_IDS)
            assert all(math.isfinite(n) for p in value["planets"] for n in p["r_km"] + p["v_km_s"])
    assert tracks["data_mode"] == "nasa_cached"


def test_track_interpolation_against_independent_cached_nasa_midpoints():
    tracks, cache = load_tracks(), EphemerisCache(TRACK_CACHE_DIR, fallback_directory=DEFAULT_CACHE_DIR)
    for body in tracks["bodies"]:
        assert body["validation"]["max_error_km"] < 10
        states = body["states"]
        # Spread a fresh offline sample across the complete interval.
        for index in np.linspace(0, len(states) - 2, 24, dtype=int):
            jd = (states[index]["jd_tdb"] + states[index + 1]["jd_tdb"]) / 2
            truth, _ = cache.get(body["body_id"], jd)
            observed = next(p for p in planet_positions(jd)["planets"] if p["body_id"] == body["body_id"])
            assert np.linalg.norm(np.array(observed["r_km"]) - truth.r_km) < 10


@pytest.mark.parametrize("jd", [float("nan"), float("inf"), 0, 9999999])
def test_track_never_extrapolates(jd):
    with pytest.raises(EphemerisUnavailable):
        planet_positions(jd)
