# All-planet bounded route catalogue (#38)

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

Run `python -m app.backend.planner.catalog --live` once to fetch missing states
serially. Run without `--live` to repeat using the cache alone. The source uses
the same validated raw-response/request hashes, units, frame and exact epoch
checks as the Earth/Mars implementation. No old repository mathematics is used.

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
A separate 900-second-Isp demo vehicle has been proposed to the leader; it is
not silently substituted. Board timing remains 100 Hz, departure tick 10,
arrival tick 12010 and end tick 12610, regardless of simulated flight duration.
Far-future UTC strings depend on the time library's leap-second assumptions;
planning and interpolation use TDB epochs, not guessed future UTC offsets.

Offline tests cover all 56 records, schema and digest verification, independent
arrival integration, Venus->Earth, Mars->Earth, Earth->Jupiter and an infeasible
pair. The original two Earth/Mars plan identities are fixed regression values.

NASA API reference: https://ssd-api.jpl.nasa.gov/doc/horizons.html . Cache entries
and each validated plan carry the exact request and response provenance.
