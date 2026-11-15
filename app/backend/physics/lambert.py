"""Lambert's problem: 'I am HERE now and want to be THERE after this much time; what velocity do I need?'

We use the Izzo (2015) solver from lamberthub 1.0.0 (GPL-3.0 licensed; see the PR notes).
Zero revolutions, prograde: the simple single-arc transfer around the Sun.
"""
from __future__ import annotations

import numpy as np
from lamberthub import izzo2015


class LambertFailure(Exception):
    """The solver did not produce a usable answer. A failed cell is invalid, never 'free'."""


def solve_lambert(mu_km3_s2: float, r1_km, r2_km, tof_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Velocity at departure (v1) and at arrival (v2), km/s, for a coast of tof_s seconds from r1 to r2."""
    r1, r2 = np.asarray(r1_km, dtype=float), np.asarray(r2_km, dtype=float)
    if not (np.isfinite(tof_s) and tof_s > 0):
        raise LambertFailure("time of flight must be positive and finite")
    if not (np.all(np.isfinite(r1)) and np.all(np.isfinite(r2))):
        raise LambertFailure("non-finite position")
    # Degenerate geometry: positions (anti)parallel means the transfer plane is undefined.
    sin_angle = np.linalg.norm(np.cross(r1, r2)) / (np.linalg.norm(r1) * np.linalg.norm(r2))
    if sin_angle < 1e-6:
        raise LambertFailure("degenerate geometry: departure and arrival positions are collinear with the Sun")
    try:
        v1, v2 = izzo2015(mu_km3_s2, r1, r2, tof_s, M=0, prograde=True, low_path=True,
                          maxiter=35, atol=1e-5, rtol=1e-7)
    except Exception as exc:                       # lamberthub raises plain ValueError/AssertionError
        raise LambertFailure(f"solver failed: {exc}") from None
    v1, v2 = np.asarray(v1, dtype=float), np.asarray(v2, dtype=float)
    if not (np.all(np.isfinite(v1)) and np.all(np.isfinite(v2))):
        raise LambertFailure("solver returned a non-finite velocity")
    return v1, v2
