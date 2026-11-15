import type { MissionPlan, PlanSummary } from "../api/missionTypes";
import type { ShuttleClass } from "./fleetMock";

function matchesClass(plan: MissionPlan, shuttleClass: ShuttleClass): boolean {
  const isp = plan.vehicle?.isp_s ?? 450;
  return shuttleClass === "long_range" ? isp >= 700 : isp < 700;
}

/** Presentation catalogue uses departure_tick 5 (or 500 after timescale regen). */
function isPresentation(plan: MissionPlan): boolean {
  const dep = plan.ticks?.departure_tick;
  return dep === 5 || dep === 500;
}

function score(plan: MissionPlan): number {
  let s = 0;
  if (isPresentation(plan)) s += 100;
  if ((plan.data_mode ?? "") === "nasa_cached") s += 10;
  return s;
}

export type RouteUnavailable = "ok" | "none" | "out_of_range";

/**
 * Prefer catalogue presentation plans for the selected shuttle class.
 * Avoids the legacy ~126 s Earth→Mars plans when a presentation twin exists.
 */
export async function selectPresentationRoutes(
  summaries: PlanSummary[],
  opts: {
    originBodyId: string;
    destinationBodyId: string;
    shuttleClass: ShuttleClass;
  },
  fetchPlan: (planId: string) => Promise<MissionPlan>,
): Promise<{
  least_fuel: MissionPlan | null;
  earliest_arrival: MissionPlan | null;
  unavailable: RouteUnavailable;
}> {
  const pairSummaries = summaries.filter(
    (p) =>
      p.origin_body_id === opts.originBodyId &&
      p.destination_body_id === opts.destinationBodyId,
  );
  if (!pairSummaries.length) {
    return { least_fuel: null, earliest_arrival: null, unavailable: "none" };
  }

  const loaded = (
    await Promise.all(
      pairSummaries.slice(0, 16).map(async (s) => {
        try {
          return await fetchPlan(s.plan_id);
        } catch {
          return null;
        }
      }),
    )
  ).filter((p): p is MissionPlan => Boolean(p));

  const forClass = loaded.filter((p) => matchesClass(p, opts.shuttleClass));
  if (!forClass.length) {
    const otherHas = loaded.some((p) => !matchesClass(p, opts.shuttleClass));
    return {
      least_fuel: null,
      earliest_arrival: null,
      unavailable: otherHas ? "out_of_range" : "none",
    };
  }

  const ranked = [...forClass].sort((a, b) => score(b) - score(a));
  const least =
    ranked.find((p) => p.objectives_won?.includes("least_fuel")) ?? null;
  const fast =
    ranked.find((p) => p.objectives_won?.includes("earliest_arrival")) ?? null;

  return {
    least_fuel: least,
    earliest_arrival: fast,
    unavailable: least || fast ? "ok" : "out_of_range",
  };
}

export function unavailableMessage(
  reason: RouteUnavailable,
  hasDockedShuttle: boolean,
): string | null {
  if (!hasDockedShuttle) return "No shuttle docked here";
  if (reason === "ok") return null;
  if (reason === "out_of_range") return "Out of range for this shuttle";
  return "Route not computed";
}
