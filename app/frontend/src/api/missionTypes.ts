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
  vehicle?: {
    label?: string;
    isp_s?: number;
    propellant_capacity_kg?: number;
  };
  ticks?: {
    tick_hz?: number;
    departure_tick?: number;
    arrival_tick?: number;
    end_tick?: number;
  };
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
  | "clear"
  | "blackout_start"
  | "blackout_end";

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
  /** contracts 1.3.0 — shuttle bound to this mission */
  shuttle_id?: string | null;
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
    /** contracts 1.2.0 */
    blackout?: boolean;
  };
  /** contracts 1.2.0 — calendar of confirmed tick */
  date_utc?: string | null;
  trip?: {
    trip_days: number | null;
    days_to_arrival: number | null;
  } | null;
  estimate?: {
    tick: number;
    epoch_jd_tdb: number | null;
    date_utc?: string | null;
    days_to_arrival: number | null;
    spacecraft: {
      phase: string;
      r_km: Vec3 | null;
    };
    fuel_remaining_g: number;
    expected_events: Array<"departure" | "capture">;
  } | null;
  reconciliation?: {
    blackout_start_tick: number;
    blackout_end_tick: number;
    events_during_blackout: Array<string | { event: string }>;
    estimate_matched: boolean;
    differences: string[];
  } | null;
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
