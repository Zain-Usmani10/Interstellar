/**
 * Plan §19.2 + issue #62 — date and time always top-right.
 * Mission on controller → snapshot.date_utc (estimate in blackout).
 * No mission → real UTC, ticking. Planets placed for the same date.
 */

import { useEffect, useState } from "react";

type Props = {
  /** Simulation / plan date when a mission is active; null → live UTC clock. */
  missionDateUtc: string | null;
  estimated?: boolean;
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

export function DateTimeCorner({ missionDateUtc, estimated }: Props) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (missionDateUtc) return;
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, [missionDateUtc]);

  let date = "—";
  let time = "";
  if (missionDateUtc) {
    const d = new Date(missionDateUtc);
    if (!Number.isNaN(d.getTime())) {
      const parts = formatParts(d);
      date = parts.date;
      time = parts.time;
    } else {
      date = missionDateUtc.slice(0, 10);
      time = missionDateUtc.slice(11, 19)
        ? `${missionDateUtc.slice(11, 19)} UTC`
        : "";
    }
  } else {
    const parts = formatParts(now);
    date = parts.date;
    time = parts.time;
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
    </div>
  );
}
