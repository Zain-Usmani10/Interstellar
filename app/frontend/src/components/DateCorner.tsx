/**
 * Plan §19.2 — calendar date always in a screen corner.
 * From snapshot.date_utc; during blackout estimate.date_utc (marked estimate);
 * before a mission, the selected plan's departure date.
 */

type Props = {
  dateUtc: string | null;
  estimated?: boolean;
};

function formatDate(utc: string): string {
  const d = new Date(utc);
  if (Number.isNaN(d.getTime())) return utc.slice(0, 10);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function DateCorner({ dateUtc, estimated }: Props) {
  return (
    <div
      className={estimated ? "date-corner estimate" : "date-corner"}
      aria-label={estimated ? "Mission date estimate" : "Mission date"}
    >
      <span className="date-corner-label">
        {estimated ? "Date · estimate" : "Date"}
      </span>
      <span className="date-corner-value">
        {dateUtc ? formatDate(dateUtc) : "—"}
      </span>
    </div>
  );
}
