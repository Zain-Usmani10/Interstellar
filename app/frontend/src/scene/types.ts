/** Rendering-only views of the canonical v1 contracts; no API/state ownership. */
export type Vec3 = [number, number, number];
export type SceneBodyId = "199" | "299" | "399" | "499" | "599" | "699" | "799" | "899";

export type SceneShuttle = {
  id: string;
  name: string;
  class: "standard" | "long_range";
  body_id: SceneBodyId | null;
  status: "docked" | "in_flight" | "lost";
};
export type ScenePlanetPosition = { body_id: SceneBodyId; r_km: Vec3 };

export type ScenePlan = {
  plan_id: string;
  plan_sha256: string;
  data_mode: string;
  origin_body_id: SceneBodyId;
  destination_body_id: SceneBodyId;
  departure: { jd_tdb: number };
  ticks?: { departure_tick: number; arrival_tick: number; end_tick: number };
  nominal_path: { jd_tdb: number; r_km: Vec3 }[];
  bodies: { body_id: SceneBodyId; states: { jd_tdb: number; r_km: Vec3 }[] }[];
};

export type SceneSnapshot = {
  server_seq: number;
  mission_id: string;
  plan_id: string;
  plan_sha256: string;
  controller_label: "FPGA" | "SIMULATED CONTROLLER";
  state:
    | "UNKNOWN"
    | "IDLE"
    | "LOADED"
    | "ARMED"
    | "RUNNING"
    | "SAFE"
    | "COMPLETE"
    | "ABORTED";
  tick: number;
  shuttle_id?: string | null;
  executed_mask: number;
  spacecraft: {
    phase: "at_origin" | "coast" | "captured" | "uncaptured_coast" | "unknown";
    r_km: Vec3 | null;
    v_km_s: Vec3 | null;
  };
  planets: { body_id: SceneBodyId; r_km: Vec3 }[];
  link: { transport_state: string; observed_age_ms: number | null; blackout?: boolean };
  estimate?: {
    tick: number;
    epoch_jd_tdb: number;
    spacecraft: { phase: string; r_km: Vec3 | null };
  } | null;
  outcome:
    "pending" | "captured" | "uncaptured" | "aborted" | "plan_invalid" | "lost";
};
