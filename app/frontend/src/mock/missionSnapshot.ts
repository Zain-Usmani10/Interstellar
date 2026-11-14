/**
 * Mock MissionSnapshot-shaped status until contracts/runtime are wired.
 * Never claim RUNNING/COMPLETE without real snapshot evidence.
 */

export type MissionSnapshotMock = {
  schema_version: number;
  data_mode: "mock";
  controller_source: "simulator";
  state: "IDLE";
  mission_id: null;
  tick: number;
  executed_mask: number;
  fuel_remaining_g: number | null;
  fault_counts: {
    masked: number;
    no_majority: number;
    rx_error: number;
  };
  freshness: "no_link";
  nasa_ephemeris: "mock";
  input_source: "mouse";
  note: string;
};

export const MOCK_SNAPSHOT: MissionSnapshotMock = {
  schema_version: 1,
  data_mode: "mock",
  controller_source: "simulator",
  state: "IDLE",
  mission_id: null,
  tick: 0,
  executed_mask: 0,
  fuel_remaining_g: null,
  fault_counts: { masked: 0, no_majority: 0, rx_error: 0 },
  freshness: "no_link",
  nasa_ephemeris: "mock",
  input_source: "mouse",
  note: "No board telemetry in this UI milestone. State stays IDLE until a real MissionSnapshot arrives.",
};
