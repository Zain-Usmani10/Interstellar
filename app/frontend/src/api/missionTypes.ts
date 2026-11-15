/**
 * Canonical MissionPlan / MissionSnapshot fields used by mission control + scene.
 */

export type Vec3 = [number, number, number];

export type PathSample = {
  jd_tdb: number;
  r_km: Vec3;
  v_km_s?: Vec3;
};

export type PlanBodyState = {
  body_id: string;
  name?: string;
  states: PathSample[];
};

export type PlanEpoch = {
  jd_tdb?: number;
  utc?: string;
};

export type MissionPlan = {
  schema_version: number;
  plan_id: string;
  plan_sha256?: string;
  data_mode?: string;
  objectives_won?: string[];
  departure?: PlanEpoch;
  arrival?: PlanEpoch;
  tof_s?: number;
  dv?: { dv_total_km_s?: number };
  masses?: { propellant_required_kg?: number };
  vehicle?: { propellant_capacity_kg?: number };
  nominal_path: PathSample[];
  uncaptured_coast_path?: PathSample[];
  bodies?: PlanBodyState[];
  origin_body_id?: string;
  destination_body_id?: string;
};

export type PlanSummary = {
  plan_id: string;
  objectives_won?: string[];
  origin_body_id?: string;
  destination_body_id?: string;
  data_mode?: string;
  departure?: PlanEpoch;
  arrival?: PlanEpoch;
  dv_total_km_s?: number;
  propellant_required_kg?: number;
};

export type MissionCommand =
  | "upload"
  | "arm"
  | "start"
  | "abort"
  | "clear";

export type SimFaultKind = "single" | "divergence";

export type CommandResult = {
  command: MissionCommand;
  applied: boolean;
  detail: string;
  snapshot: MissionSnapshot;
};

export type MissionSnapshot = {
  schema_version: number;
  server_seq: number;
  mission_id: string;
  plan_id: string;
  plan_sha256?: string;
  controller_source: "fpga" | "simulator";
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
  departure_executed_tick: number | null;
  capture_executed_tick: number | null;
  fuel_remaining_g: number;
  safe_reason?: string;
  faults?: {
    masked_fault_count: number;
    no_majority_count: number;
    rx_error_count: number;
  };
  link?: {
    transport_state: string;
    observed_age_ms: number | null;
    view?: string;
    delay_demo_s?: number | null;
    delay_physical_s?: number | null;
  };
  epoch_jd_tdb: number | null;
  spacecraft: {
    phase: "at_origin" | "coast" | "captured" | "uncaptured_coast" | "unknown";
    r_km: Vec3 | null;
    v_km_s: Vec3 | null;
  };
  planets?: Array<{ body_id: string; r_km: Vec3 }>;
  outcome?: string;
  failure?: { code: string; message: string } | null;
};

export type FaultHistoryEntry = {
  id: string;
  at_seq: number;
  kind: string;
  detail: string;
};
