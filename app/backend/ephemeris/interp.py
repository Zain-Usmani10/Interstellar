"""Planet position between cached NASA nodes: cubic Hermite interpolation, never extrapolation.

A cubic Hermite curve passes through both neighbouring NASA positions AND matches both NASA
velocities, so with daily nodes it follows the real orbit to well under a kilometre.
"""
from __future__ import annotations

import bisect

import numpy as np

SECONDS_PER_DAY = 86400.0


def hermite_state(states: list[dict], jd_tdb: float) -> tuple[np.ndarray, np.ndarray]:
    """Position (km) and velocity (km/s) at jd_tdb from time-ordered {jd_tdb, r_km, v_km_s} nodes."""
    times = [s["jd_tdb"] for s in states]
    if not times[0] <= jd_tdb <= times[-1]:
        raise ValueError(f"epoch {jd_tdb} is outside the cached interval [{times[0]}, {times[-1]}]; no extrapolation")
    i = min(max(bisect.bisect_right(times, jd_tdb) - 1, 0), len(times) - 2)
    a, b = states[i], states[i + 1]
    h = (b["jd_tdb"] - a["jd_tdb"]) * SECONDS_PER_DAY          # interval length in seconds
    s = (jd_tdb - a["jd_tdb"]) * SECONDS_PER_DAY / h           # 0..1 inside the interval
    r0, v0 = np.array(a["r_km"]), np.array(a["v_km_s"])
    r1, v1 = np.array(b["r_km"]), np.array(b["v_km_s"])
    h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
    h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
    r = h00 * r0 + h10 * h * v0 + h01 * r1 + h11 * h * v1
    d00, d10 = 6 * s**2 - 6 * s, 3 * s**2 - 4 * s + 1
    d01, d11 = -6 * s**2 + 6 * s, 3 * s**2 - 2 * s
    v = (d00 * r0 + d01 * r1) / h + d10 * v0 + d11 * v1
    return r, v
