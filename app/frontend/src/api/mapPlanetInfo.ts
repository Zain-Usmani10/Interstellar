import type { ApiPlanetInfo } from "./types";
import {
  formatFactSource,
  formatFactValue,
  getPlanetByTargetId,
  type PlanetInfo as MockPlanetInfo,
} from "../mock/planetInfo";

/** Card view model used by PlanetInfoCard (API or mock). */
export type PlanetCardModel = {
  body_id: "399" | "499";
  target_id: "planet.399" | "planet.499";
  name: string;
  scene_epoch_jd_tdb: number;
  scene_epoch_utc_label: string;
  data_mode_label: string;
  facts: Array<{
    key: string;
    label: string;
    display_value: string;
    note?: string;
    source_label: string;
  }>;
  orbital: {
    availability: string;
    frame_label: string;
    r_km: [number, number, number] | null;
    v_km_s: [number, number, number] | null;
    provenance_note: string;
  };
  conditions: MockPlanetInfo["conditions"];
};

export function cardFromApi(info: ApiPlanetInfo): PlanetCardModel {
  const frame = info.orbital_state.frame;
  const frameLabel = frame
    ? [frame.ref_system, frame.ref_plane, frame.center, frame.units]
        .filter(Boolean)
        .join(" · ")
    : "frame n/a";
  const provenance =
    info.orbital_state.provenance?.source?.name ??
    info.orbital_state.note ??
    info.orbital_state.provenance?.mode ??
    "provenance n/a";

  return {
    body_id: info.body_id,
    target_id: `planet.${info.body_id}`,
    name: info.name,
    scene_epoch_jd_tdb: info.scene_epoch_jd_tdb,
    scene_epoch_utc_label: `JD TDB ${info.scene_epoch_jd_tdb} (scene epoch)`,
    data_mode_label:
      info.orbital_state.provenance?.mode ??
      info.conditions.delivery ??
      "api",
    facts: info.facts.map((fact) => ({
      key: fact.key,
      label: fact.label,
      display_value: formatFactValue(fact.value, fact.unit),
      note: fact.note,
      source_label: formatFactSource(fact.source),
    })),
    orbital: {
      availability: info.orbital_state.availability,
      frame_label: frameLabel,
      r_km: info.orbital_state.r_km,
      v_km_s: info.orbital_state.v_km_s,
      provenance_note: String(provenance),
    },
    conditions: {
      scope: info.conditions.scope,
      kind: info.conditions.kind,
      label: info.conditions.label,
      availability: info.conditions.availability,
      delivery: info.conditions.delivery,
      observed_from_utc: info.conditions.observed_from_utc,
      observed_to_utc: info.conditions.observed_to_utc,
      retrieved_utc: info.conditions.retrieved_utc,
      note: info.conditions.note,
      items: info.conditions.items ?? [],
    },
  };
}

export function cardFromMock(targetId: "planet.399" | "planet.499"): PlanetCardModel {
  const planet = getPlanetByTargetId(targetId);
  return {
    body_id: planet.body_id,
    target_id: planet.target_id,
    name: planet.name,
    scene_epoch_jd_tdb: planet.scene_epoch_jd_tdb,
    scene_epoch_utc_label: planet.scene_epoch_utc_label,
    data_mode_label: planet.data_mode,
    facts: planet.facts.map((fact) => ({
      key: fact.key,
      label: fact.label,
      display_value: formatFactValue(fact.value, fact.unit),
      note: fact.note,
      source_label: formatFactSource(fact.source),
    })),
    orbital: {
      availability: planet.orbital_state.availability,
      frame_label: planet.orbital_state.frame_label,
      r_km: planet.orbital_state.r_km,
      v_km_s: planet.orbital_state.v_km_s,
      provenance_note: planet.orbital_state.provenance_note,
    },
    conditions: planet.conditions,
  };
}
