# Validated route choices and presentation timing (#38)

Human scope update: expand nearby, easily validated choices for a two-minute
presentation, without lengthy Saturn/Uranus/Neptune downloads. The catalogue
now contains **33 flight options across 13 distinct directed routes** (previously
12 options across seven routes). Count options by unique catalogue plan ID,
and routes by origin/destination, independent of vehicle and objective.

| Vehicle | Qualified directed routes | Flight options |
|---|---|---|
| Default 450 s | Venus->Earth/Mars; Earth->Venus/Mars; Mars->Earth | 9 |
| Hypothetical demo vehicle (Isp 900 s) | Mercury->Earth/Mars; Venus->Earth/Mars; Earth->Mercury/Venus/Mars/Jupiter; Mars->Venus/Earth/Jupiter; Jupiter->Earth/Mars | 24 |

The 43 fuel-feasible demo pairs are only a search-stage result: 13 are now
fully qualified, 29 still lack locally cached validation tracks, and one
(Venus->Neptune) fails the independent numerical gate (39.2 km position
residual, 38.6 km convergence difference against a 10 km limit). The other
13/56 demo pairs have no feasible cell on their recorded grids. Missing cache
data is not a claim that NASA lacks data, and fuel feasibility alone is not
mission readiness. No fabricated routes fill the gaps; all default vehicle
failures remain recorded separately.

`plan_pair`, `run_grid`, `Constants.from_source` and `build_plan` accept
`origin_body_id` and `destination_body_id`. `run_search` accepts those keys in its
request mapping. Defaults retain Earth (399) -> Mars (499); `plan_earth_mars`
remains a compatibility wrapper. API request models and filtering belong to the
leader; the frontend belongs to Cursor.

All eight targets use **planet centres** (199, 299, 399, 499, 599, 699, 799, 899),
not planet-system barycentres. This keeps the endpoint and parking-orbit body GM
consistent. Constants come from each target's cached NASA Horizons object-data
page. All parking radii use the existing hypothetical circular 12-hour period
and must clear the sourced mean radius; no surface-launch claims are made.

Run `python -m app.backend.planner.catalog --presentation` and then the same
command with `--demo` to reproduce both catalogues offline. For a deliberate
extension, add `--live --fetch-pair 399:599` (repeat the pair option as needed)
to fetch only selected routes serially. This expansion fetched only
199:499, 299:399, 299:499, 399:199, 399:299, 399:499, 499:299, 499:399,
499:599, 599:399 and 599:499 with `--demo --presentation`; no outer-planet
tracks were downloaded. The source uses
the same validated raw-response/request hashes, units, frame and exact epoch
checks as the Earth/Mars implementation. Mercury uses half-day rather than
daily nodes because daily interpolation failed the unchanged 10 km gate.
No old repository mathematics is used.

`app/data/search/planet_pairs.json` lists every ordered pair. `complete` only
means all 56 records were evaluated, not that all pairs are feasible. Each
record contains its grid, vehicle and either both objective-to-plan-ID mappings
or an explicit reason. `no_feasible_route` means this bounded grid contains no
feasible solved cell. `unavailable` means missing data or a numerical validation
failure; it is not a claim of physical impossibility. Counts distinguish fuel
capacity failures from solver/geometry rejection.

Search design: six departure dates, 73 days apart starting 2026-11-15; eight
durations per pair. Duration bounds are 60–420 days for inner-only pairs,
300–3000 with Jupiter, 600–8000 with Saturn, 1500–20000 with Uranus, and
2000–40000 with Neptune. These broad, deliberately coarse bounds are search
choices, not estimated transfer times. No global optimum is claimed. Existing
Earth/Mars plans retain their original finer grid and exact IDs/digests.

The catalogue uses the original hypothetical 450-second-Isp chemical vehicle.
An infeasible pair is not made available by disabling propellant, solar
intersection, independent DOP853 arrival, convergence or interpolation gates.
A separate leader-approved opt-in vehicle is labelled exactly
`Hypothetical demo vehicle (Isp 900 s)`, with the same masses and tank capacity.
Generate it with `python -m app.backend.planner.catalog --demo --presentation` after the
default run finishes. It writes `demo_pairs` and `demo_complete` in the same
manifest; `pairs` and `complete` always describe the original default vehicle.
Do not run catalogue writers concurrently. Without `--live`, missing track data
is explicitly unavailable. Demo plans have `_demo_` in their filenames and
their own vehicle block; they never replace the original plans or failures.
Presentation plans retain the 100 Hz wire clock, with departure tick 5,
arrival tick 6005 (60.05 seconds) and end tick 6305 (63.05 seconds for a missed
capture). `presentation_plan` doubles simulated seconds per tick while halving
all three tick values: physical epochs, paths and fuel remain identical. New
IDs/digests identify these variants; original Earth/Mars files remain unchanged.
The API/frontend should select the IDs in the catalogue, not legacy plans
whose board duration is over two minutes. Live hardware timing is not yet
qualified here; a software protocol-controller run at speed=1 completed in
60.11 seconds with both burns and the correct fuel ledger.
Far-future UTC strings depend on the time library's leap-second assumptions;
planning and interpolation use TDB epochs, not guessed future UTC offsets.

Offline tests cover all 56 records, schema and digest verification, independent
arrival integration, Venus->Earth, Mars->Earth, Earth->Jupiter and an infeasible
pair. The original two Earth/Mars plan identities are fixed regression values.

NASA API reference: https://ssd-api.jpl.nasa.gov/doc/horizons.html . Cache entries
and each validated plan carry the exact request and response provenance.
