"""Dated all-planet scene positions, with NASA midpoint validation and no extrapolation.

Build: python -m app.backend.ephemeris.planet_tracks --live
Uniform ranges use Horizons START_TIME/STOP_TIME/STEP_SIZE to avoid long TLIST
URLs (https://ssd-api.jpl.nasa.gov/doc/horizons.html). Requests use the existing
serialized client and verified raw-response cache.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .cache import DEFAULT_CACHE_DIR, EphemerisCache, EphemerisSource, EphemerisUnavailable
from .horizons import PLANET_IDS, FRAME, build_vector_request, HorizonsClient
from .interp import hermite_state

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TRACK_PATH = DATA_DIR / "planet_tracks.json"
TRACK_CACHE_DIR = DATA_DIR / "planet_track_cache"


def _range(source, body, start, stop, spacing):
    epochs = [start + i * spacing for i in range(round((stop - start) / spacing) + 1)]
    if any(source.cache.get(body, epoch) is None for epoch in epochs):
        if source.client is None:
            raise EphemerisUnavailable(f"missing planet track for {body}; rebuild with --live")
        request = build_vector_request(body, [start])
        request.pop("TLIST")
        request.pop("TLIST_TYPE", None)
        request.update(START_TIME=f"'JD{start:.9f}'", STOP_TIME=f"'JD{stop:.9f}'",
                       STEP_SIZE=f"'{round(spacing * 24 * 60)} m'")
        raw, retrieved = source.client.get(request)
        source.cache.store(body, "vectors", request, raw, retrieved, epochs)
    return source.states(body, epochs)


def build_tracks(live=False, output_path=TRACK_PATH):
    plans = [json.loads(path.read_text()) for path in (DATA_DIR / "plans").glob("*.json")]
    start = math.floor(min(p["run_interval"]["start_jd_tdb"] for p in plans) - 0.5) + 0.5
    stop = math.ceil(max(p["run_interval"]["end_jd_tdb"] for p in plans) - 0.5) + 0.5
    # Isolate enrichment from the planner cache so adding tracks cannot change
    # which raw response supplies an existing plan's provenance.
    source = EphemerisSource(EphemerisCache(TRACK_CACHE_DIR, fallback_directory=DEFAULT_CACHE_DIR),
                             HorizonsClient() if live else None)
    bodies = []
    for body in PLANET_IDS:
        spacing = 0.5 if body == "199" else 1.0
        for attempt in range(4):
            print(f"{body}: {spacing} day nodes + independent midpoints", flush=True)
            nodes = _range(source, body, start, stop, spacing)
            checks = _range(source, body, start + spacing / 2, stop - spacing / 2, spacing)
            states = [{"jd_tdb": r.jd_tdb, "r_km": list(r.r_km), "v_km_s": list(r.v_km_s)} for r in nodes]
            errors = [float(np.linalg.norm(hermite_state(states, r.jd_tdb)[0] - r.r_km)) for r in checks]
            maximum = max(errors)
            if maximum < 10:
                break
            spacing /= 2
        else:
            raise ValueError(f"{body}: interpolation gate failed ({maximum} km)")
        bodies.append({"body_id": body, "states": states, "node_spacing_days": spacing,
                       "validation": {"n_held_out": len(checks), "max_error_km": maximum, "limit_km": 10}})
        print(f"  validated {len(checks)} midpoints, max {maximum:.4f} km", flush=True)
    result = {"version": 1, "data_mode": "nasa_cached", "frame": FRAME,
              "start_jd_tdb": start, "end_jd_tdb": stop, "bodies": bodies,
              "provenance": source.sources()}
    result["sha256"] = _digest(result)
    Path(output_path).write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    return result


def _digest(value):
    body = {k: v for k, v in value.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@lru_cache(maxsize=1)
def load_tracks(path=TRACK_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("sha256") != _digest(value) or value.get("frame") != FRAME:
        raise ValueError("planet track integrity/frame mismatch")
    if {b["body_id"] for b in value["bodies"]} != set(PLANET_IDS):
        raise ValueError("planet track must contain all eight planets")
    return value


def planet_positions(jd_tdb: float, path=TRACK_PATH) -> dict:
    """Backend hook. Positions/velocities share one TDB date and frame."""
    tracks = load_tracks(path)
    if not math.isfinite(jd_tdb) or not tracks["start_jd_tdb"] <= jd_tdb <= tracks["end_jd_tdb"]:
        raise EphemerisUnavailable("date outside the validated all-planet track")
    planets = []
    for body in tracks["bodies"]:
        r, v = hermite_state(body["states"], jd_tdb)
        planets.append({"body_id": body["body_id"], "r_km": list(r), "v_km_s": list(v)})
    return {"epoch_jd_tdb": jd_tdb, "frame": tracks["frame"], "data_mode": "nasa_cached",
            "planets": planets, "track_sha256": tracks["sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    build_tracks(parser.parse_args().live)
