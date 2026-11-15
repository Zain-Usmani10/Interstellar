/**
 * Layout placeholder for §18.7 days-to-arrival / T-minus.
 * Values must come from snapshot `trip` / `estimate` (and plan departure_tick for
 * T-minus) after contracts 1.2.0 — never invent mission numbers here.
 */

type Props = {
  daysToArrival: number | null;
  tripDays: number | null;
  tMinusLabel: string | null;
  estimated?: boolean;
  preview?: boolean;
};

export function TripReadout({
  daysToArrival,
  tripDays,
  tMinusLabel,
  estimated,
  preview,
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
      {preview ? (
        <p className="trip-preview-tag">Layout preview · not live telemetry</p>
      ) : null}
    </div>
  );
}
