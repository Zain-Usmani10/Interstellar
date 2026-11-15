/**
 * Mock PlanetInfo-shaped fixtures until backend PlanetInfo is wired.
 * Labelled MOCK — not live NASA / Horizons / EONET.
 * Fact rows match contracts v1: render via label/value/unit/note only (do not hardcode keys).
 */

export type PlanetTargetId = "planet.399" | "planet.499";

export type FactSource = {
  name: string;
  url?: string | null;
  retrieved_utc?: string | null;
};

export type Fact = {
  key: string;
  label: string;
  value: number | string | null;
  unit: string | null;
  note?: string;
  source: FactSource | string;
};

export type OrbitalState = {
  availability: "available" | "unavailable" | "error";
  epoch_jd_tdb: number | null;
  r_km: [number, number, number] | null;
  v_km_s: [number, number, number] | null;
  frame_label: string;
  provenance_note: string;
};

export type Conditions = {
  scope: "earth" | "mars";
  kind: "natural_hazard_events" | "current_weather";
  label: string;
  availability: "available" | "empty" | "unavailable" | "error";
  delivery: "live_fetch" | "cached" | "mock" | null;
  /** Observation window — not the mission/scene epoch. */
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

export type PlanetInfo = {
  schema_version: number;
  body_id: "399" | "499";
  target_id: PlanetTargetId;
  name: string;
  scene_epoch_jd_tdb: number;
  scene_epoch_utc_label: string;
  display_color: string;
  /** Illustrative scene radius in display units — not to scale. */
  display_radius: number;
  /** Heliocentric position in display units (1 au = 10). Scientific → Three.js via axis map. */
  display_position_au_scaled: [number, number, number];
  facts: Fact[];
  orbital_state: OrbitalState;
  conditions: Conditions;
  data_mode: "mock";
};

/** 1 au = 10 display units (MAIN_BACKEND_FPGA_TASKS §12). */
export const AU_DISPLAY = 10;

const MOCK_SOURCE: FactSource = {
  name: "MOCK fixture — not NASA/JPL Horizons",
  url: null,
  retrieved_utc: null,
};

export function formatFactValue(value: Fact["value"], unit: Fact["unit"]): string {
  if (value === null || value === undefined) return "—";
  const text =
    typeof value === "number"
      ? Number.isInteger(value)
        ? String(value)
        : value.toPrecision(6)
      : String(value);
  return unit ? `${text} ${unit}` : text;
}

export function formatFactSource(source: Fact["source"]): string {
  return typeof source === "string" ? source : source.name;
}

export const PLANETS: PlanetInfo[] = [
  {
    schema_version: 1,
    body_id: "399",
    target_id: "planet.399",
    name: "Earth",
    scene_epoch_jd_tdb: 2461000.5,
    scene_epoch_utc_label: "2026-11-15 00:00 UTC (mock epoch)",
    display_color: "#3d7ea6",
    display_radius: 0.35,
    display_position_au_scaled: [AU_DISPLAY * 1.0, 0, 0],
    facts: [
      {
        key: "mean_radius",
        label: "Mean radius",
        value: 6371.01,
        unit: "km",
        source: MOCK_SOURCE,
      },
      {
        key: "mean_temperature",
        label: "Mean surface temperature",
        value: 287.6,
        unit: "K",
        note: "Long-term mean, not a current weather reading",
        source: MOCK_SOURCE,
      },
      {
        key: "gm",
        label: "Gravitational parameter (GM)",
        value: 398600.435436,
        unit: "km^3/s^2",
        source: MOCK_SOURCE,
      },
    ],
    orbital_state: {
      availability: "available",
      epoch_jd_tdb: 2461000.5,
      r_km: [149597870.7, 0, 0],
      v_km_s: [0, 29.78, 0],
      frame_label: "ICRF / ecliptic (mock)",
      provenance_note: "MOCK fixture — not NASA/JPL Horizons",
    },
    conditions: {
      scope: "earth",
      kind: "natural_hazard_events",
      label: "Earth natural hazard events",
      availability: "unavailable",
      delivery: "mock",
      observed_from_utc: null,
      observed_to_utc: null,
      retrieved_utc: null,
      items: [],
      note: "MOCK: EONET Earth hazard events not wired yet. Unavailable is not an all-clear. Observation times below (when present) are not the mission epoch.",
    },
    data_mode: "mock",
  },
  {
    schema_version: 1,
    body_id: "499",
    target_id: "planet.499",
    name: "Mars",
    scene_epoch_jd_tdb: 2461000.5,
    scene_epoch_utc_label: "2026-11-15 00:00 UTC (mock epoch)",
    display_color: "#c45c3a",
    display_radius: 0.28,
    display_position_au_scaled: [AU_DISPLAY * 1.52, 0, AU_DISPLAY * 0.15],
    facts: [
      {
        key: "mean_radius",
        label: "Mean radius",
        value: 3389.92,
        unit: "km",
        source: MOCK_SOURCE,
      },
      {
        key: "mean_temperature",
        label: "Mean temperature",
        value: 210,
        unit: "K",
        note: "Long-term mean, not a current weather reading",
        source: MOCK_SOURCE,
      },
      {
        key: "gm",
        label: "Gravitational parameter (GM)",
        value: 42828.375662,
        unit: "km^3/s^2",
        source: MOCK_SOURCE,
      },
    ],
    orbital_state: {
      availability: "available",
      epoch_jd_tdb: 2461000.5,
      r_km: [227939200, 0, 22400000],
      v_km_s: [0, 24.07, 0],
      frame_label: "ICRF / ecliptic (mock)",
      provenance_note: "MOCK fixture — not NASA/JPL Horizons",
    },
    conditions: {
      scope: "mars",
      kind: "current_weather",
      label: "Mars current weather",
      availability: "unavailable",
      delivery: "mock",
      observed_from_utc: null,
      observed_to_utc: null,
      retrieved_utc: null,
      items: [],
      note: "Current Mars weather unavailable (InSight ended 2022). MOCK panel does not invent live weather.",
    },
    data_mode: "mock",
  },
];

export function getPlanetByTargetId(targetId: PlanetTargetId): PlanetInfo {
  const found = PLANETS.find((p) => p.target_id === targetId);
  if (!found) {
    throw new Error(`Unknown target ${targetId}`);
  }
  return found;
}
