/**
 * Plan §19.2 + §19.3 — date always top-right.
 * Mission → snapshot.date_utc (estimate in blackout).
 * Overview → free-running calendar date from the NASA track.
 */

type Props = {
  /** Absolute date to show (mission or calendar). */
  dateUtc: string | null;
  estimated?: boolean;
  /** Optional note under the date (e.g. track end). */
  note?: string | null;
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function formatParts(d: Date): { date: string; time: string } {
  return {
    date: d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }),
    time: `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`,
  };
}

export function DateTimeCorner({ dateUtc, estimated, note }: Props) {
  let date = "—";
  let time = "";
  if (dateUtc) {
    const d = new Date(dateUtc);
    if (!Number.isNaN(d.getTime())) {
      const parts = formatParts(d);
      date = parts.date;
      time = parts.time;
    } else {
      date = dateUtc.slice(0, 10);
      time = dateUtc.slice(11, 19) ? `${dateUtc.slice(11, 19)} UTC` : "";
    }
  }

  return (
    <div
      className={estimated ? "date-corner estimate" : "date-corner"}
      aria-label={estimated ? "Mission date estimate" : "Mission date and time"}
    >
      <span className="date-corner-label">
        {estimated ? "Date · estimate" : "Date · UTC"}
      </span>
      <span className="date-corner-value">{date}</span>
      {time ? <span className="date-corner-time">{time}</span> : null}
      {note ? <span className="date-corner-note">{note}</span> : null}
    </div>
  );
}
