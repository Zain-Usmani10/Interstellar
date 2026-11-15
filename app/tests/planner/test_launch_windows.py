"""Offline fine-grid coverage and independent NASA interpolation checks."""
import json
import math

import numpy as np
import pytest

from app.backend.ephemeris.cache import EphemerisUnavailable
from app.backend.ephemeris.interp import hermite_state
from app.backend.ephemeris.track_source import TrackSource
from app.backend.planner.demo import SEARCH_DIR, PLANS_DIR
from app.backend.planner.launch_windows import PAIRS, window_grid, CatalogueGrid
from app.backend.planner.search import GridSpec


@pytest.fixture(scope='module')
def source():
    return TrackSource()


def test_window_covers_synodic_period_and_keeps_countdown_and_tail_inside_cache(source):
    for pair in PAIRS:
        grid, period = window_grid(source, pair)
        dates = grid.departure_epochs()
        assert grid.departure_step_days <= 5 and grid.tof_step_days <= 5
        assert dates[-1] - dates[0] >= period
        assert math.floor(dates[0] - grid.tof_max_days / 1200 - 0.5) + 0.5 >= source.track['start_jd_tdb']
        assert math.ceil(dates[-1] + 1.1 * grid.tof_max_days - 0.5) + 0.5 <= source.track['end_jd_tdb']


def test_online_grid_stays_small_and_offline_grid_is_bounded():
    with pytest.raises(ValueError):
        GridSpec(n_departures=26)
    with pytest.raises(ValueError):
        CatalogueGrid(n_departures=1001)
    with pytest.raises(ValueError):
        CatalogueGrid(tof_step_days=float('nan'))


def test_track_fallback_is_labeled_and_validation_cannot_use_interpolation(source):
    epoch = source.track['start_jd_tdb'] + 0.123456
    row = source.states('399', [epoch])[0]
    r, v = hermite_state(source.bodies['399']['states'][:2], row.jd_tdb)
    np.testing.assert_allclose(row.r_km, r)
    np.testing.assert_allclose(row.v_km_s, v)
    assert any('planet_tracks.json' in p['name'] for p in source.sources())
    with pytest.raises(EphemerisUnavailable):
        source.validation_states('399', [epoch])
    with pytest.raises(EphemerisUnavailable):
        source.states('399', [source.track['end_jd_tdb'] + 100000])


def test_catalogue_keeps_only_current_objective_plans():
    manifest = json.loads((SEARCH_DIR / 'planet_pairs.json').read_text())
    plans = {p['plan_id']: p for path in PLANS_DIR.glob('*.json') for p in [json.loads(path.read_text())]}
    referenced = set()
    for key in ('pairs', 'demo_pairs'):
        for row in manifest[key]:
            if (row['origin_body_id'], row['destination_body_id']) not in PAIRS:
                continue
            assert row['grid']['departure_step_days'] <= 5
            assert row['grid']['tof_step_days'] <= 5
            if row['status'] != 'validated':
                continue
            least, earliest = (plans[row['objectives'][obj]] for obj in ('least_fuel', 'earliest_arrival'))
            assert least['masses']['propellant_required_kg'] <= earliest['masses']['propellant_required_kg']
            assert earliest['arrival']['jd_tdb'] <= least['arrival']['jd_tdb']
            for obj, identity in row['objectives'].items():
                referenced.add(identity)
                assert obj in plans[identity]['objectives_won']
                assert plans[identity]['ticks']['arrival_tick'] == 3500
                assert plans[identity]['ticks']['end_tick'] == 3800
    assert set(plans) == referenced
