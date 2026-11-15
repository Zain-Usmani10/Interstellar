import type { PlanetTargetId } from "../api/types";
import { kmToScene } from "./axes";
import { finiteVector } from "./flightState";
import type { ScenePlan, SceneSnapshot, Vec3 } from "./types";

export type VisualPlanet = {
  name: string;
  radius: number;
  displayOrbitAU: number;
  angle: number;
  color: string;
  accent: string;
  surface: "rock" | "earth" | "gas";
  target?: PlanetTargetId;
  /** Horizons id when this visual body maps to a plan origin/destination. */
  bodyId?: string;
  rings?: boolean;
};

// Illustrative overview, not ephemeris. Outer distances are compressed for framing.
// Supplied Earth/Mars positions and the route always retain their actual AU scale.
export const VISUAL_PLANETS: VisualPlanet[] = [
  {
    name: "Mercury",
    radius: 0.28,
    displayOrbitAU: 0.39,
    angle: 2.2,
    color: "#aaa39a",
    accent: "#5b5350",
    surface: "rock",
    bodyId: "199",
  },
  {
    name: "Venus",
    radius: 0.55,
    displayOrbitAU: 0.72,
    angle: 4.5,
    color: "#d6ad79",
    accent: "#9b714e",
    surface: "gas",
    bodyId: "299",
  },
  {
    name: "Earth",
    radius: 0.65,
    displayOrbitAU: 1,
    angle: 0,
    color: "#1b6b9d",
    accent: "#5d9c79",
    surface: "earth",
    bodyId: "399",
    target: "planet.399",
  },
  {
    name: "Mars",
    radius: 0.46,
    displayOrbitAU: 1.52,
    angle: 1,
    color: "#cf7955",
    accent: "#70372b",
    surface: "rock",
    bodyId: "499",
    target: "planet.499",
  },
  {
    name: "Jupiter",
    radius: 2.5,
    displayOrbitAU: 3.3,
    angle: 2.4,
    color: "#d8b58e",
    accent: "#946452",
    surface: "gas",
    bodyId: "599",
  },
  {
    name: "Saturn",
    radius: 2.05,
    displayOrbitAU: 4.6,
    angle: 5.6,
    color: "#d3bf8f",
    accent: "#93846b",
    surface: "gas",
    bodyId: "699",
    rings: true,
  },
  {
    name: "Uranus",
    radius: 1.45,
    displayOrbitAU: 6,
    angle: 3.6,
    color: "#9ed3d0",
    accent: "#638e9f",
    surface: "gas",
    bodyId: "799",
  },
  {
    name: "Neptune",
    radius: 1.4,
    displayOrbitAU: 7.5,
    angle: 0.6,
    color: "#4b75bd",
    accent: "#244075",
    surface: "gas",
    bodyId: "899",
  },
];

export function planetPosition(
  body: VisualPlanet,
  plan?: ScenePlan | null,
  snapshot?: SceneSnapshot | null,
): Vec3 {
  const reported =
    body.bodyId && snapshot?.planets.find((p) => p.body_id === body.bodyId);
  if (reported && finiteVector(reported.r_km)) return kmToScene(reported.r_km);
  const first =
    body.bodyId &&
    plan?.bodies.find((p) => p.body_id === body.bodyId)?.states[0];
  if (first && finiteVector(first.r_km)) return kmToScene(first.r_km);
  return [
    Math.cos(body.angle) * body.displayOrbitAU * 10,
    0,
    -Math.sin(body.angle) * body.displayOrbitAU * 10,
  ];
}

