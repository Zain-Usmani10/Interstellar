/** Horizons body ids for the eight planets (contracts 1.1.0). */

export type PlanetBodyId =
  | "199"
  | "299"
  | "399"
  | "499"
  | "599"
  | "699"
  | "799"
  | "899";

export const PLANET_BODIES: ReadonlyArray<{
  bodyId: PlanetBodyId;
  name: string;
}> = [
  { bodyId: "199", name: "Mercury" },
  { bodyId: "299", name: "Venus" },
  { bodyId: "399", name: "Earth" },
  { bodyId: "499", name: "Mars" },
  { bodyId: "599", name: "Jupiter" },
  { bodyId: "699", name: "Saturn" },
  { bodyId: "799", name: "Uranus" },
  { bodyId: "899", name: "Neptune" },
];

export function planetName(bodyId: string | null | undefined): string {
  return PLANET_BODIES.find((p) => p.bodyId === bodyId)?.name ?? bodyId ?? "—";
}
