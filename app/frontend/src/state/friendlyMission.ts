import type { MissionSnapshot } from "../api/missionTypes";

/** Plain-language mission words for visitors — never invent RUNNING without a snapshot. */
export function friendlyMissionLabel(
  snapshot: MissionSnapshot | null,
  destinationName?: string | null,
): string {
  if (!snapshot) return "Ready to prepare";
  const dest = destinationName || "destination";
  switch (snapshot.state) {
    case "IDLE":
    case "UNKNOWN":
      return "Ready";
    case "LOADED":
      return "Prepared — ready to arm";
    case "ARMED":
      return "Armed — ready to launch";
    case "RUNNING": {
      if (snapshot.spacecraft.phase === "coast") return `Flying to ${dest}`;
      if (snapshot.spacecraft.phase === "at_origin") return "Waiting at origin";
      if (snapshot.spacecraft.phase === "captured") return "Arrived";
      if (snapshot.spacecraft.phase === "uncaptured_coast")
        return "Missed capture — coasting";
      return "Mission running";
    }
    case "COMPLETE":
      return snapshot.outcome === "captured" ? "Arrived" : "Mission complete";
    case "SAFE":
      return "Safe mode";
    case "ABORTED":
      return "Aborted — start over to continue";
    default:
      return snapshot.state;
  }
}

export type GuidedStep = "prepare" | "arm" | "launch" | "reset" | "done";

export function guidedStep(snapshot: MissionSnapshot | null): GuidedStep {
  const state = snapshot?.state;
  if (state === "ABORTED" || state === "COMPLETE" || state === "SAFE") {
    return "reset";
  }
  if (!snapshot || state === "IDLE" || state === "UNKNOWN") return "prepare";
  if (state === "LOADED") return "arm";
  if (state === "ARMED") return "launch";
  return "done";
}
