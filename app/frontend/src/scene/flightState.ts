import { kmToScene } from "./axes.ts";
import type { ScenePlan, SceneSnapshot, Vec3 } from "./types.ts";

export type FlightView = {
  mode: "docked" | "coast" | "captured" | "uncaptured" | "unavailable";
  position: Vec3 | null;
  departed: boolean;
  stale: boolean;
  label: string;
};

export function finiteVector(
  value: readonly number[] | null | undefined,
): value is Vec3 {
  return !!value && value.length === 3 && value.every(Number.isFinite);
}

/** No time integration, orbit propagation or optimistic launch state in the scene. */
export function flightView(
  snapshot?: SceneSnapshot | null,
  plan?: ScenePlan | null,
): FlightView {
  if (!snapshot)
    return {
      mode: "docked",
      position: null,
      departed: false,
      stale: false,
      label: "DOCKED · NO MISSION TELEMETRY",
    };
  const stale = snapshot.link.transport_state !== "connected";
  const invalid =
    snapshot.state === "UNKNOWN" ||
    snapshot.spacecraft.phase === "unknown" ||
    snapshot.outcome === "lost" ||
    snapshot.outcome === "plan_invalid" ||
    (plan &&
      (snapshot.plan_id !== plan.plan_id ||
        snapshot.plan_sha256 !== plan.plan_sha256));
  if (invalid)
    return {
      mode: "unavailable",
      position: null,
      departed: false,
      stale,
      label: "MISSION POSITION UNAVAILABLE",
    };
  const departed = (snapshot.executed_mask & 1) !== 0;
  const position = finiteVector(snapshot.spacecraft.r_km)
    ? kmToScene(snapshot.spacecraft.r_km)
    : null;
  if (!departed)
    return {
      mode: "docked",
      position: null,
      departed: false,
      stale,
      label: `${snapshot.state} · DEPARTURE NOT REPORTED`,
    };
  if (!position)
    return {
      mode: "unavailable",
      position: null,
      departed: true,
      stale,
      label: "SPACECRAFT POSITION UNAVAILABLE",
    };
  const captured =
    snapshot.spacecraft.phase === "captured" &&
    (snapshot.executed_mask & 2) !== 0 &&
    snapshot.state === "COMPLETE" &&
    snapshot.outcome === "captured";
  const failed =
    snapshot.state === "SAFE" ||
    snapshot.state === "ABORTED" ||
    snapshot.spacecraft.phase === "uncaptured_coast" ||
    snapshot.outcome === "uncaptured";
  const mode = captured ? "captured" : failed ? "uncaptured" : "coast";
  return {
    mode,
    position,
    departed,
    stale,
    label: captured
      ? "CAPTURE CONFIRMED"
      : failed
        ? `${snapshot.state} · UNCAPTURED COAST`
        : "COAST · DEPARTURE CONFIRMED",
  };
}

/** Verbatim supplied nominal samples; never manufacture a decorative transfer curve. */
export function routePoints(plan?: ScenePlan | null): Vec3[] {
  if (
    !plan ||
    plan.nominal_path.length < 2 ||
    !plan.nominal_path.every((p) => finiteVector(p.r_km))
  )
    return [];
  return plan.nominal_path.map((p) => kmToScene(p.r_km));
}

function dist2(a: Vec3, b: Vec3): number {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  const dz = a[2] - b[2];
  return dx * dx + dy * dy + dz * dz;
}

/**
 * Split a nominal polyline at the closest point to the confirmed craft position.
 * Flown = solid; remaining = dotted. Never invents samples beyond the path.
 */
export function splitRouteAtCraft(
  points: Vec3[],
  craft: Vec3 | null | undefined,
): { flown: Vec3[]; remaining: Vec3[] } {
  if (points.length < 2) return { flown: [], remaining: [] };
  if (!craft || !finiteVector(craft)) {
    return { flown: [], remaining: points.slice() };
  }

  let bestSeg = 0;
  let bestT = 0;
  let bestD = Infinity;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const ab: Vec3 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const ab2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2];
    let t = 0;
    if (ab2 > 1e-18) {
      t =
        ((craft[0] - a[0]) * ab[0] +
          (craft[1] - a[1]) * ab[1] +
          (craft[2] - a[2]) * ab[2]) /
        ab2;
      t = Math.max(0, Math.min(1, t));
    }
    const p: Vec3 = [
      a[0] + ab[0] * t,
      a[1] + ab[1] * t,
      a[2] + ab[2] * t,
    ];
    const d = dist2(craft, p);
    if (d < bestD) {
      bestD = d;
      bestSeg = i;
      bestT = t;
    }
  }

  const a = points[bestSeg];
  const b = points[bestSeg + 1];
  const atCraft: Vec3 = [
    a[0] + (b[0] - a[0]) * bestT,
    a[1] + (b[1] - a[1]) * bestT,
    a[2] + (b[2] - a[2]) * bestT,
  ];

  const flown = points.slice(0, bestSeg + 1);
  flown.push(atCraft);
  const remaining = [atCraft, ...points.slice(bestSeg + 1)];
  // Drop a zero-length tail when craft sits on the last sample.
  if (bestSeg === points.length - 2 && bestT >= 1 - 1e-9) {
    return { flown: points.slice(), remaining: [] };
  }
  return { flown, remaining };
}

/** Decorative easing is bounded by the two received positions, never extrapolated. */
export function betweenReceived(from: Vec3, to: Vec3, progress: number): Vec3 {
  const t = Math.max(0, Math.min(1, progress));
  return from.map((value, i) => value + (to[i] - value) * t) as Vec3;
}
