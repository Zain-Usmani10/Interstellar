"""Burn sizes (delta-v) and propellant for the two engine firings: leave Earth, get captured at Mars.

Model (deliberately simple, labelled as such): instantaneous burns from circular 12-hour parking
orbits, and the Tsiolkovsky rocket equation. No launch, no atmosphere, no finite burn time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

G0_M_S2 = 9.80665                 # standard gravity, converts Isp (seconds) to exhaust speed
PARKING_PERIOD_S = 43200.0        # 12 hours
DEMO_VEHICLE_LABEL = "Hypothetical demo vehicle (Isp 900 s)"


class BurnModelError(ValueError):
    pass


@dataclass(frozen=True)
class Vehicle:
    label: str = "Hypothetical chemical vehicle (not a NASA spacecraft)"
    dry_mass_kg: float = 1000.0
    payload_mass_kg: float = 100.0
    isp_s: float = 450.0
    propellant_capacity_kg: float = 10000.0

    def __post_init__(self):
        values = (self.dry_mass_kg, self.payload_mass_kg, self.isp_s, self.propellant_capacity_kg)
        if not all(math.isfinite(v) for v in values):
            raise BurnModelError("vehicle values must be finite")
        if self.dry_mass_kg <= 0 or self.isp_s <= 0 or self.propellant_capacity_kg <= 0 or self.payload_mass_kg < 0:
            raise BurnModelError("dry mass, Isp and capacity must be positive; payload cannot be negative")


def parking_radius_km(mu_planet_km3_s2: float, planet_radius_km: float) -> float:
    """Radius of the circular orbit with a 12-hour period (Kepler's third law). Must clear the surface."""
    r_park = (mu_planet_km3_s2 * (PARKING_PERIOD_S / (2 * math.pi)) ** 2) ** (1 / 3)
    if r_park <= planet_radius_km:
        raise BurnModelError(f"parking orbit radius {r_park:.0f} km is not above the surface ({planet_radius_km} km)")
    return r_park


def parking_orbit_dv_km_s(v_inf_km_s: float, mu_planet_km3_s2: float, r_park_km: float) -> float:
    """Burn needed in parking orbit to leave the planet with speed v_inf far away (or the reverse, to be captured).

    Speed needed at r_park on the escape path, minus the circular speed we already have there.
    """
    return math.sqrt(v_inf_km_s ** 2 + 2 * mu_planet_km3_s2 / r_park_km) - math.sqrt(mu_planet_km3_s2 / r_park_km)


@dataclass(frozen=True)
class Propellant:
    m_final_kg: float                 # dry + payload: what is left after both burns
    required_kg: float                # total propellant loaded (exactly what is needed, no reserve)
    departure_kg: float               # burned leaving Earth
    capture_kg: float                 # burned at Mars
    departure_g: int                  # the same costs as whole grams, rounded UP, for the FPGA ledger
    capture_g: int
    initial_g: int                    # departure_g + capture_g
    feasible: bool                    # fits in the tank, also after rounding


def propellant_for(dv_depart_km_s: float, dv_capture_km_s: float, vehicle: Vehicle) -> Propellant:
    """Rocket equation, burns applied in order: departure first (heavier ship), capture second."""
    if not (math.isfinite(dv_depart_km_s) and math.isfinite(dv_capture_km_s)) or dv_depart_km_s <= 0 or dv_capture_km_s <= 0:
        raise BurnModelError("both burns need a positive finite delta-v")
    exhaust_m_s = vehicle.isp_s * G0_M_S2
    m_final = vehicle.dry_mass_kg + vehicle.payload_mass_kg
    required = m_final * math.expm1((dv_depart_km_s + dv_capture_km_s) * 1000 / exhaust_m_s)
    m_loaded = m_final + required
    m_after_departure = m_loaded * math.exp(-dv_depart_km_s * 1000 / exhaust_m_s)
    departure = m_loaded - m_after_departure
    capture = m_after_departure - m_final
    departure_g, capture_g = math.ceil(departure * 1000), math.ceil(capture * 1000)
    initial_g = departure_g + capture_g
    feasible = (required <= vehicle.propellant_capacity_kg
                and initial_g <= vehicle.propellant_capacity_kg * 1000
                and initial_g <= 0xFFFFFFFF)
    return Propellant(m_final, required, departure, capture, departure_g, capture_g, initial_g, feasible)
