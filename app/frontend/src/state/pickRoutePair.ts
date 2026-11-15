import type { PlanSummary } from "../api/missionTypes";

const MODE_PREF = ["nasa_cached", "cached", "live_fetch", "synthetic"] as const;

/**
 * Pick one least_fuel + one earliest_arrival from the same data_mode so the
 * comparison is apples-to-apples (backend may also list a synthetic fixture).
 * Optionally filter by origin/destination body ids (contracts 1.1.0).
 */
export function pickRoutePair(
  plans: PlanSummary[],
  opts?: { originBodyId?: string; destinationBodyId?: string },
): {
  least_fuel: PlanSummary | null;
  earliest_arrival: PlanSummary | null;
  data_mode: string | null;
} {
  const filtered = plans.filter((plan) => {
    if (opts?.originBodyId && plan.origin_body_id !== opts.originBodyId) {
      return false;
    }
    if (
      opts?.destinationBodyId &&
      plan.destination_body_id !== opts.destinationBodyId
    ) {
      return false;
    }
    return true;
  });

  const byMode = new Map<string, { least?: PlanSummary; fast?: PlanSummary }>();

  for (const plan of filtered) {
    const mode = plan.data_mode ?? "unknown";
    const bucket = byMode.get(mode) ?? {};
    if (plan.objectives_won?.includes("least_fuel") && !bucket.least) {
      bucket.least = plan;
    }
    if (plan.objectives_won?.includes("earliest_arrival") && !bucket.fast) {
      bucket.fast = plan;
    }
    byMode.set(mode, bucket);
  }

  for (const mode of MODE_PREF) {
    const bucket = byMode.get(mode);
    if (bucket?.least && bucket.fast) {
      return {
        least_fuel: bucket.least,
        earliest_arrival: bucket.fast,
        data_mode: mode,
      };
    }
  }

  for (const [mode, bucket] of byMode) {
    if (bucket.least && bucket.fast) {
      return {
        least_fuel: bucket.least,
        earliest_arrival: bucket.fast,
        data_mode: mode,
      };
    }
  }

  // Incomplete pair: prefer nasa_cached singles, then anything.
  const preferredModes = [...MODE_PREF, ...byMode.keys()];
  let least: PlanSummary | null = null;
  let fast: PlanSummary | null = null;
  for (const mode of preferredModes) {
    const bucket = byMode.get(mode);
    if (!least && bucket?.least) least = bucket.least;
    if (!fast && bucket?.fast) fast = bucket.fast;
  }
  return {
    least_fuel: least,
    earliest_arrival: fast,
    data_mode: least?.data_mode ?? fast?.data_mode ?? null,
  };
}
