import type { ScenePlan, SceneSnapshot, ScenePlanetPosition } from "./types.ts";
import { finiteVector } from "./flightState.ts";

const IDS = ["199", "299", "399", "499", "599", "699", "799", "899"];
export type PositionReply = {
  epoch_jd_tdb: number;
  date_utc: string;
  data_mode: string;
  frame: { center: string; ref_system: string; ref_plane: string; units: string; time_scale: string };
  planets: ScenePlanetPosition[];
};

/** No browser clock: request the date already shown by the parent/snapshot. */
export function positionQuery(dateUtc: string | null | undefined, plan?: ScenePlan | null, snapshot?: SceneSnapshot | null): string | null {
  if (dateUtc !== undefined) return dateUtc ? `date_utc=${encodeURIComponent(dateUtc)}` : null;
  if (snapshot) {
    const date = snapshot.link.blackout ? snapshot.estimate?.date_utc : snapshot.date_utc;
    return date ? `date_utc=${encodeURIComponent(date)}` : null;
  }
  if (plan?.departure.utc) return `date_utc=${encodeURIComponent(plan.departure.utc)}`;
  return plan && Number.isFinite(plan.departure.jd_tdb) ? `jd_tdb=${plan.departure.jd_tdb}` : null;
}

export function validatePositions(value: PositionReply): PositionReply {
  const frame = value?.frame;
  if (!Number.isFinite(value?.epoch_jd_tdb) || !Number.isFinite(Date.parse(value?.date_utc)) || value?.data_mode !== "nasa_cached" ||
      frame?.center !== "500@10" || frame.ref_system !== "ICRF" || frame.ref_plane !== "ECLIPTIC" ||
      frame.units !== "KM-S" || frame.time_scale !== "TDB" || !Array.isArray(value.planets) ||
      value.planets.length !== 8 || new Set(value.planets.map(p => p.body_id)).size !== 8 ||
      value.planets.some(p => !IDS.includes(p.body_id) || !finiteVector(p.r_km))) {
    throw new Error("Invalid all-planet position response");
  }
  return value;
}

export type PositionResult = { key: string; data?: PositionReply; error?: string };
export class PositionRequest {
  private revision = 0;
  private controller: AbortController | null = null;

  cancel() {
    this.revision++;
    this.controller?.abort();
  }

  async load(key: string, request: (path: string, init: RequestInit) => Promise<PositionReply>): Promise<PositionResult | null> {
    this.cancel();
    const revision = this.revision;
    this.controller = new AbortController();
    const controller = this.controller;
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const data = validatePositions(await request(`/api/v1/planets/positions?${key}`, { signal: controller.signal }));
      const query = new URLSearchParams(key);
      const date = query.get("date_utc"), jd = query.get("jd_tdb");
      if ((date && Math.abs(Date.parse(data.date_utc) - Date.parse(date)) > 1000) ||
          (jd && Math.abs(data.epoch_jd_tdb - Number(jd)) > 1e-7)) {
        throw new Error("Planet response is for a different scene date");
      }
      return revision === this.revision ? { key, data } : null;
    } catch (error) {
      if (revision !== this.revision) return null;
      return { key, error: error instanceof Error ? error.message : "Planet positions unavailable" };
    } finally {
      clearTimeout(timeout);
    }
  }
}
