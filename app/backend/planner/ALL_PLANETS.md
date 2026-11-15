# Validated route choices and presentation timing (#38)

Human scope update: a good variety for a two-minute presentation, not every
possible route. The catalogue records all pair outcomes, but only seven pairs
are qualified for presentation: Venus->Earth, Venus->Mars, Earth->Venus,
Earth->Mars, Mars->Earth (450 s vehicle), plus Mercury->Earth and Earth->Jupiter
(the explicitly hypothetical 900 s vehicle). Other pairs remain unavailable
or infeasible on their recorded grids. Unused century-long track downloads
were removed; no fabricated routes fill the gaps.

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
to fetch only selected routes serially. The source uses
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
