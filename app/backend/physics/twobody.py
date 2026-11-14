"""Two-body coast around the Sun, integrated numerically (SciPy DOP853).

This is the INDEPENDENT check on the Lambert solver: we take the Lambert departure velocity,
let only the Sun's gravity act for the flight time, and see whether we really end up at Mars.
It uses a different method (step-by-step integration) than the solver (an algebraic solution).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar

RTOL = 1e-10
ATOL = [1e-3, 1e-3, 1e-3, 1e-9, 1e-9, 1e-9]      # km for position, km/s for velocity


class PropagationFailure(Exception):
    pass


@dataclass
class Coast:
    """An integrated arc. Evaluate it only inside [0, duration_s]; it refuses to extrapolate."""
    mu_km3_s2: float
    duration_s: float
    _solution: object

    def state(self, t_s: float) -> tuple[np.ndarray, np.ndarray]:
        if not -1e-6 <= t_s <= self.duration_s + 1e-6:
            raise ValueError(f"t={t_s} s is outside the integrated interval [0, {self.duration_s}] s")
        y = self._solution(min(max(t_s, 0.0), self.duration_s))
        return y[:3], y[3:]

    def min_radius_km(self) -> float:
        """Closest approach to the Sun's centre anywhere on the arc, including between samples."""
        radius = lambda t: float(np.linalg.norm(self._solution(t)[:3]))
        grid = np.linspace(0.0, self.duration_s, 2049)
        radii = [radius(t) for t in grid]
        i = int(np.argmin(radii))
        lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
        refined = minimize_scalar(radius, bounds=(lo, hi), method="bounded", options={"xatol": 1.0})
        return min(radii[i], float(refined.fun))

    def specific_energy(self, t_s: float) -> float:
        r, v = self.state(t_s)
        return float(v @ v / 2 - self.mu_km3_s2 / np.linalg.norm(r))

    def angular_momentum(self, t_s: float) -> np.ndarray:
        r, v = self.state(t_s)
        return np.cross(r, v)


def propagate(mu_km3_s2: float, r0_km, v0_km_s, duration_s: float, rtol: float = RTOL) -> Coast:
    """Integrate r'' = -mu r / |r|^3 from (r0, v0) for duration_s seconds."""
    def gravity(_t, y):
        r = y[:3]
        return np.concatenate((y[3:], -mu_km3_s2 * r / np.linalg.norm(r) ** 3))

    y0 = np.concatenate((np.asarray(r0_km, dtype=float), np.asarray(v0_km_s, dtype=float)))
    scale = rtol / RTOL
    result = solve_ivp(gravity, (0.0, duration_s), y0, method="DOP853", dense_output=True,
                       rtol=rtol, atol=[a * scale for a in ATOL])
    if not result.success:
        raise PropagationFailure(result.message)
    return Coast(mu_km3_s2, duration_s, result.sol)
