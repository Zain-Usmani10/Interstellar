/**
 * Plan §18.7 — days-to-arrival / T-minus from snapshot (+ plan departure_tick).
 * Never invent mission numbers beyond formatting confirmed fields.
 */

type Props = {
  daysToArrival: number | null;
  tripDays: number | null;
  tMinusLabel: string | null;
  estimated?: boolean;
};

export function TripReadout({
  daysToArrival,
  tripDays,
  tMinusLabel,
  estimated,
}: Props) {
  return (
    <div
      className={estimated ? "trip-readout estimate" : "trip-readout"}
      aria-label="Trip timing"
    >
      <div className="trip-metric">
        <span className="trip-metric-label">
          Days to arrival{estimated ? " · estimate" : ""}
        </span>
        <span className="trip-metric-value">
          {daysToArrival == null ? "—" : daysToArrival}
          {tripDays != null ? (
            <span className="trip-metric-sub"> / {tripDays} trip</span>
          ) : null}
        </span>
      </div>
      <div className="trip-metric">
        <span className="trip-metric-label">T-minus</span>
        <span className="trip-metric-value">{tMinusLabel ?? "—"}</span>
      </div>
    </div>
  );
}
