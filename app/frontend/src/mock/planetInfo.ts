/**
 * Mock PlanetInfo-shaped fixtures until Agent 1 schemas + Agent 2 data land.
 * Labelled MOCK — not live NASA / Horizons / EONET.
 */

export type PlanetTargetId = "planet.399" | "planet.499";

export type Fact = {
  key: string;
  label: string;
  value: string;
  unit: string;
  source: string;
};

export type OrbitalState = {
  frame: string;
  center: string;
  units: string;
  epoch_jd_tdb: number;
  position_km: [number, number, number];
  velocity_km_s: [number, number, number];
  provenance: string;
};

export type Conditions = {
  scope: string;
  kind: string;
  availability: "available" | "empty" | "unavailable" | "error";
  delivery: "live_fetch" | "cached" | "mock";
  observed_utc: string | null;
  retrieved_utc: string | null;
  items: Array<{ id: string; title: string; category: string; source: string }>;
  note: string;
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
        value: "6371",
        unit: "km",
        source: "MOCK — replace with NASA/JPL facts",
      },
      {
        key: "atmosphere",
        label: "Atmosphere",
        value: "N2/O2 dominated",
        unit: "",
        source: "MOCK — replace with sourced dataset",
      },
      {
        key: "gm",
        label: "GM (illustrative)",
        value: "3.986004418e5",
        unit: "km³/s²",
        source: "MOCK — not a Horizons pull",
      },
    ],
    orbital_state: {
      frame: "ICRF / ecliptic (mock)",
      center: "500@10 (Sun)",
      units: "KM-S",
      epoch_jd_tdb: 2461000.5,
      position_km: [149597870.7, 0, 0],
      velocity_km_s: [0, 29.78, 0],
      provenance: "MOCK fixture — not NASA/JPL Horizons",
    },
    conditions: {
      scope: "Earth",
      kind: "natural_hazard_events",
      availability: "unavailable",
      delivery: "mock",
      observed_utc: null,
      retrieved_utc: null,
      items: [],
      note: "MOCK: EONET Earth hazard events not wired yet. Empty/unavailable is not an all-clear.",
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
        value: "3389.5",
        unit: "km",
        source: "MOCK — replace with NASA/JPL facts",
      },
      {
        key: "atmosphere",
        label: "Atmosphere",
        value: "Thin CO2",
        unit: "",
        source: "MOCK — replace with sourced dataset",
      },
      {
        key: "gm",
        label: "GM (illustrative)",
        value: "4.282837e4",
        unit: "km³/s²",
        source: "MOCK — not a Horizons pull",
      },
    ],
    orbital_state: {
      frame: "ICRF / ecliptic (mock)",
      center: "500@10 (Sun)",
      units: "KM-S",
      epoch_jd_tdb: 2461000.5,
      position_km: [227939200, 0, 22400000],
      velocity_km_s: [0, 24.07, 0],
      provenance: "MOCK fixture — not NASA/JPL Horizons",
    },
    conditions: {
      scope: "Mars",
      kind: "surface_weather",
      availability: "unavailable",
      delivery: "mock",
      observed_utc: null,
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
