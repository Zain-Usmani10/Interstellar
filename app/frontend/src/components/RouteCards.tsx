import type { MissionPlan } from "../api/missionTypes";

type Props = {
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  disabled?: boolean;
  /** When true, cards are display-only (To → From). */
  readOnly?: boolean;
  onSelect: (planId: string) => void;
};

function tripDays(plan: MissionPlan): string {
  if (plan.tof_s === undefined || !Number.isFinite(plan.tof_s)) return "—";
  return `${Math.round(plan.tof_s / 86400)}`;
}

function dateLabel(utc: string | undefined): string {
  if (!utc) return "—";
  const d = new Date(utc);
  if (Number.isNaN(d.getTime())) return utc.slice(0, 10);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function fuelKg(plan: MissionPlan): string {
  const need = plan.masses?.propellant_required_kg;
  if (need === undefined || !Number.isFinite(need)) return "—";
  return `${Math.round(need)} kg`;
}

const BLURB: Record<"least_fuel" | "earliest_arrival" | "same", string> = {
  least_fuel: "Saves the most fuel: waits for the planets to line up",
  earliest_arrival: "Gets there fastest: leaves sooner, burns more",
  same: "Best fuel and earliest arrival are the same trip",
};

function Card({
  title,
  blurb,
  plan,
  selected,
  disabled,
  readOnly,
  onSelect,
}: {
  title: string;
  blurb: string;
  plan: MissionPlan;
  selected: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={selected ? "route-glass selected" : "route-glass"}
      disabled={disabled || readOnly}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="route-title">{title}</span>
      <span className="route-blurb">{blurb}</span>
      <dl className="route-metrics">
        <div>
          <dt>Launch</dt>
          <dd>{dateLabel(plan.departure?.utc)}</dd>
        </div>
        <div>
          <dt>Arrival</dt>
          <dd>{dateLabel(plan.arrival?.utc)}</dd>
        </div>
        <div>
          <dt>Trip days</dt>
          <dd>{tripDays(plan)}</dd>
        </div>
        <div>
          <dt>Fuel</dt>
          <dd>{fuelKg(plan)}</dd>
        </div>
      </dl>
    </button>
  );
}

/** Route options: launch / arrival / trip days / fuel for the chosen plan only. */
export function RouteCards({
  leastFuel,
  earliestArrival,
  selectedPlanId,
  disabled,
  readOnly,
  onSelect,
}: Props) {
  if (!leastFuel && !earliestArrival) {
    return (
      <div className="route-cards empty">
        <p>Route being calculated / not available yet.</p>
      </div>
    );
  }

  const sameTrip =
    leastFuel &&
    earliestArrival &&
    leastFuel.plan_id === earliestArrival.plan_id;

  return (
    <div className="route-cards" aria-label="Choose a route">
      {sameTrip && leastFuel ? (
        <Card
          title="Best option"
          blurb={BLURB.same}
          plan={leastFuel}
          selected={selectedPlanId === leastFuel.plan_id}
          disabled={disabled}
          readOnly={readOnly}
          onSelect={() => onSelect(leastFuel.plan_id)}
        />
      ) : (
        <>
          {leastFuel ? (
            <Card
              title="Saves the most fuel"
              blurb={BLURB.least_fuel}
              plan={leastFuel}
              selected={selectedPlanId === leastFuel.plan_id}
              disabled={disabled}
              readOnly={readOnly}
              onSelect={() => onSelect(leastFuel.plan_id)}
            />
          ) : null}
          {earliestArrival ? (
            <Card
              title="Gets there fastest"
              blurb={BLURB.earliest_arrival}
              plan={earliestArrival}
              selected={selectedPlanId === earliestArrival.plan_id}
              disabled={disabled}
              readOnly={readOnly}
              onSelect={() => onSelect(earliestArrival.plan_id)}
            />
          ) : null}
        </>
      )}
    </div>
  );
}
