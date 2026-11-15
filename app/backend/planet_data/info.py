"""Build the PlanetInfo card for one planet (contracts schema v1). Read-only, works offline.

Three sections, each with its own provenance so nothing can be mislabelled:
  facts          stable numbers (radius, mass, ...) transcribed from the cached NASA/JPL Horizons pages
  orbital_state  where the planet is at the scene epoch, from the cached NASA vectors
  conditions     dated observations. Earth hazard events (NASA EONET) are not wired in yet and Mars has
                 no current-weather source, so both honestly say 'unavailable'.
Missing data stays null/unavailable. A data problem never raises: the card still opens.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache
from ..ephemeris.horizons import FRAME, HORIZONS_URL, HorizonsError
from ..ephemeris.interp import hermite_state

SCHEMA_VERSION = 1
FACTS_FILE = Path(__file__).resolve().parents[2] / "data" / "planet_facts.json"
PLANS_INDEX = Path(__file__).resolve().parents[2] / "data" / "search" / "index.json"
BODY_NAMES = {"399": "Earth", "499": "Mars"}
MAX_INTERPOLATION_GAP_DAYS = 1.0 + 1e-6      # only interpolate between daily (or closer) NASA rows
AU_KM = 149597870.7


class UnsupportedBody(ValueError):
    code = "UNSUPPORTED_BODY"


@lru_cache(maxsize=1)
def _cache() -> EphemerisCache:
    return EphemerisCache(DEFAULT_CACHE_DIR)


@lru_cache(maxsize=1)
def _facts_dataset() -> dict:
    return json.loads(FACTS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def default_scene_epoch() -> float:
    """Scene epoch used when none is given: departure of the stored least-fuel plan."""
    index = json.loads(PLANS_INDEX.read_text(encoding="utf-8"))
    plan = json.loads((PLANS_INDEX.parent.parent / "plans" / index["objectives"]["least_fuel"]).read_text(encoding="utf-8"))
    return plan["departure"]["jd_tdb"]


def _source(cache: EphemerisCache, file_name: str) -> dict:
    p = cache.provenance(file_name)
    return {"name": f"{p['source_name']} ({file_name})", "url": p["source_url"], "retrieved_utc": p["retrieved_utc"],
            "sha256": p["raw_sha256"], "api_signature": f"{p['api_signature']['source']} v{p['api_signature']['version']}"}


def _facts(body_id: str) -> list[dict]:
    """Facts with their NASA page as source. If the page is not in the cache the list is empty, not invented."""
    try:
        entry = _facts_dataset()["bodies"][body_id]
        source = _source(_cache(), entry["source_file"])
    except (OSError, KeyError, ValueError, HorizonsError):
        return []
    out = []
    for fact in entry["facts"]:
        item = {"key": fact["key"], "label": fact["label"], "value": fact["value"], "unit": fact["unit"], "source": source}
        if "note" in fact:
            item["note"] = fact["note"]
        out.append(item)
    return out


def _no_orbital_state(availability: str, reason: str) -> dict:
    return {"availability": availability, "epoch_jd_tdb": None, "r_km": None, "v_km_s": None, "frame": dict(FRAME),
            "provenance": {"mode": None, "source": None}, "note": reason}


def _orbital_state(body_id: str, jd_tdb: float) -> dict:
    """NASA position/velocity at the scene epoch: an exact cached row, or interpolated between two close rows."""
    try:
        cache = _cache()
        exact = cache.get(body_id, jd_tdb)
        if exact is not None:
            row, file_name = exact
            r, v, method, files = np.array(row.r_km), np.array(row.v_km_s), "exact_cached_nasa_row", [file_name]
        else:
            pair = cache.neighbours(body_id, jd_tdb)
            if pair is None or pair[1][0].jd_tdb - pair[0][0].jd_tdb > MAX_INTERPOLATION_GAP_DAYS:
                return _no_orbital_state("unavailable", "This date is outside the cached NASA/JPL data; nothing was substituted.")
            nodes = [{"jd_tdb": row.jd_tdb, "r_km": row.r_km, "v_km_s": row.v_km_s} for row, _ in pair]
            r, v = hermite_state(nodes, jd_tdb)
            method, files = "cubic_hermite_between_cached_nasa_rows", sorted({f for _, f in pair})
        source = _source(cache, files[0])
    except (OSError, KeyError, ValueError, HorizonsError) as exc:
        return _no_orbital_state("error", f"The NASA cache could not be read ({type(exc).__name__}).")
    distance = float(np.linalg.norm(r))
    return {
        "availability": "available", "epoch_jd_tdb": jd_tdb,
        "r_km": [float(x) for x in r], "v_km_s": [float(x) for x in v], "frame": dict(FRAME),
        "provenance": {"mode": "nasa_cached", "source": source},
        "method": method, "source_files": files,
        "derived": {"distance_from_sun_km": distance, "distance_from_sun_au": distance / AU_KM,
                    "speed_km_s": float(np.linalg.norm(v))},
    }


def _conditions(body_id: str) -> dict:
    blank = {"availability": "unavailable", "delivery": None, "observed_from_utc": None, "observed_to_utc": None,
             "retrieved_utc": None, "items": [], "provenance": {"mode": None, "source": None}}
    if body_id == "399":
        return {"scope": "earth", "kind": "natural_hazard_events", "label": "Earth natural hazard events", **blank,
                "note": "NASA EONET event retrieval is not connected in this build. Unavailable is not an all-clear, "
                        "and such events would be dated observations, not a description of the simulated mission epoch."}
    return {"scope": "mars", "kind": "current_weather", "label": "Mars current weather", **blank,
            "note": "No current Mars weather source is connected. NASA's InSight lander stopped reporting in 2022, "
                    "so its old measurements are not shown as live. The mean temperature above is a long-term average."}


def get_planet_info(body_id: str, scene_epoch_jd_tdb: float | None = None) -> dict:
    """PlanetInfo for Earth '399' or Mars '499' at the scene epoch (Julian date, TDB)."""
    body_id = str(body_id)
    if body_id not in BODY_NAMES:
        raise UnsupportedBody(f"UNSUPPORTED_BODY: only 399 (Earth) and 499 (Mars) have information cards, got {body_id!r}")
    if scene_epoch_jd_tdb is None:
        scene_epoch_jd_tdb = default_scene_epoch()
    scene_epoch_jd_tdb = float(scene_epoch_jd_tdb)
    if not math.isfinite(scene_epoch_jd_tdb):
        raise ValueError("scene_epoch_jd_tdb must be a finite Julian date")
    return {
        "schema_version": SCHEMA_VERSION,
        "body_id": body_id,
        "name": BODY_NAMES[body_id],
        "scene_epoch_jd_tdb": scene_epoch_jd_tdb,
        "facts": _facts(body_id),
        "orbital_state": _orbital_state(body_id, scene_epoch_jd_tdb),
        "conditions": _conditions(body_id),
    }
