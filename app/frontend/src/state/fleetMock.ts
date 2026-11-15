import type { PlanetBodyId } from "./planetBodies";

/** Plan §20 fleet shape — mock until GET /api/v1/fleet exists. */

export type ShuttleClass = "standard" | "long_range";

export type FleetShuttle = {
  id: string;
  name: string;
  class: ShuttleClass;
  location:
    | { kind: "docked"; body_id: PlanetBodyId }
    | { kind: "in_flight"; mission_id: string }
    | { kind: "lost" };
};

export const SHUTTLE_LABEL: Record<ShuttleClass, string> = {
  standard: "Standard shuttle",
  long_range: "Long-range shuttle",
};

/** Default fleet from plan §20 (data/fleet.json once the API lands). */
export const MOCK_FLEET: FleetShuttle[] = [
  {
    id: "shuttle-std-earth-1",
    name: "Standard shuttle",
    class: "standard",
    location: { kind: "docked", body_id: "399" },
  },
  {
    id: "shuttle-lr-earth-1",
    name: "Long-range shuttle",
    class: "long_range",
    location: { kind: "docked", body_id: "399" },
  },
  {
    id: "shuttle-std-venus-1",
    name: "Standard shuttle",
    class: "standard",
    location: { kind: "docked", body_id: "299" },
  },
  {
    id: "shuttle-std-mars-1",
    name: "Standard shuttle",
    class: "standard",
    location: { kind: "docked", body_id: "499" },
  },
  {
    id: "shuttle-lr-mercury-1",
    name: "Long-range shuttle",
    class: "long_range",
    location: { kind: "docked", body_id: "199" },
  },
  {
    id: "shuttle-lr-jupiter-1",
    name: "Long-range shuttle",
    class: "long_range",
    location: { kind: "docked", body_id: "599" },
  },
];

export function dockedAt(
  fleet: FleetShuttle[],
  bodyId: PlanetBodyId,
): FleetShuttle[] {
  return fleet.filter(
    (s) => s.location.kind === "docked" && s.location.body_id === bodyId,
  );
}
