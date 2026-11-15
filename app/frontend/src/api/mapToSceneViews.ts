/**
 * Map API MissionPlan / MissionSnapshot → Affan's ScenePlan / SceneSnapshot
 * (app/frontend/src/scene/types.ts on 19-scene-graphics). Kept local so this
 * PR does not touch Affan's scene tree; swap the import once his types land on
 * the branch we build against.
 */

import type { MissionPlan, MissionSnapshot, Vec3 } from "./missionTypes";

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
  outcome: "pending" | "captured" | "uncaptured" | "aborted" | "plan_invalid" | "lost";
};

function asBodyId(id: string | undefined, fallback: SceneBodyId): SceneBodyId {
  return id === "399" || id === "499" ? id : fallback;
}

function asVec3(v: number[] | null | undefined): Vec3 | null {
  if (!v || v.length < 3) return null;
  return [v[0], v[1], v[2]];
}

export function toScenePlan(plan: MissionPlan | null): ScenePlan | null {
  if (!plan?.nominal_path?.length) return null;
  const origin = asBodyId(plan.origin_body_id, "399");
  const destination = asBodyId(plan.destination_body_id, "499");
  const departureJd = plan.departure?.jd_tdb ?? plan.nominal_path[0]?.jd_tdb;
  if (departureJd === undefined) return null;

  const bodies = (plan.bodies ?? [])
    .filter((b) => b.body_id === "399" || b.body_id === "499")
    .map((b) => ({
      body_id: b.body_id as SceneBodyId,
      states: b.states.map((s) => ({
        jd_tdb: s.jd_tdb,
        r_km: asVec3(s.r_km) ?? ([0, 0, 0] as Vec3),
      })),
    }));

  return {
    plan_id: plan.plan_id,
    plan_sha256: plan.plan_sha256 ?? "",
    data_mode: plan.data_mode ?? "unknown",
    origin_body_id: origin,
    destination_body_id: destination,
    departure: { jd_tdb: departureJd },
    nominal_path: plan.nominal_path.map((s) => ({
      jd_tdb: s.jd_tdb,
      r_km: asVec3(s.r_km) ?? ([0, 0, 0] as Vec3),
    })),
    bodies,
  };
}

export function toSceneSnapshot(
  snapshot: MissionSnapshot | null,
): SceneSnapshot | null {
  if (!snapshot) return null;
  const planets = (snapshot.planets ?? [])
    .filter((p) => p.body_id === "399" || p.body_id === "499")
    .map((p) => ({
      body_id: p.body_id as SceneBodyId,
      r_km: asVec3(p.r_km) ?? ([0, 0, 0] as Vec3),
    }));

  return {
    server_seq: snapshot.server_seq,
    mission_id: snapshot.mission_id,
    plan_id: snapshot.plan_id,
    plan_sha256: snapshot.plan_sha256 ?? "",
    controller_label: snapshot.controller_label,
    state: snapshot.state,
    tick: snapshot.tick,
    executed_mask: snapshot.executed_mask,
    spacecraft: {
      phase: snapshot.spacecraft.phase,
      r_km: asVec3(snapshot.spacecraft.r_km),
      v_km_s: asVec3(snapshot.spacecraft.v_km_s),
    },
    planets,
    link: {
      transport_state: snapshot.link?.transport_state ?? "unknown",
      observed_age_ms: snapshot.link?.observed_age_ms ?? null,
    },
    outcome: (snapshot.outcome as SceneSnapshot["outcome"]) ?? "pending",
  };
}
