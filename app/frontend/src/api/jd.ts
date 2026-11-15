/**
 * Approximate JD_TDB ↔ UTC for GUI calendar work.
 * Backend uses astropy; ~69.184 s TT−UTC offset is enough for day-scale animation.
 */

const JD_UNIX_EPOCH = 2440587.5;
const TDB_MINUS_UTC_DAYS = 69.184 / 86400;

export function utcIsoToJdTdb(iso: string): number | null {
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return null;
  return ms / 86_400_000 + JD_UNIX_EPOCH + TDB_MINUS_UTC_DAYS;
}

export function jdTdbToUtcIso(jd: number): string {
  const ms = (jd - TDB_MINUS_UTC_DAYS - JD_UNIX_EPOCH) * 86_400_000;
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function formatJdUtcDate(jd: number): string {
  const d = new Date((jd - TDB_MINUS_UTC_DAYS - JD_UNIX_EPOCH) * 86_400_000);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
