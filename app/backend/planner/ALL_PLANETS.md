# Fine launch windows and 30-second flights (#70)

Rebuild offline with `python -m app.backend.planner.launch_windows` using the
numeric pins in `requirements-core.txt`. No NASA requests occur in this job.
The shipped catalogue contains 38 distinct options over 13 directed routes:
12 Standard options (six routes) and 26 Long-range options (13 routes).
Mars -> Venus is now fuel-feasible for Standard on the finer grid.

The launch and duration axes both step by five TDB days. Inner routes use
336 launches from 2026-11-17 through 2031-06-19 and 113 durations (40–600 days).
Jupiter routes use 182 launches through 2029-05-10 and 241 durations
(100–1300 days). Every launch window exceeds the pair's synodic period,
estimated from its initial cached heliocentric osculating states. Bounds reserve
leading NASA nodes, countdown coverage, the 10% missed-capture tail and the
rounded final interpolation node. This is a bounded grid, not a global optimum.
In particular Jupiter -> Earth least fuel reaches the 1300-day upper duration
bound; a longer-duration search could reduce its fuel further.

`least_fuel` minimizes required propellant; `earliest_arrival` minimizes the
absolute arrival date among tank-feasible cells (fuel breaks ties). Matching
winners share one plan/objective list. Each option carries its actual departure,
arrival, duration, vehicle and grid. Failed routes outside the 13 qualified
pairs retain their prior explicitly recorded coarse-grid outcomes; they were
not silently promoted or described as newly searched. The standard tank is not
relaxed to qualify a long-range route.

Positions use verified raw NASA/JPL Horizons rows where present, otherwise
cubic Hermite interpolation of `app/data/planet_tracks.json`. Plans explicitly
record that source and its semantic hash. Constants remain cached NASA body
GM/radii, not system barycentres. Plan body tracks are checked against **raw
held-out NASA rows**, never against their own interpolant. Mercury uses half-day
nodes; other bodies use daily nodes. Residual (<10 km, <1e-5 km/s), tighter
integration convergence, solar clearance, interpolation (<10 km), integer fuel,
SHA-256 and MissionPlan schema gates remain unchanged. A rejected winner stops
publication instead of substituting a different objective winner.

`FLIGHT_TICKS=3000` is defined in `backend/timescale`. Every stored plan uses
500 / 3500 / 3800: five-second countdown, 30-second flight, three-second tail.
The physical transfer duration still comes from the NASA/Lambert plan. No live
FPGA timing test is claimed. Old plan files are replaced; `search/index.json`
keeps the legacy Earth/Mars loader pointing at current objectives. Ordinary
online planning still accepts at most 25 by 25 cells and recomputes its own
bounded request rather than pretending that it is the fine offline catalogue.

Data size (decimal MB): 40.678 before, 35.976 after, **4.702 MB smaller**.
Plans are serialized compactly with full numerical precision; no raw NASA cache
or validation track was deleted to achieve this. All generated plans together
are 8.55 MB. `search/launch_windows.json` is the machine-readable result table.

## Route table (UTC dates; fuel in kg)

| Shuttle | Route | Objective | Launch | Arrival | Days | Fuel kg |
|---|---|---|---|---|---:|---:|
| Long-range | Mercury → Earth | least_fuel | 2027-01-31 | 2027-05-11 | 100 | 4,311.72 |
| Long-range | Mercury → Earth | earliest_arrival | 2027-01-21 | 2027-04-16 | 85 | 9,783.32 |
| Long-range | Mercury → Mars | least_fuel | 2027-01-26 | 2027-07-30 | 185 | 7,693.19 |
| Long-range | Mercury → Mars | earliest_arrival | 2027-01-26 | 2027-07-05 | 160 | 9,500.37 |
| Standard | Venus → Earth | least_fuel | 2031-06-19 | 2031-12-11 | 175 | 2,251.19 |
| Standard | Venus → Earth | earliest_arrival | 2026-11-17 | 2027-06-05 | 200 | 9,813.53 |
| Long-range | Venus → Earth | least_fuel | 2031-06-19 | 2031-12-11 | 175 | 819.98 |
| Long-range | Venus → Earth | earliest_arrival | 2026-11-17 | 2027-02-15 | 90 | 9,931.57 |
| Standard | Venus → Mars | least_fuel | 2028-08-13 | 2029-05-25 | 285 | 6,672.62 |
| Standard | Venus → Mars | earliest_arrival | 2027-09-08 | 2028-02-05 | 150 | 9,281.83 |
| Long-range | Venus → Mars | least_fuel | 2028-08-13 | 2029-05-25 | 285 | 1,824.02 |
| Long-range | Venus → Mars | earliest_arrival | 2026-11-17 | 2027-03-17 | 120 | 9,805.11 |
| Long-range | Earth → Mercury | least_fuel | 2031-05-10 | 2031-08-28 | 110 | 4,712.68 |
| Long-range | Earth → Mercury | earliest_arrival | 2026-11-17 | 2027-03-12 | 115 | 7,792.24 |
| Standard | Earth → Venus | least_fuel | 2031-05-25 | 2031-10-27 | 155 | 2,262.78 |
| Standard | Earth → Venus | earliest_arrival | 2027-05-11 | 2028-03-11 | 305 | 9,810.82 |
| Long-range | Earth → Venus | least_fuel | 2031-05-25 | 2031-10-27 | 155 | 823.29 |
| Long-range | Earth → Venus | earliest_arrival | 2026-11-17 | 2027-02-05 | 80 | 9,893.08 |
| Standard | Earth → Mars | least_fuel | 2028-11-21 | 2029-09-17 | 300 | 1,945.10 |
| Standard | Earth → Mars | earliest_arrival | 2026-11-17 | 2027-05-06 | 170 | 9,110.89 |
| Long-range | Earth → Mars | least_fuel | 2028-11-21 | 2029-09-17 | 300 | 730.19 |
| Long-range | Earth → Mars | earliest_arrival | 2026-11-17 | 2027-03-17 | 120 | 8,383.15 |
| Long-range | Earth → Jupiter | least_fuel | 2028-12-26 | 2031-12-21 | 1090 | 7,149.17 |
| Long-range | Earth → Jupiter | earliest_arrival | 2026-11-17 | 2029-01-10 | 785 | 9,976.15 |
| Standard | Mars → Venus | least_fuel | 2027-06-20 | 2027-12-27 | 190 | 6,722.62 |
| Standard | Mars → Venus | earliest_arrival | 2027-05-11 | 2027-12-12 | 215 | 9,673.85 |
| Long-range | Mars → Venus | least_fuel | 2027-06-20 | 2027-12-27 | 190 | 1,833.41 |
| Long-range | Mars → Venus | earliest_arrival | 2026-11-17 | 2027-10-28 | 345 | 8,568.99 |
| Standard | Mars → Earth | least_fuel | 2028-08-03 | 2029-07-14 | 345 | 1,930.00 |
| Standard | Mars → Earth | earliest_arrival | 2026-11-17 | 2027-04-21 | 155 | 9,625.77 |
| Long-range | Mars → Earth | least_fuel | 2028-08-03 | 2029-07-14 | 345 | 725.65 |
| Long-range | Mars → Earth | earliest_arrival | 2026-11-17 | 2027-03-07 | 110 | 8,899.19 |
| Long-range | Mars → Jupiter | least_fuel | 2028-10-07 | 2031-07-24 | 1020 | 5,948.29 |
| Long-range | Mars → Jupiter | earliest_arrival | 2028-10-02 | 2030-03-31 | 545 | 9,949.23 |
| Long-range | Jupiter → Earth | least_fuel | 2027-02-05 | 2030-08-28 | 1300 | 7,742.05 |
| Long-range | Jupiter → Earth | earliest_arrival | 2026-11-17 | 2028-06-24 | 585 | 9,962.93 |
| Long-range | Jupiter → Mars | least_fuel | 2028-09-12 | 2032-01-20 | 1225 | 5,301.51 |
| Long-range | Jupiter → Mars | earliest_arrival | 2026-11-17 | 2029-08-13 | 1000 | 9,551.20 |
