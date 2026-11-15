# app/data: NASA cache and validated demo plans

Owner: `@sadattanzim01/claude`.

| Path | What |
|---|---|
| `ephemeris/horizons_*.json` | Raw NASA/JPL Horizons replies (Earth 399, Mars 499, Sun 10) with the exact request, retrieval time (UTC), API signature, source URL and SHA-256. Loaded files are re-parsed and hash-checked; an edited file is refused. |
| `plans/mission_plan_earth_mars_<objective>.json` | Validated `MissionPlan` (contracts schema v1), `data_mode: "nasa_cached"`. Only MissionPlans go in this folder: the backend loads every `*.json` here. |
| `search/grid_earth_mars.json` | Every cell of the searched grid (departure, arrival, delta-v, propellant, feasible or why not). |
| `planet_facts.json` | Stable Earth/Mars facts transcribed from the cached Horizons object-data pages; each has the exact quoted NASA text and a test checks it is really in the page. |
| `eonet/earth_events_snapshot.json` | One real NASA EONET v3 reply (open severe storms + wildfires, last 30 days, max 20) with URL, retrieval time and SHA-256. Shown as a dated, not-live snapshot when live fetch is off or fails. Refresh: `python -m app.backend.planet_data.eonet --refresh`. |
| `search/index.json` | Objective -> plan file. |

Planet positions, velocities and GM values are NASA data. The transfer arc, burns and propellant are
computed by this project with a simplified model (Sun-only two-body coast, impulsive burns from
12-hour parking orbits). NASA did not compute or certify these routes. Recommendations are the best
**within the searched grid** only.

## Commands (repo root)

```
python -m app.backend.planner.demo            # rebuild plans from the cache only (no network)
python -m app.backend.planner.demo --live     # fetch missing NASA data first, one request at a time
python -m pytest app/tests/ephemeris app/tests/physics app/tests/planner app/tests/planet_data
```

Use from code:

```python
from app.backend.planner.demo import load_demo_plan
plan = load_demo_plan("least_fuel")           # or "earliest_arrival"; digest and gates re-verified on load

from app.backend.planet_data import get_planet_info   # get_planet_info("499", scene_epoch_jd_tdb) -> PlanetInfo card
from app.backend.planner import run_search     # backend hook: run_search(params, progress, cancelled) -> [MissionPlan]
```

Dates outside the cached range raise `EPHEMERIS_UNAVAILABLE` offline; nothing is substituted.
`run_search` stays offline unless `INTERSTELLAR_NASA_LIVE=1` is set.
Earth hazard events stay on the saved snapshot unless `INTERSTELLAR_EONET_LIVE=1` is set (then: one bounded request, reused for 15 minutes).

Dependencies: numpy, scipy, astropy, httpx, `lamberthub==1.0.0` (GPL-3.0; its package metadata says otherwise, the LICENSE file is GPL-3.0).


## Retimed catalogue and all-planet tracks (#46)

Every stored plan now uses departure/arrival/end ticks 500/6500/6800. All plan
identities changed, including the two legacy Earth/Mars ids. Nine slower duplicate
files were removed; 33 plans remain. Physical paths, burns and fuel are unchanged.
`python -m app.backend.planner.retime` reapplies the migration idempotently.

`planet_tracks.json` covers JD TDB 2461359.5 through 2463700.5 for all eight
planet centres in the existing Sun-centred ICRF/ecliptic KM-S frame. Mercury uses
half-day nodes; other planets use daily nodes. Every interval was checked against
a separately requested NASA midpoint (21,069 checks; maximum 7.152 km, Jupiter).
This is an interpolation consistency gate, not spacecraft navigation accuracy.
The track has a content digest and source provenance. Raw replies are in
`planet_track_cache/`, deliberately isolated from the planner cache so a newly
fetched overlapping epoch cannot alter old plan provenance. Some already-cached
rows are reused from `ephemeris/` and retain their original source filenames.

Backend hook: `app.backend.ephemeris.planet_tracks.planet_positions(jd_tdb)`
returns the common date/frame and eight `{body_id,r_km,v_km_s}` entries. Out-of-range
or nonfinite dates raise `EPHEMERIS_UNAVAILABLE`; no extrapolation or synthetic
fallback is used. Build with `python -m app.backend.ephemeris.planet_tracks`
(offline) or add `--live` to fetch missing ranges through the serialized client.
