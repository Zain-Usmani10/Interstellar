/**
 * Map API MissionPlan / MissionSnapshot → Affan's ScenePlan / SceneSnapshot.
 * Coordinates stay in km; the scene owns axis mapping.
 */

import type {
  SceneBodyId,
  ScenePlan,
  SceneSnapshot,
  Vec3,
} from "../scene/types";
import type { MissionPlan, MissionSnapshot } from "./missionTypes";

export type { ScenePlan, SceneSnapshot } from "../scene/types";

const BODY_IDS: SceneBodyId[] = [
  "199",
  "299",
  "399",
  "499",
  "599",
  "699",
  "799",
  "899",
];

function asBodyId(id: string | undefined, fallback: SceneBodyId): SceneBodyId {
  if (id && (BODY_IDS as string[]).includes(id)) return id as SceneBodyId;
  return fallback;
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
    .filter((b) => (BODY_IDS as string[]).includes(b.body_id))
    .map((b) => ({
      body_id: b.body_id as SceneBodyId,
      states: b.states.map((s) => ({
        jd_tdb: s.jd_tdb,
        r_km: asVec3(s.r_km) ?? ([0, 0, 0] as Vec3),
      })),
    }));

  const ticks =
    plan.ticks?.departure_tick != null &&
    plan.ticks.arrival_tick != null &&
    plan.ticks.end_tick != null
      ? {
          departure_tick: plan.ticks.departure_tick,
          arrival_tick: plan.ticks.arrival_tick,
          end_tick: plan.ticks.end_tick,
        }
      : undefined;

  return {
    plan_id: plan.plan_id,
    plan_sha256: plan.plan_sha256 ?? "",
    data_mode: plan.data_mode ?? "unknown",
    origin_body_id: origin,
    destination_body_id: destination,
    departure: { jd_tdb: departureJd },
    ticks,
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
    .filter((p) => (BODY_IDS as string[]).includes(p.body_id))
    .map((p) => ({
      body_id: p.body_id as SceneBodyId,
      r_km: asVec3(p.r_km) ?? ([0, 0, 0] as Vec3),
    }));

  const estimate = snapshot.estimate
    ? {
        tick: snapshot.estimate.tick,
        epoch_jd_tdb: snapshot.estimate.epoch_jd_tdb ?? 0,
        spacecraft: {
          phase: snapshot.estimate.spacecraft.phase,
          r_km: asVec3(snapshot.estimate.spacecraft.r_km),
        },
      }
    : null;

  return {
    server_seq: snapshot.server_seq,
    mission_id: snapshot.mission_id,
    plan_id: snapshot.plan_id,
    plan_sha256: snapshot.plan_sha256 ?? "",
    controller_label: snapshot.controller_label,
    state: snapshot.state,
    tick: snapshot.tick,
    shuttle_id: snapshot.shuttle_id ?? null,
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
      blackout: Boolean(snapshot.link?.blackout),
    },
    estimate,
    outcome: (snapshot.outcome as SceneSnapshot["outcome"]) ?? "pending",
  };
}
