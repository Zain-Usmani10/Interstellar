import type { MissionPlan } from "../api/missionTypes";

type Props = {
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  disabled?: boolean;
  onSelect: (planId: string) => void;
};

function daysFromTof(tofS: number | undefined): string {
  if (tofS === undefined || !Number.isFinite(tofS)) return "—";
  // Display only: plan stores seconds; show whole days from that field.
  return `${Math.round(tofS / 86400)} days`;
}

function fuelFraction(plan: MissionPlan): number {
  const need = plan.masses?.propellant_required_kg;
  const cap = plan.vehicle?.propellant_capacity_kg;
  if (
    need === undefined ||
    cap === undefined ||
    !Number.isFinite(need) ||
    !Number.isFinite(cap) ||
    cap <= 0
  ) {
    return 0.35;
  }
  return Math.min(1, Math.max(0.08, need / cap));
}

function dateLabel(utc: string | undefined): string {
  if (!utc) return "—";
  return utc.slice(0, 10);
}

function Card({
  title,
  plan,
  selected,
  disabled,
  onSelect,
}: {
  title: string;
  plan: MissionPlan;
  selected: boolean;
  disabled?: boolean;
  onSelect: () => void;
}) {
  const frac = fuelFraction(plan);
  return (
    <button
      type="button"
      className={selected ? "route-glass selected" : "route-glass"}
      disabled={disabled}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="route-title">{title}</span>
      <span className="route-time">{daysFromTof(plan.tof_s)}</span>
      <span className="route-dates">
        {dateLabel(plan.departure?.utc)} → {dateLabel(plan.arrival?.utc)}
      </span>
      <span className="fuel-bar" aria-hidden="true">
        <span className="fuel-fill" style={{ width: `${frac * 100}%` }} />
      </span>
      <span className="route-fuel-label">
        Fuel needed (from plan)
        {plan.masses?.propellant_required_kg !== undefined
          ? ` · ${plan.masses.propellant_required_kg.toFixed(0)} kg`
          : ""}
      </span>
    </button>
  );
}

export function RouteCards({
  leastFuel,
  earliestArrival,
  selectedPlanId,
  disabled,
  onSelect,
}: Props) {
  if (!leastFuel && !earliestArrival) {
    return (
      <div className="route-cards empty">
        <p>Route being calculated / not available yet.</p>
      </div>
    );
  }
  return (
    <div className="route-cards" aria-label="Choose a route">
      {leastFuel ? (
        <Card
          title="Saves the most fuel"
          plan={leastFuel}
          selected={selectedPlanId === leastFuel.plan_id}
          disabled={disabled}
          onSelect={() => onSelect(leastFuel.plan_id)}
        />
      ) : null}
      {earliestArrival ? (
        <Card
          title="Gets there fastest"
          plan={earliestArrival}
          selected={selectedPlanId === earliestArrival.plan_id}
          disabled={disabled}
          onSelect={() => onSelect(earliestArrival.plan_id)}
        />
      ) : null}
    </div>
  );
}
