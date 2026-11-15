import type { MissionPlan } from "../api/missionTypes";

type Props = {
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  disabled?: boolean;
  onSelect: (planId: string) => void;
};

function planTitle(plan: MissionPlan, fallback: string) {
  const won = plan.objectives_won ?? [];
  if (won.includes("least_fuel")) return "Most fuel-efficient";
  if (won.includes("earliest_arrival")) return "Fastest";
  return fallback;
}

function RouteCard({
  plan,
  selected,
  disabled,
  onSelect,
  fallbackTitle,
}: {
  plan: MissionPlan;
  selected: boolean;
  disabled?: boolean;
  onSelect: () => void;
  fallbackTitle: string;
}) {
  const dv = plan.dv?.dv_total_km_s;
  const fuel = plan.masses?.propellant_required_kg;
  return (
    <button
      type="button"
      className={selected ? "route-card selected" : "route-card"}
      disabled={disabled}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <p className="eyebrow">{planTitle(plan, fallbackTitle)}</p>
      <p className="route-meta">
        Δv {dv === undefined ? "n/a" : `${dv} km/s`} · fuel{" "}
        {fuel === undefined ? "n/a" : `${fuel} kg`}
      </p>
      <p className="muted">
        depart {plan.departure?.utc ?? "n/a"}
        <br />
        arrive {plan.arrival?.utc ?? "n/a"}
        <br />
        tof_s {plan.tof_s ?? "n/a"}
      </p>
      <p className="muted">data: {plan.data_mode ?? "?"}</p>
    </button>
  );
}

export function RouteCompare({
  leastFuel,
  earliestArrival,
  selectedPlanId,
  disabled,
  onSelect,
}: Props) {
  if (!leastFuel && !earliestArrival) {
    return (
      <section className="route-compare" aria-label="Route comparison">
        <h3>Route comparison</h3>
        <p className="muted">No plans from GET /api/v1/plans.</p>
      </section>
    );
  }

  return (
    <section className="route-compare" aria-label="Route comparison">
      <h3>Route comparison</h3>
      <p className="muted">
        Numbers are taken from the plan — nothing is computed in the browser.
        Selected plan is passed to the 3D scene.
      </p>
      <div className="route-grid">
        {leastFuel ? (
          <RouteCard
            plan={leastFuel}
            selected={selectedPlanId === leastFuel.plan_id}
            disabled={disabled}
            fallbackTitle="Most fuel-efficient"
            onSelect={() => onSelect(leastFuel.plan_id)}
          />
        ) : null}
        {earliestArrival ? (
          <RouteCard
            plan={earliestArrival}
            selected={selectedPlanId === earliestArrival.plan_id}
            disabled={disabled}
            fallbackTitle="Fastest"
            onSelect={() => onSelect(earliestArrival.plan_id)}
          />
        ) : null}
      </div>
    </section>
  );
}
