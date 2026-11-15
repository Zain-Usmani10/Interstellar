"""Orbital math tests: published Lambert case, conservation laws, rocket-equation behaviour."""
import math

import numpy as np
import pytest

from app.backend.physics.burns import (BurnModelError, Vehicle, parking_orbit_dv_km_s, parking_radius_km,
                                       propellant_for)
from app.backend.physics.lambert import LambertFailure, solve_lambert
from app.backend.physics.twobody import propagate

MU_EARTH = 398600.4418
MU_SUN = 132712440041.93938


def test_lambert_matches_published_reference_case():
    # Vallado, "Fundamentals of Astrodynamics and Applications", Example 7-5 (Earth orbit, 76 minutes).
    v1, v2 = solve_lambert(MU_EARTH, [15945.34, 0.0, 0.0], [12214.83899, 10249.46731, 0.0], 76 * 60.0)
    assert np.allclose(v1, [2.058913, 2.915965, 0.0], atol=1e-5)
    assert np.allclose(v2, [-3.451565, 0.910315, 0.0], atol=1e-5)


def test_lambert_solution_is_confirmed_by_independent_integration():
    r1, r2, tof = [15945.34, 0.0, 0.0], [12214.83899, 10249.46731, 0.0], 76 * 60.0
    v1, v2 = solve_lambert(MU_EARTH, r1, r2, tof)
    r_end, v_end = propagate(MU_EARTH, r1, v1, tof).state(tof)
    assert np.linalg.norm(r_end - r2) < 1e-3 and np.linalg.norm(v_end - v2) < 1e-6


@pytest.mark.parametrize("r1, r2, tof", [
    ([1.5e8, 0, 0], [2.2e8, 1e7, 0], 0.0),            # zero flight time
    ([1.5e8, 0, 0], [2.2e8, 1e7, 0], -5.0),           # negative flight time
    ([1.5e8, 0, 0], [2.2e8, 1e7, 0], math.nan),
    ([1.5e8, 0, 0], [-2.2e8, 0, 0], 2e7),             # exactly opposite: transfer plane undefined
    ([1.5e8, 0, 0], [math.inf, 0, 0], 2e7),
])
def test_lambert_rejects_bad_input_instead_of_returning_numbers(r1, r2, tof):
    with pytest.raises(LambertFailure):
        solve_lambert(MU_SUN, r1, r2, tof)


def test_coast_conserves_energy_and_angular_momentum():
    r0, v0 = [1.5e8, 0.0, 1e6], [2.0, 31.0, 1.5]                  # eccentric, inclined orbit around the Sun
    duration = 300 * 86400.0
    coast = propagate(MU_SUN, r0, v0, duration)
    e0, h0 = coast.specific_energy(0.0), coast.angular_momentum(0.0)
    for t in np.linspace(0, duration, 7):
        assert abs(coast.specific_energy(t) - e0) / abs(e0) < 1e-8
        assert np.linalg.norm(coast.angular_momentum(t) - h0) / np.linalg.norm(h0) < 1e-8


def test_circular_orbit_returns_to_start_and_tolerances_converge():
    r = 1.5e8
    speed = math.sqrt(MU_SUN / r)
    period = 2 * math.pi * math.sqrt(r ** 3 / MU_SUN)
    coast = propagate(MU_SUN, [r, 0, 0], [0, speed, 0], period)
    assert np.linalg.norm(coast.state(period)[0] - [r, 0, 0]) < 1.0            # km, after one full orbit
    tighter = propagate(MU_SUN, [r, 0, 0], [0, speed, 0], period, rtol=1e-12)
    assert np.linalg.norm(tighter.state(period)[0] - coast.state(period)[0]) < 1.0
    assert coast.min_radius_km() == pytest.approx(r, rel=1e-8)


def test_min_radius_finds_a_perihelion_between_the_endpoints():
    # Start and end far from the Sun, dipping inside: endpoints alone would miss the closest approach.
    r0, v0 = [1.5e8, 0.0, 0.0], [-20.0, 12.0, 0.0]
    h = np.cross(r0, v0)
    e = np.linalg.norm(np.cross(v0, h) / MU_SUN - np.array(r0) / 1.5e8)
    perihelion = float(h @ h / MU_SUN / (1 + e))
    coast = propagate(MU_SUN, r0, v0, 120 * 86400.0)
    assert coast.min_radius_km() == pytest.approx(perihelion, rel=1e-6)
    assert perihelion < 0.9 * min(1.5e8, np.linalg.norm(coast.state(120 * 86400.0)[0]))


def test_coast_refuses_to_extrapolate():
    coast = propagate(MU_SUN, [1.5e8, 0, 0], [0, 30, 0], 1000.0)
    with pytest.raises(ValueError):
        coast.state(2000.0)


# ------------------------------------------------------------------ burns and propellant

def test_parking_orbit_has_a_twelve_hour_period_and_clears_the_surface():
    r = parking_radius_km(398600.435436, 6371.01)
    assert 2 * math.pi * math.sqrt(r ** 3 / 398600.435436) == pytest.approx(43200.0)
    assert r == pytest.approx(26610.2, abs=0.1)
    with pytest.raises(BurnModelError):
        parking_radius_km(398600.435436, 30000.0)               # 'planet' bigger than the orbit


def test_parking_orbit_burn_formula():
    mu, r = 398600.435436, 26610.2227
    assert parking_orbit_dv_km_s(0.0, mu, r) == pytest.approx((math.sqrt(2) - 1) * math.sqrt(mu / r))   # bare escape
    assert parking_orbit_dv_km_s(4.0, mu, r) > parking_orbit_dv_km_s(3.0, mu, r)


def test_propellant_rises_with_payload_and_dv_and_falls_with_isp():
    base = propellant_for(2.5, 1.9, Vehicle()).required_kg
    assert propellant_for(2.5, 1.9, Vehicle(payload_mass_kg=500.0)).required_kg > base
    assert propellant_for(2.6, 1.9, Vehicle()).required_kg > base
    assert propellant_for(2.5, 2.0, Vehicle()).required_kg > base
    assert propellant_for(2.5, 1.9, Vehicle(isp_s=320.0)).required_kg > base
    assert propellant_for(2.5, 1.9, Vehicle(isp_s=900.0)).required_kg < base


def test_propellant_matches_the_rocket_equation_and_splits_in_order():
    vehicle = Vehicle()
    p = propellant_for(2.5, 1.9, vehicle)
    ve = vehicle.isp_s * 9.80665 / 1000
    assert p.required_kg == pytest.approx(1100.0 * (math.exp(4.4 / ve) - 1))
    assert p.departure_kg + p.capture_kg == pytest.approx(p.required_kg)
    assert p.departure_kg > p.capture_kg > 0                                   # the first burn pushes a heavier ship
    assert p.capture_kg == pytest.approx(1100.0 * (math.exp(1.9 / ve) - 1))    # capture alone, from the final mass


def test_gram_ledger_rounds_up_and_adds_up():
    p = propellant_for(2.5, 1.9, Vehicle())
    assert p.departure_g == math.ceil(p.departure_kg * 1000) and p.capture_g == math.ceil(p.capture_kg * 1000)
    assert p.initial_g == p.departure_g + p.capture_g
    assert 0 <= p.initial_g - p.required_kg * 1000 < 2                          # at most 2 g of rounding
    assert isinstance(p.initial_g, int) and p.departure_g >= 1 and p.capture_g >= 1


def test_capacity_edge_cases():
    p = propellant_for(2.5, 1.9, Vehicle())
    exactly_enough = Vehicle(propellant_capacity_kg=p.initial_g / 1000)
    assert propellant_for(2.5, 1.9, exactly_enough).feasible
    one_gram_short = Vehicle(propellant_capacity_kg=(p.initial_g - 1) / 1000)
    assert not propellant_for(2.5, 1.9, one_gram_short).feasible
    # Fits before rounding but not after: the integer ledger is what the FPGA must hold.
    between = Vehicle(propellant_capacity_kg=(p.required_kg + p.initial_g / 1000) / 2)
    assert p.required_kg <= between.propellant_capacity_kg and not propellant_for(2.5, 1.9, between).feasible
    assert not propellant_for(9.0, 9.0, Vehicle()).feasible


@pytest.mark.parametrize("kwargs", [{"dry_mass_kg": 0}, {"isp_s": -1}, {"payload_mass_kg": -5},
                                    {"propellant_capacity_kg": math.inf}, {"dry_mass_kg": math.nan}])
def test_unphysical_vehicles_are_refused(kwargs):
    with pytest.raises(BurnModelError):
        Vehicle(**kwargs)


@pytest.mark.parametrize("dv", [(0.0, 1.0), (1.0, -1.0), (math.nan, 1.0)])
def test_nonpositive_burns_are_refused(dv):
    with pytest.raises(BurnModelError):
        propellant_for(*dv, Vehicle())
