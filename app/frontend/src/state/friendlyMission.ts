import type { MissionSnapshot } from "../api/missionTypes";

/** Plain-language mission words for visitors — never invent RUNNING without a snapshot. */
export function friendlyMissionLabel(snapshot: MissionSnapshot | null): string {
  if (!snapshot) return "Ready to prepare";
  switch (snapshot.state) {
    case "IDLE":
    case "UNKNOWN":
      return "Ready";
    case "LOADED":
      return "Prepared — ready to arm";
    case "ARMED":
      return "Armed — ready to launch";
    case "RUNNING": {
      if (snapshot.spacecraft.phase === "coast") return "Flying to Mars";
      if (snapshot.spacecraft.phase === "at_origin") return "Waiting at Earth";
      if (snapshot.spacecraft.phase === "captured") return "Arrived";
      if (snapshot.spacecraft.phase === "uncaptured_coast") return "Missed capture — coasting";
      return "Mission running";
    }
    case "COMPLETE":
      return snapshot.outcome === "captured" ? "Arrived" : "Mission complete";
    case "SAFE":
      return "Safe mode";
    case "ABORTED":
      return "Aborted";
    default:
      return snapshot.state;
  }
}

export type GuidedStep = "prepare" | "arm" | "launch" | "done";

export function guidedStep(snapshot: MissionSnapshot | null): GuidedStep {
  const state = snapshot?.state;
  if (!snapshot || state === "IDLE" || state === "UNKNOWN") return "prepare";
  if (state === "LOADED") return "arm";
  if (state === "ARMED") return "launch";
  return "done";
}
