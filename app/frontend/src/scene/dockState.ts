import { finiteVector, flightView } from "./flightState.ts";
import { kmToScene } from "./axes.ts";
import type { ScenePlan, SceneSnapshot, SceneShuttle, Vec3 } from "./types.ts";

/** Explicit opt-in mock only; production callers pass the backend fleet. */
export const MOCK_FLEET: SceneShuttle[] = [
  { id: "earth-standard", name: "Standard shuttle", class: "standard", body_id: "399", status: "docked" },
  { id: "earth-long", name: "Long-range shuttle", class: "long_range", body_id: "399", status: "docked" },
  { id: "venus-standard", name: "Standard shuttle", class: "standard", body_id: "299", status: "docked" },
  { id: "mars-standard", name: "Standard shuttle", class: "standard", body_id: "499", status: "docked" },
  { id: "mercury-long", name: "Long-range shuttle", class: "long_range", body_id: "199", status: "docked" },
  { id: "jupiter-long", name: "Long-range shuttle", class: "long_range", body_id: "599", status: "docked" },
];

export function countdownProgress(snapshot?: SceneSnapshot | null, plan?: ScenePlan | null): number {
  if (!snapshot || !plan?.ticks || snapshot.link.blackout ||
      snapshot.state !== "RUNNING" || flightView(snapshot, plan).mode !== "docked") return 0;
  return Math.max(0, Math.min(1, snapshot.tick / plan.ticks.departure_tick));
}

/** Estimate remains a separate marker and can never change the confirmed view. */
export function estimatePosition(snapshot?: SceneSnapshot | null, plan?: ScenePlan | null): Vec3 | null {
  if (!snapshot?.link.blackout || flightView(snapshot, plan).mode === "unavailable") return null;
  const value = snapshot.estimate?.spacecraft.r_km;
  return finiteVector(value) ? kmToScene(value) : null;
}

export function dockedShuttles(fleet: SceneShuttle[], bodyId: string, snapshot?: SceneSnapshot | null): SceneShuttle[] {
  return fleet.filter(ship => ship.status === "docked" && ship.body_id === bodyId &&
    !(snapshot && (snapshot.executed_mask & 1) && ship.id === snapshot.shuttle_id));
}
