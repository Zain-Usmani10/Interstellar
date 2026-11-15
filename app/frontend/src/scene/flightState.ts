import { kmToScene } from "./axes.ts";
import type { ScenePlan, SceneSnapshot, Vec3 } from "./types.ts";

export type FlightView = {
  mode: "docked" | "coast" | "captured" | "uncaptured" | "unavailable";
  position: Vec3 | null;
  departed: boolean;
  stale: boolean;
  label: string;
};

export function finiteVector(value: readonly number[] | null | undefined): value is Vec3 {
  return !!value && value.length === 3 && value.every(Number.isFinite);
}

/** No time integration, orbit propagation or optimistic launch state in the scene. */
export function flightView(snapshot?: SceneSnapshot | null, plan?: ScenePlan | null): FlightView {
  if (!snapshot) return { mode: "docked", position: null, departed: false, stale: false, label: "DOCKED · NO MISSION TELEMETRY" };
  const stale = snapshot.link.transport_state !== "connected";
  const invalid = snapshot.state === "UNKNOWN" || snapshot.outcome === "lost" || snapshot.outcome === "plan_invalid"
    || (plan && (snapshot.plan_id !== plan.plan_id || snapshot.plan_sha256 !== plan.plan_sha256));
  if (invalid) return { mode: "unavailable", position: null, departed: false, stale, label: "MISSION POSITION UNAVAILABLE" };
  const departed = (snapshot.executed_mask & 1) !== 0;
  const position = finiteVector(snapshot.spacecraft.r_km) ? kmToScene(snapshot.spacecraft.r_km) : null;
  if (!departed) return { mode: "docked", position: null, departed: false, stale,
    label: `${snapshot.state} · DEPARTURE NOT REPORTED` };
  if (!position) return { mode: "unavailable", position: null, departed: true, stale, label: "SPACECRAFT POSITION UNAVAILABLE" };
  const captured = snapshot.spacecraft.phase === "captured" && (snapshot.executed_mask & 2) !== 0
    && snapshot.state === "COMPLETE" && snapshot.outcome === "captured";
  const failed = snapshot.state === "SAFE" || snapshot.state === "ABORTED"
    || snapshot.spacecraft.phase === "uncaptured_coast" || snapshot.outcome === "uncaptured";
  const mode = captured ? "captured" : failed ? "uncaptured" : "coast";
  return { mode, position, departed, stale,
    label: captured ? "CAPTURE CONFIRMED" : failed ? `${snapshot.state} · UNCAPTURED COAST` : "COAST · DEPARTURE CONFIRMED" };
}

/** Verbatim supplied nominal samples; never manufacture a decorative transfer curve. */
export function routePoints(plan?: ScenePlan | null): Vec3[] {
  if (!plan || plan.nominal_path.length < 2 || !plan.nominal_path.every(p => finiteVector(p.r_km))) return [];
  return plan.nominal_path.map(p => kmToScene(p.r_km));
}

/** Decorative easing is bounded by the two received positions, never extrapolated. */
export function betweenReceived(from: Vec3, to: Vec3, progress: number): Vec3 {
  const t = Math.max(0, Math.min(1, progress));
  return from.map((value, i) => value + (to[i] - value) * t) as Vec3;
}
