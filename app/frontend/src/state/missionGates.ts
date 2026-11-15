import type { MissionSnapshot } from "../api/missionTypes";

/** Which operator buttons the current MissionSnapshot.state allows. */
export function missionActionGates(snapshot: MissionSnapshot | null) {
  const state = snapshot?.state ?? null;
  const hasMission = Boolean(snapshot?.mission_id);

  return {
    canCreate:
      !hasMission ||
      state === "IDLE" ||
      state === "UNKNOWN" ||
      state === null,
    canUpload: hasMission && (state === "IDLE" || state === "UNKNOWN"),
    canArm: hasMission && state === "LOADED",
    canStart: hasMission && state === "ARMED",
    canAbort:
      hasMission &&
      (state === "LOADED" ||
        state === "ARMED" ||
        state === "RUNNING" ||
        state === "SAFE"),
    canClear:
      hasMission &&
      state !== null &&
      state !== "RUNNING" &&
      state !== "UNKNOWN",
  };
}
