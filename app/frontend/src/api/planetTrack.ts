import { apiFetch } from "./http";

export type PlanetTrackResponse = {
  schema_version?: number;
  frame?: unknown;
  data_mode?: string;
  start_jd_tdb: number;
  end_jd_tdb: number;
  step_days: number;
  epochs_jd_tdb: number[];
  planets: Array<{
    body_id: string;
    r_km: Array<[number, number, number]>;
  }>;
};

export async function getPlanetTrack(args: {
  start_jd_tdb: number;
  end_jd_tdb: number;
  step_days?: number;
}): Promise<PlanetTrackResponse> {
  const params = new URLSearchParams({
    start_jd_tdb: String(args.start_jd_tdb),
    end_jd_tdb: String(args.end_jd_tdb),
    step_days: String(args.step_days ?? 1),
  });
  return apiFetch(`/api/v1/planets/track?${params}`);
}

export {
  interpolateTrack,
  type TrackSample,
} from "./planetTrackMath";
