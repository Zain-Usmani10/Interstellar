import type { Vec3 } from "./types";

/** Illustrative Earth→destination arc for scenic tours (not controller telemetry). */
export function scenicPath(from: Vec3, to: Vec3, steps = 64): Vec3[] {
  const mid: Vec3 = [
    (from[0] + to[0]) * 0.5,
    Math.max(4, Math.hypot(to[0] - from[0], to[2] - from[2]) * 0.22),
    (from[2] + to[2]) * 0.5,
  ];
  const out: Vec3[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    out.push([
      u * u * from[0] + 2 * u * t * mid[0] + t * t * to[0],
      u * u * from[1] + 2 * u * t * mid[1] + t * t * to[1],
      u * u * from[2] + 2 * u * t * mid[2] + t * t * to[2],
    ]);
  }
  return out;
}

export function scenicPosition(path: Vec3[], progress: number): Vec3 {
  if (path.length === 0) return [0, 0, 0];
  const t = Math.min(1, Math.max(0, progress));
  const f = t * (path.length - 1);
  const i = Math.floor(f);
  const j = Math.min(path.length - 1, i + 1);
  const u = f - i;
  return [
    path[i][0] + (path[j][0] - path[i][0]) * u,
    path[i][1] + (path[j][1] - path[i][1]) * u,
    path[i][2] + (path[j][2] - path[i][2]) * u,
  ];
}
