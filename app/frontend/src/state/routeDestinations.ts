import type { PlanSummary } from "../api/missionTypes";
import type { PlanetBodyId } from "./planetBodies";

/** Destinations that have at least one stored plan from this origin. */
export function destinationsWithRoute(
  summaries: PlanSummary[],
  originBodyId: PlanetBodyId,
): Set<PlanetBodyId> {
  const out = new Set<PlanetBodyId>();
  for (const plan of summaries) {
    if (plan.origin_body_id !== originBodyId) continue;
    const dest = plan.destination_body_id;
    if (dest) out.add(dest as PlanetBodyId);
  }
  return out;
}

/** Origins that have at least one stored plan into this destination. */
export function originsWithRoute(
  summaries: PlanSummary[],
  destinationBodyId: PlanetBodyId,
): Set<PlanetBodyId> {
  const out = new Set<PlanetBodyId>();
  for (const plan of summaries) {
    if (plan.destination_body_id !== destinationBodyId) continue;
    const origin = plan.origin_body_id;
    if (origin) out.add(origin as PlanetBodyId);
  }
  return out;
}
