/** Rendering-only views of the canonical v1 contracts; no API/state ownership. */
export type Vec3 = [number, number, number];
export type SceneBodyId = "399" | "499";

export type ScenePlan = {
  plan_id: string;
  plan_sha256: string;
  data_mode: string;
  origin_body_id: SceneBodyId;
  destination_body_id: SceneBodyId;
  departure: { jd_tdb: number };
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
  executed_mask: number;
  spacecraft: {
    phase: "at_origin" | "coast" | "captured" | "uncaptured_coast" | "unknown";
    r_km: Vec3 | null;
    v_km_s: Vec3 | null;
  };
  planets: { body_id: SceneBodyId; r_km: Vec3 }[];
  link: { transport_state: string; observed_age_ms: number | null };
  outcome:
    "pending" | "captured" | "uncaptured" | "aborted" | "plan_invalid" | "lost";
};
