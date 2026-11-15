"""Regenerate the 13 qualified pairs offline: python -m app.backend.planner.launch_windows.

The online GridSpec/API stays limited to 25x25. This explicit offline job searches
the full stored interval that leaves room for the longest flight and missed capture.
"""
from dataclasses import asdict, dataclass
import json
import math
import uuid

import numpy as np

from ..ephemeris.track_source import TrackSource
from ..ephemeris.timeconv import utc_to_jd_tdb
from ..physics.burns import Vehicle, propellant_for
from ..runtime.stores import load_validators
from .catalog import DEMO_VEHICLE
from .demo import PLANS_DIR, SEARCH_DIR
from .plan import build_plan, plan_digest, verify_plan, _PLAN_NAMESPACE
from .search import GridSpec, Constants, run_grid, select_winners, NoFeasibleRoute

PAIRS = (('199', '399'), ('199', '499'), ('299', '399'), ('299', '499'),
         ('399', '199'), ('399', '299'), ('399', '499'), ('399', '599'),
         ('499', '299'), ('499', '399'), ('499', '599'), ('599', '399'), ('599', '499'))


@dataclass(frozen=True)
class CatalogueGrid(GridSpec):
    def __post_init__(self):
        if any(type(n) is not int or not 1 <= n <= 1000 for n in (self.n_departures, self.n_durations)):
            raise ValueError('offline grid axes must have 1..1000 points')
        if not all(math.isfinite(x) and x > 0 for x in
                   (self.departure_step_days, self.tof_min_days, self.tof_step_days)):
            raise ValueError('grid steps must be finite and positive')


def synodic_days(source, pair, mu):
    """Estimate periods from the cached initial heliocentric osculating states."""
    periods = []
    for body in pair:
        state = source.states(body, [source.track['start_jd_tdb']])[0]
        r, v = np.asarray(state.r_km), np.asarray(state.v_km_s)
        a = 1 / (2 / np.linalg.norm(r) - v @ v / mu)
        periods.append(2 * math.pi * math.sqrt(a**3 / mu) / 86400)
    return 1 / abs(1 / periods[0] - 1 / periods[1])


def window_grid(source, pair):
    low, high = (100, 1300) if '599' in pair else (40, 600)
    start_utc = "2026-11-17T00:00:00Z"  # reserve leading NASA nodes and real countdown
    start = utc_to_jd_tdb(start_utc)
    # Full rectangular grid; reserve the 10% uncaptured coast and rounded daily nodes.
    last = source.track['end_jd_tdb'] - 1.1 * high - 2
    count = math.floor((last - start) / 5) + 1
    grid = CatalogueGrid(departure_start_utc=start_utc, departure_step_days=5, n_departures=count,
                         tof_min_days=low, tof_step_days=5, n_durations=(high-low)//5+1)
    synodic = synodic_days(source, pair, Constants.from_source(source, *pair).mu_sun)
    if (count-1)*5 < synodic:
        raise ValueError(f'{pair}: stored range cannot cover a full synodic period')
    return grid, synodic


def regenerate():
    source = TrackSource()
    manifest_path = SEARCH_DIR / 'planet_pairs.json'
    manifest = json.loads(manifest_path.read_text())
    plans, table = {}, []
    for pair in PAIRS:
        source.files_used.clear()
        source.interpolated.clear()
        for key, vehicle in [('pairs', Vehicle()), ('demo_pairs', DEMO_VEHICLE)]:
            grid, synodic = window_grid(source, pair)
            constants = Constants.from_source(source, *pair)
            print(f'{key} {pair}: {grid.n_departures}x{grid.n_durations}', flush=True)
            if key == 'pairs':
                cells = run_grid(source, grid, vehicle, constants,
                                 origin_body_id=pair[0], destination_body_id=pair[1])
            else:
                # Same geometry and burns; only the rocket equation changes with Isp.
                for cell in cells:
                    if cell.status in ('ok', 'exceeds_propellant_capacity'):
                        cell.propellant = propellant_for(cell.dv_depart, cell.dv_capture, vehicle)
                        cell.feasible = cell.propellant.feasible
                        cell.status = 'ok' if cell.feasible else 'exceeds_propellant_capacity' 
            record = dict(origin_body_id=pair[0], destination_body_id=pair[1],
                          grid=asdict(grid), vehicle=asdict(vehicle),
                          position_reference='NASA planet centres; cached rows or validated Hermite track',
                          scope='best within recorded 5-day grid; not a global optimum',
                          synodic_period_days=synodic)
            try:
                winners = select_winners(cells)
            except NoFeasibleRoute as error:
                record.update(status='no_feasible_route', reason_code=error.code,
                              reason=str(error), rejection_counts=error.rejection_counts)
            else:
                mapping = {}
                for objective, cell in winners.items():
                    if objective in mapping:
                        continue
                    won = [name for name, candidate in winners.items() if candidate is cell]
                    # A failed winner stops publication, rather than silently choosing a worse cell.
                    plan = build_plan(cell, won, grid, sum(c.feasible for c in cells),
                                      vehicle, constants, source,
                                      origin_body_id=pair[0], destination_body_id=pair[1])
                    plan['provenance']['notes'] += (
                        ' Fine-grid search uses raw cached NASA rows where present, otherwise cubic Hermite '
                        'interpolation of app/data/planet_tracks.json (hash in sources). Body-track held-out '
                        'checks use independent raw NASA rows, never values interpolated from the same track. '
                        'Five-day launch and duration steps; no global optimum claimed.')
                    plan.pop('plan_id')
                    plan.pop('plan_sha256')
                    plan['plan_id'] = str(uuid.uuid5(_PLAN_NAMESPACE, plan_digest(plan)))
                    plan['plan_sha256'] = plan_digest(plan)
                    if verify_plan(plan):
                        raise ValueError(verify_plan(plan))
                    name = f'mission_plan_{pair[0]}_{pair[1]}_{key}_{won[0]}.json'
                    plans[name] = plan
                    for obj in won:
                        mapping[obj] = plan['plan_id']
                        table.append([key, '->'.join(pair), obj, plan['departure']['utc'],
                                      plan['arrival']['utc'], cell.tof_days, round(cell.propellant.required_kg, 2)])
                record.update(status='validated', objectives=mapping)
            index = next(i for i, r in enumerate(manifest[key])
                         if (r['origin_body_id'], r['destination_body_id']) == pair)
            manifest[key][index] = record
            print(f"  {record['status']}", flush=True)
    # Validate everything before replacing any shipped catalogue file.
    validator = load_validators()['mission_plan']
    for plan in plans.values():
        validator.validate(plan)
    manifest['presentation_max_seconds'] = 38
    # Only previously qualified pairs are regenerated; other recorded failures remain honest history.
    for path in PLANS_DIR.glob('*.json'):
        path.unlink()
    for name, plan in plans.items():
        (PLANS_DIR / name).write_text(json.dumps(plan, separators=(',', ':'))+'\n')
    manifest_path.write_text(json.dumps(manifest, indent=1)+'\n')
    earth = {obj: name for name, p in plans.items()
             if p['origin_body_id'] == '399' and p['destination_body_id'] == '499' and p['vehicle']['isp_s'] == 450
             for obj in p['objectives_won']}
    # Legacy loader still resolves objectives, but the old 600-cell request is no longer this catalogue.
    (SEARCH_DIR / 'index.json').write_text(json.dumps({'objectives': earth,
        'grid': 'launch_windows.json', 'built_from': {'offline_catalogue': True}}, indent=1)+'\n')
    (SEARCH_DIR / 'launch_windows.json').write_text(json.dumps({'columns':
        ['class', 'route', 'objective', 'departure_utc', 'arrival_utc', 'days', 'fuel_kg'], 'rows': table}, indent=1)+'\n')
    print(f'Wrote {len(plans)} plans; {sum(p.stat().st_size for p in PLANS_DIR.glob("*.json"))/1e6:.2f} MB', flush=True)


if __name__ == '__main__':
    regenerate()
