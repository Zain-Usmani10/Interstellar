import type { SceneBodyId, SceneShuttle } from "../scene/types";
import type { PlanetBodyId } from "./planetBodies";

/** Fleet shapes matching contracts 1.3.0 GET /api/v1/fleet. */

export type ShuttleClass = "standard" | "long_range";

export type FleetLocation =
  | { kind: "docked"; body_id: string }
  | { kind: "in_flight"; mission_id: string }
  | { kind: "lost"; mission_id?: string };

export type FleetShuttle = {
  id: string;
  name: string;
  class: ShuttleClass;
  label?: string;
  location: FleetLocation;
};

export type FleetState = {
  schema_version?: number;
  active_mission_id?: string | null;
  shuttles: FleetShuttle[];
};

export const SHUTTLE_LABEL: Record<ShuttleClass, string> = {
  standard: "Standard shuttle",
  long_range: "Long-range shuttle",
};

export function shuttleClassFromIsp(isp: number | undefined): ShuttleClass {
  return (isp ?? 450) >= 900 ? "long_range" : "standard";
}

export function dockedAt(
  fleet: FleetShuttle[],
  bodyId: PlanetBodyId,
): FleetShuttle[] {
  return fleet.filter(
    (s) => s.location.kind === "docked" && s.location.body_id === bodyId,
  );
}

/** Affan's OrbitScene fleet prop (flattened body_id + status). */
export function toSceneFleet(fleet: FleetShuttle[]): SceneShuttle[] {
  const bodies: SceneBodyId[] = [
    "199",
    "299",
    "399",
    "499",
    "599",
    "699",
    "799",
    "899",
  ];
  return fleet.map((s) => {
    if (s.location.kind === "docked") {
      const body = s.location.body_id;
      return {
        id: s.id,
        name: s.name,
        class: s.class,
        body_id: bodies.includes(body as SceneBodyId)
          ? (body as SceneBodyId)
          : null,
        status: "docked" as const,
      };
    }
    return {
      id: s.id,
      name: s.name,
      class: s.class,
      body_id: null,
      status: s.location.kind === "lost" ? ("lost" as const) : ("in_flight" as const),
    };
  });
}
