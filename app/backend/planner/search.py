"""Bounded Earth->Mars route search: try a grid of (departure date, flight time) pairs.

For every cell: take NASA's Earth position at departure and Mars position at arrival, solve
Lambert for the connecting arc, size the two burns, apply the rocket equation, mark feasible or not.
Then pick two recommendations, both only 'best within this grid':
  - least_fuel:        the feasible cell needing the least propellant
  - earliest_arrival:  the feasible cell that reaches Mars on the earliest date
                       (ties broken by propellant; this is NOT the same as shortest flight)
All NASA vectors are fetched/read before the loop; there are no network calls per cell.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..ephemeris.cache import EphemerisSource
from ..ephemeris.horizons import SUN_ID, canonical_epoch
from ..ephemeris.timeconv import jd_tdb_to_utc, utc_to_jd_tdb
from ..physics.burns import BurnModelError, Propellant, Vehicle, parking_orbit_dv_km_s, parking_radius_km, propellant_for
from ..physics.lambert import LambertFailure, solve_lambert

ORIGIN_ID, DESTINATION_ID = "399", "499"
MAX_GRID_AXIS = 25
OBJECTIVES = ("least_fuel", "earliest_arrival")


class NoFeasibleRoute(Exception):
    code = "NO_FEASIBLE_ROUTE"


class SearchCancelled(Exception):
    code = "SEARCH_CANCELLED"


@dataclass(frozen=True)
class GridSpec:
    """Search bounds. Departures are evenly spaced in TDB starting at departure_start_utc."""
    departure_start_utc: str = "2026-11-15T00:00:00Z"
    departure_step_days: float = 4.0
    n_departures: int = 24                    # 2026-11-15 .. 2027-02-15
    tof_min_days: float = 120.0
    tof_step_days: float = 10.0
    n_durations: int = 25                     # 120 .. 360 days

    def __post_init__(self):
        if not (1 <= self.n_departures <= MAX_GRID_AXIS and 1 <= self.n_durations <= MAX_GRID_AXIS):
            raise ValueError(f"grid axes must have 1..{MAX_GRID_AXIS} points")
        numbers = (self.departure_step_days, self.tof_min_days, self.tof_step_days)
        if not all(math.isfinite(x) and x > 0 for x in numbers):
            raise ValueError("grid steps and minimum flight time must be positive and finite")

    def departure_epochs(self) -> list[float]:
        start = canonical_epoch(utc_to_jd_tdb(self.departure_start_utc))
        return [canonical_epoch(start + i * self.departure_step_days) for i in range(self.n_departures)]

    def durations_days(self) -> list[float]:
        return [self.tof_min_days + j * self.tof_step_days for j in range(self.n_durations)]

    @property
    def tof_max_days(self) -> float:
        return self.durations_days()[-1]


@dataclass(frozen=True)
class Constants:
    """GM values and radii exactly as printed by JPL Horizons (body GM, not planet-system GM)."""
    mu_sun: float
    mu_origin: float
    mu_destination: float
    radius_sun_km: float
    radius_origin_km: float
    radius_destination_km: float

    @classmethod
    def from_source(cls, source: EphemerisSource) -> "Constants":
        sun, origin, dest = (source.body_constants(b) for b in (SUN_ID, ORIGIN_ID, DESTINATION_ID))
        return cls(sun["gm_km3_s2"], origin["gm_km3_s2"], dest["gm_km3_s2"],
                   sun["mean_radius_km"], origin["mean_radius_km"], dest["mean_radius_km"])


@dataclass
class Cell:
    """One (departure, flight time) candidate and everything computed for it."""
    departure_jd_tdb: float
    arrival_jd_tdb: float
    tof_days: float
    status: str = "ok"                         # "ok" or the reason the cell is invalid
    feasible: bool = False
    v_inf_depart: float = math.nan
    v_inf_arrive: float = math.nan
    dv_depart: float = math.nan
    dv_capture: float = math.nan
    propellant: Propellant | None = None
    vectors: dict = field(default_factory=dict, repr=False)   # r/v of both planets + Lambert v1, v2

    @property
    def dv_total(self) -> float:
        return self.dv_depart + self.dv_capture


def periapsis_radius_km(mu: float, r, v) -> float:
    """Closest point to the Sun of the whole orbit through (r, v). Conservative Sun-collision screen."""
    h = np.cross(r, v)
    e = np.linalg.norm(np.cross(v, h) / mu - r / np.linalg.norm(r))
    return float(h @ h / mu / (1 + e))


def evaluate_cell(cell: Cell, constants: Constants, vehicle: Vehicle, r_park_origin: float, r_park_dest: float) -> Cell:
    """Fill in one cell. Any failure marks the cell invalid; it can never look like a cheap route."""
    v = cell.vectors
    try:
        v1, v2 = solve_lambert(constants.mu_sun, v["origin_r"], v["destination_r"], cell.tof_days * 86400.0)
    except LambertFailure as exc:
        cell.status = f"lambert_failed: {exc}"
        return cell
    if periapsis_radius_km(constants.mu_sun, np.array(v["origin_r"]), v1) <= constants.radius_sun_km:
        cell.status = "solar_intersection"
        return cell
    v["lambert_v1"], v["lambert_v2"] = v1, v2
    cell.v_inf_depart = float(np.linalg.norm(v1 - np.array(v["origin_v"])))
    cell.v_inf_arrive = float(np.linalg.norm(v2 - np.array(v["destination_v"])))
    cell.dv_depart = parking_orbit_dv_km_s(cell.v_inf_depart, constants.mu_origin, r_park_origin)
    cell.dv_capture = parking_orbit_dv_km_s(cell.v_inf_arrive, constants.mu_destination, r_park_dest)
    try:
        cell.propellant = propellant_for(cell.dv_depart, cell.dv_capture, vehicle)
    except (BurnModelError, OverflowError) as exc:
        cell.status = f"burn_model_failed: {exc}"
        return cell
    cell.feasible = cell.propellant.feasible
    if not cell.feasible:
        cell.status = "exceeds_propellant_capacity"
    return cell


def run_grid(source: EphemerisSource, grid: GridSpec, vehicle: Vehicle, constants: Constants,
             progress=lambda fraction: None, cancelled=lambda: False) -> list[Cell]:
    """Evaluate every cell of the grid. NASA data is gathered first, in two batched reads.

    `progress` gets 0..1 as cells finish; if `cancelled()` turns true the search stops with SearchCancelled.
    """
    departures = grid.departure_epochs()
    cells = [Cell(d, canonical_epoch(d + tof), tof) for d in departures for tof in grid.durations_days()]
    arrivals = sorted({c.arrival_jd_tdb for c in cells})
    earth = dict(zip(departures, source.states(ORIGIN_ID, departures)))
    mars = dict(zip(arrivals, source.states(DESTINATION_ID, arrivals)))

    r_park_origin = parking_radius_km(constants.mu_origin, constants.radius_origin_km)
    r_park_dest = parking_radius_km(constants.mu_destination, constants.radius_destination_km)
    for n, cell in enumerate(cells):
        if cancelled():
            raise SearchCancelled("search cancelled")
        progress(n / len(cells))
        e, m = earth[cell.departure_jd_tdb], mars[cell.arrival_jd_tdb]
        cell.vectors = {"origin_r": e.r_km, "origin_v": e.v_km_s, "destination_r": m.r_km, "destination_v": m.v_km_s}
        evaluate_cell(cell, constants, vehicle, r_park_origin, r_park_dest)
    return cells


def select_winners(cells: list[Cell]) -> dict[str, Cell]:
    """The two recommendations. Only feasible, successfully solved cells can win."""
    feasible = [c for c in cells if c.status == "ok" and c.feasible and c.propellant is not None]
    if not feasible:
        raise NoFeasibleRoute("NO_FEASIBLE_ROUTE: no cell in this grid fits the vehicle's propellant capacity")
    return {
        "least_fuel": min(feasible, key=lambda c: (c.propellant.required_kg, c.arrival_jd_tdb)),
        "earliest_arrival": min(feasible, key=lambda c: (c.arrival_jd_tdb, c.propellant.required_kg)),
    }


def grid_summary(cells: list[Cell], grid: GridSpec, winners: dict[str, Cell]) -> dict:
    """Compact table of every cell (the 'porkchop' data) for the route-comparison view."""
    def row(c: Cell) -> dict:
        ok = c.propellant is not None
        return {
            "departure_jd_tdb": c.departure_jd_tdb, "departure_utc": jd_tdb_to_utc(c.departure_jd_tdb),
            "arrival_jd_tdb": c.arrival_jd_tdb, "arrival_utc": jd_tdb_to_utc(c.arrival_jd_tdb),
            "tof_days": c.tof_days, "status": c.status, "feasible": c.feasible,
            "dv_total_km_s": c.dv_total if ok else None,
            "propellant_required_kg": c.propellant.required_kg if ok else None,
            "objectives_won": [name for name, w in winners.items() if w is c],
        }
    return {
        "label": "Best within this grid only. Not a global optimum.",
        "departure_start_utc": grid.departure_start_utc,
        "departure_end_utc": jd_tdb_to_utc(grid.departure_epochs()[-1]),
        "departure_step_days": grid.departure_step_days, "n_departures": grid.n_departures,
        "tof_min_days": grid.tof_min_days, "tof_max_days": grid.tof_max_days,
        "tof_step_days": grid.tof_step_days, "n_durations": grid.n_durations,
        "n_feasible": sum(c.feasible for c in cells),
        "cells": [row(c) for c in cells],
    }
