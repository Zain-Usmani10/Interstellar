type Props = {
  tripDays: number | null;
  daysToArrival: number | null;
  dateUtc: string | null;
  /** Sim days per second after departure — trip_days / 30 from the plan. */
  daysPerSecond: number | null;
  estimated?: boolean;
  visible: boolean;
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Flight progress from confirmed backend trip fields only (§19.3). */
export function FlightProgress({
  tripDays,
  daysToArrival,
  dateUtc,
  daysPerSecond,
  estimated,
  visible,
}: Props) {
  if (!visible) return null;

  const elapsed =
    tripDays != null && daysToArrival != null
      ? Math.max(0, tripDays - daysToArrival)
      : null;
  const progress =
    tripDays != null && tripDays > 0 && elapsed != null
      ? Math.min(1, elapsed / tripDays)
      : 0;

  return (
    <div
      className={estimated ? "flight-progress estimate" : "flight-progress"}
      aria-label="Flight progress"
    >
      <div className="flight-progress-bar" aria-hidden>
        <span style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <div className="flight-progress-row">
        <span>
          {elapsed == null ? "—" : `${elapsed} d elapsed`}
          {daysToArrival != null ? ` · ${daysToArrival} d left` : ""}
          {estimated ? " · estimate" : ""}
        </span>
        <span>{formatDate(dateUtc)}</span>
      </div>
      <div className="flight-progress-speed">
        {daysPerSecond != null && Number.isFinite(daysPerSecond)
          ? `${daysPerSecond.toFixed(1)} d/s`
          : "— d/s"}
      </div>
    </div>
  );
}
