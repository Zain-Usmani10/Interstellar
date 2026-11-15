export type TrackSample = {
  body_id: string;
  r_km: [number, number, number];
};

/** Linear interpolate planet positions between neighbouring track epochs. Never extrapolates. */
export function interpolateTrack(
  epochs: number[],
  planets: Array<{ body_id: string; r_km: Array<[number, number, number]> }>,
  jd: number,
): TrackSample[] | null {
  if (!epochs.length || !planets.length) return null;
  if (jd < epochs[0] || jd > epochs[epochs.length - 1]) return null;

  let i = 0;
  while (i < epochs.length - 2 && epochs[i + 1] < jd) i += 1;
  const j = Math.min(i + 1, epochs.length - 1);
  const t0 = epochs[i];
  const t1 = epochs[j];
  const u = t1 === t0 ? 0 : (jd - t0) / (t1 - t0);

  const out: TrackSample[] = [];
  for (const body of planets) {
    const a = body.r_km[i];
    const b = body.r_km[j];
    if (!a || !b) return null;
    out.push({
      body_id: body.body_id,
      r_km: [
        a[0] + (b[0] - a[0]) * u,
        a[1] + (b[1] - a[1]) * u,
        a[2] + (b[2] - a[2]) * u,
      ],
    });
  }
  return out;
}
