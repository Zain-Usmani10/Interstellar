export type BodyId = "399" | "499";
export type PlanetTargetId = `planet.${BodyId}`;
export type TargetId = PlanetTargetId | "planet.more_details" | "navigation.back";

export type FactSource = {
  name: string;
  url?: string | null;
  retrieved_utc?: string | null;
};

export type ApiFact = {
  key: string;
  label: string;
  value: number | string | null;
  unit: string | null;
  note?: string;
  source: FactSource | string;
};

export type ApiPlanetInfo = {
  schema_version: number;
  body_id: BodyId;
  name: string;
  scene_epoch_jd_tdb: number;
  facts: ApiFact[];
  orbital_state: {
    availability: "available" | "unavailable" | "error";
    epoch_jd_tdb: number | null;
    r_km: [number, number, number] | null;
    v_km_s: [number, number, number] | null;
    frame?: {
      center?: string;
      ref_system?: string;
      ref_plane?: string;
      units?: string;
    };
    provenance?: {
      mode?: string | null;
      source?: FactSource | null;
    };
    note?: string;
  };
  conditions: {
    scope: "earth" | "mars";
    kind: "natural_hazard_events" | "current_weather";
    label: string;
    availability: "available" | "empty" | "unavailable" | "error";
    delivery: "live_fetch" | "cached" | "mock" | null;
    observed_from_utc: string | null;
    observed_to_utc: string | null;
    retrieved_utc: string | null;
    note: string;
    items: Array<{
      id: string;
      title: string;
      category: string;
      date_utc?: string;
      source_url?: string;
    }>;
  };
};

export type InputContext = {
  schema_version: number;
  context_id: string;
  revision: number;
  input_session_id: string;
  capability: string;
  screen: string;
  selected_body_id: BodyId | null;
  allowed_targets: TargetId[];
  enabled: boolean;
  expires_in_ms: number;
};

export type SelectionEventData = {
  selected_body_id: BodyId | null;
  screen: string;
  context_revision: number;
  source: string;
  event_id?: string | null;
};

export type WsEnvelope =
  | { type: "hello"; server_seq: number; data: Record<string, unknown> }
  | { type: "selection"; server_seq: number; data: SelectionEventData }
  | { type: "mission_snapshot"; server_seq: number; data: Record<string, unknown> }
  | { type: "job_update"; server_seq: number; data: Record<string, unknown> }
  | { type: "transport"; server_seq: number; data: Record<string, unknown> }
  | { type: string; server_seq: number; data: unknown };
