"""Regenerate every contract fixture deterministically.

Run from the repo root:   python -m app.contracts.tools.generate

Writes:
  app/contracts/fixtures/frames/*.bin, *.hex, manifest.json   golden wire frames
  app/contracts/fixtures/*.json                                one valid example per schema

The MissionPlan fixture is SYNTHETIC: circular coplanar planet orbits and a Hohmann-type
ellipse computed here with Kepler's equation. It has the right shape, units and internal
consistency for building against, and is labelled data_mode "synthetic". It is not NASA data
and not a validated route; the NASA owner replaces it with a real cached plan.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from app.contracts import protocol_v1 as p

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FRAMES = FIXTURES / "frames"

# ----------------------------------------------------------------- mock constants
AU_KM = 149597870.7
MU_SUN = 132712440041.279419   # km^3/s^2, mock copy; NASA owner supplies the sourced value
MU_EARTH = 398600.435507
MU_MARS = 42828.375816
G0 = 9.80665
R_EARTH_ORBIT = 1.0 * AU_KM
R_MARS_ORBIT = 1.523679 * AU_KM
DEPART_JD_TDB = 2461359.5      # 2026-11-15 00:00 TDB
THETA0 = 0.9                   # Earth's heliocentric angle at departure (rad), arbitrary
DEPARTURE_TICK, ARRIVAL_TICK, END_TICK = 10, 12010, 12610

PLAN_ID = "0b7f1c3e-5a2d-4e8b-9c41-7d6a2f3b8e10"
MISSION_UUID = "5d0c9a54-3f1e-4b7a-8a66-2c1e9f4d7b03"
CONTEXT_ID = "9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"
INPUT_SESSION_ID = "c3d4e5f6-a7b8-4c9d-8e0f-1a2b3c4d5e6f"
SESSION = 0x1A2B3C4D           # wire session id used in the golden frames
MISSION = 0x00C0FFEE           # wire mission id used in the golden frames

FRAME = {"center": "500@10", "ref_system": "ICRF", "ref_plane": "ECLIPTIC",
         "units": "KM-S", "time_scale": "TDB"}
MOCK_SOURCE = {"name": "Interstellar contract fixture generator (synthetic, not NASA data)",
               "url": "app/contracts/tools/generate.py", "retrieved_utc": None,
               "sha256": None, "api_signature": None}
FACT_SOURCE = {"name": "NASA Planetary Fact Sheet (NSSDCA)",
               "url": "https://nssdc.gsfc.nasa.gov/planetary/factsheet/",
               "retrieved_utc": None, "sha256": None, "api_signature": None}


def r3(v):
    return [round(x, 3) for x in v]


def v9(v):
    return [round(x, 9) for x in v]


def utc_label(jd_tdb: float) -> str:
    """Approximate UTC label for a TDB Julian date (TDB - UTC taken as 69.184 s). Mock only."""
    t = datetime(2000, 1, 1, 12) + timedelta(days=jd_tdb - 2451545.0) - timedelta(seconds=69.184)
    return t.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def circular_state(radius: float, angle_at_ref: float, jd_ref: float, jd: float):
    n = math.sqrt(MU_SUN / radius ** 3)
    a = angle_at_ref + n * (jd - jd_ref) * 86400.0
    speed = math.sqrt(MU_SUN / radius)
    return ([radius * math.cos(a), radius * math.sin(a), 0.0],
            [-speed * math.sin(a), speed * math.cos(a), 0.0])


class Transfer:
    """Ellipse from Earth's orbit (periapsis at THETA0) to Mars' orbit (apoapsis)."""

    def __init__(self):
        self.a = (R_EARTH_ORBIT + R_MARS_ORBIT) / 2
        self.e = (R_MARS_ORBIT - R_EARTH_ORBIT) / (R_MARS_ORBIT + R_EARTH_ORBIT)
        self.n = math.sqrt(MU_SUN / self.a ** 3)
        self.tof_s = math.pi / self.n

    def state(self, t_s: float):
        """Heliocentric state t_s seconds after departure (two-body, Kepler's equation)."""
        m = self.n * t_s
        ecc = m
        for _ in range(50):
            ecc -= (ecc - self.e * math.sin(ecc) - m) / (1 - self.e * math.cos(ecc))
        r = self.a * (1 - self.e * math.cos(ecc))
        x, y = self.a * (math.cos(ecc) - self.e), self.a * math.sqrt(1 - self.e ** 2) * math.sin(ecc)
        k = math.sqrt(MU_SUN * self.a) / r
        vx, vy = -k * math.sin(ecc), k * math.sqrt(1 - self.e ** 2) * math.cos(ecc)
        c, s = math.cos(THETA0), math.sin(THETA0)
        return [c * x - s * y, s * x + c * y, 0.0], [c * vx - s * vy, s * vx + c * vy, 0.0]


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def build_plan() -> dict:
    tr = Transfer()
    tof_s = tr.tof_s
    arrive_jd = DEPART_JD_TDB + tof_s / 86400.0
    spt = tof_s / (ARRIVAL_TICK - DEPARTURE_TICK)

    def epoch(tick):
        return DEPART_JD_TDB + (tick - DEPARTURE_TICK) * spt / 86400.0

    def earth(jd):
        return circular_state(R_EARTH_ORBIT, THETA0, DEPART_JD_TDB, jd)

    def mars(jd):
        return circular_state(R_MARS_ORBIT, THETA0 + math.pi, arrive_jd, jd)

    def sample(jd):
        r, v = tr.state((jd - DEPART_JD_TDB) * 86400.0)
        return {"jd_tdb": round(jd, 6), "r_km": r3(r), "v_km_s": v9(v)}

    r_e, v_e = earth(DEPART_JD_TDB)
    r_m, v_m = mars(arrive_jd)
    _, v1 = tr.state(0.0)
    r_end, v2 = tr.state(tof_s)

    v_inf_dep, v_inf_arr = norm(sub(v1, v_e)), norm(sub(v2, v_m))
    r_park_e = (MU_EARTH * (43200 / (2 * math.pi)) ** 2) ** (1 / 3)
    r_park_m = (MU_MARS * (43200 / (2 * math.pi)) ** 2) ** (1 / 3)
    dv_dep = math.sqrt(v_inf_dep ** 2 + 2 * MU_EARTH / r_park_e) - math.sqrt(MU_EARTH / r_park_e)
    dv_cap = math.sqrt(v_inf_arr ** 2 + 2 * MU_MARS / r_park_m) - math.sqrt(MU_MARS / r_park_m)

    dry, payload, isp, capacity = 1000.0, 100.0, 450.0, 10000.0
    m_final = dry + payload
    prop = m_final * math.expm1((dv_dep + dv_cap) * 1000 / (isp * G0))
    m0 = m_final + prop
    m_after_dep = m0 * math.exp(-dv_dep * 1000 / (isp * G0))
    dep_kg, cap_kg = m0 - m_after_dep, m_after_dep - m_final
    dep_g, cap_g = math.ceil(dep_kg * 1000), math.ceil(cap_kg * 1000)

    n_path = 65
    nominal = [sample(DEPART_JD_TDB + (arrive_jd - DEPART_JD_TDB) * i / (n_path - 1)) for i in range(n_path)]
    end_jd = epoch(END_TICK)
    coast = [sample(arrive_jd + (end_jd - arrive_jd) * i / 8) for i in range(9)]

    def body_states(fn):
        out, jd = [], DEPART_JD_TDB - 1.0
        while True:
            r, v = fn(jd)
            out.append({"jd_tdb": round(jd, 6), "r_km": r3(r), "v_km_s": v9(v)})
            if jd >= end_jd:
                return out
            jd += 4.0

    plan = {
        "schema_version": 1,
        "plan_id": PLAN_ID,
        "model_version": "two-body-lambert-v1",
        "data_mode": "synthetic",
        "origin_body_id": "399",
        "destination_body_id": "499",
        "objectives_won": ["least_fuel"],
        "departure": {"utc": utc_label(DEPART_JD_TDB), "jd_tdb": DEPART_JD_TDB},
        "arrival": {"utc": utc_label(arrive_jd), "jd_tdb": round(arrive_jd, 6)},
        "tof_s": round(tof_s, 3),
        "frame": FRAME,
        "constants": {"mu_sun_km3_s2": MU_SUN, "mu_origin_km3_s2": MU_EARTH,
                      "mu_destination_km3_s2": MU_MARS, "g0_m_s2": G0,
                      "source": "MOCK copy of JPL-style values for fixture arithmetic only; not sourced"},
        "boundary": {"origin_r_km": r3(r_e), "origin_v_km_s": v9(v_e),
                     "destination_r_km": r3(r_m), "destination_v_km_s": v9(v_m),
                     "lambert_v1_km_s": v9(v1), "lambert_v2_km_s": v9(v2)},
        "dv": {"v_inf_depart_km_s": round(v_inf_dep, 6), "v_inf_arrive_km_s": round(v_inf_arr, 6),
               "r_park_origin_km": round(r_park_e, 3), "r_park_destination_km": round(r_park_m, 3),
               "dv_depart_km_s": round(dv_dep, 6), "dv_capture_km_s": round(dv_cap, 6),
               "dv_total_km_s": round(dv_dep + dv_cap, 6)},
        "vehicle": {"label": "Hypothetical chemical vehicle (not a NASA spacecraft)",
                    "dry_mass_kg": dry, "payload_mass_kg": payload, "isp_s": isp,
                    "propellant_capacity_kg": capacity},
        "masses": {"m_final_kg": m_final, "propellant_required_kg": round(prop, 6),
                   "departure_propellant_kg": round(dep_kg, 6), "capture_propellant_kg": round(cap_kg, 6)},
        "wire": {"initial_fuel_g": dep_g + cap_g, "departure_fuel_g": dep_g, "capture_fuel_g": cap_g},
        "ticks": {"tick_hz": 100, "departure_tick": DEPARTURE_TICK, "arrival_tick": ARRIVAL_TICK,
                  "end_tick": END_TICK, "seconds_per_tick": spt},
        "residuals": {"position_km": round(norm(sub(r_end, r_m)), 6), "velocity_km_s": 0.0,
                      "min_heliocentric_radius_km": round(R_EARTH_ORBIT, 3), "passed": True},
        "grid": {"departure_start_utc": utc_label(DEPART_JD_TDB), "departure_end_utc": utc_label(DEPART_JD_TDB),
                 "tof_min_days": round(tof_s / 86400, 3), "tof_max_days": round(tof_s / 86400, 3),
                 "n_departures": 1, "n_durations": 1, "n_feasible": 1},
        "nominal_path": nominal,
        "uncaptured_coast_path": coast,
        "bodies": [{"body_id": "399", "name": "Earth", "states": body_states(earth)},
                   {"body_id": "499", "name": "Mars", "states": body_states(mars)}],
        "provenance": {"sources": [MOCK_SOURCE],
                       "notes": "SYNTHETIC FIXTURE. Circular coplanar planets and a Hohmann-type ellipse. "
                                "Not NASA data, not a validated route. Residuals are self-consistency of the "
                                "generator, not an independent propagation check."},
    }
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    plan["plan_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    plan["_helpers"] = (tr, earth, mars, epoch)   # removed before writing
    return plan


def build_snapshots(plan: dict, wire_plan: p.Plan) -> dict:
    tr, earth, mars, epoch = plan["_helpers"]
    w = plan["wire"]

    def snap(seq, state, tick, mask, dep_tick, cap_tick, fuel, phase, outcome, safe="NONE",
             no_majority=0, age=40, transport="connected"):
        jd = epoch(tick)
        if phase == "at_origin":
            r, v = earth(jd)
        elif phase == "captured":
            r, v = mars(jd)
        else:
            r, v = tr.state((jd - plan["departure"]["jd_tdb"]) * 86400.0)
        delay_phys = norm(sub(r, earth(jd)[0])) / 299792.458
        return {
            "schema_version": 1, "server_seq": seq, "mission_id": MISSION_UUID,
            "plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"],
            "wire": {"session_id": SESSION, "mission_id": MISSION, "plan_crc16": wire_plan.crc16()},
            "controller_source": "simulator", "controller_label": "SIMULATED CONTROLLER",
            "state": state, "tick": tick, "executed_mask": mask,
            "departure_executed_tick": dep_tick, "capture_executed_tick": cap_tick,
            "fuel_remaining_g": fuel, "safe_reason": safe,
            "faults": {"masked_fault_count": 0, "no_majority_count": no_majority, "rx_error_count": 0},
            "link": {"transport_state": transport, "observed_age_ms": age, "view": "ground_delayed",
                     "delay_demo_s": round(min(3.0, max(0.1, delay_phys / 300)), 3),
                     "delay_physical_s": round(delay_phys, 3)},
            "epoch_jd_tdb": round(jd, 6),
            "spacecraft": {"phase": phase, "r_km": r3(r), "v_km_s": v9(v)},
            "planets": [{"body_id": "399", "r_km": r3(earth(jd)[0])},
                        {"body_id": "499", "r_km": r3(mars(jd)[0])}],
            "outcome": outcome, "failure": None,
        }

    after_dep = w["initial_fuel_g"] - w["departure_fuel_g"]
    return {
        "mission_snapshot_loaded": snap(3, "LOADED", 0, 0, None, None, w["initial_fuel_g"], "at_origin", "pending"),
        "mission_snapshot_running_coast": snap(641, "RUNNING", 6000, 1, 10, None, after_dep, "coast", "pending"),
        "mission_snapshot_complete": snap(1290, "COMPLETE", 12010, 3, 10, 12010, 0, "captured", "captured"),
        "mission_snapshot_safe_uncaptured": snap(1355, "SAFE", 12610, 1, 10, None, after_dep,
                                                 "uncaptured_coast", "uncaptured", safe="NO_MAJORITY", no_majority=1),
    }


def build_planet_info(plan: dict) -> dict:
    _, earth, mars, _ = plan["_helpers"]
    jd = plan["departure"]["jd_tdb"]

    def fact(key, label, value, unit, note=None):
        f = {"key": key, "label": label, "value": value, "unit": unit, "source": FACT_SOURCE}
        if note:
            f["note"] = note
        return f

    def orbital(fn):
        r, v = fn(jd)
        return {"availability": "available", "epoch_jd_tdb": jd, "r_km": r3(r), "v_km_s": v9(v),
                "frame": FRAME, "provenance": {"mode": "synthetic", "source": MOCK_SOURCE}}

    climate = "Long-term mean, not a current weather reading"
    earth_info = {
        "schema_version": 1, "body_id": "399", "name": "Earth", "scene_epoch_jd_tdb": jd,
        "facts": [fact("diameter", "Diameter", 12756, "km"),
                  fact("mass", "Mass", 5.97e24, "kg"),
                  fact("surface_gravity", "Surface gravity", 9.8, "m/s^2"),
                  fact("length_of_day", "Length of day", 24.0, "h"),
                  fact("orbital_period", "Orbital period", 365.2, "days"),
                  fact("distance_from_sun", "Mean distance from Sun", 149.6e6, "km"),
                  fact("mean_temperature", "Mean temperature", 15, "degC", climate),
                  fact("moons", "Moons", 1, None)],
        "orbital_state": orbital(earth),
        "conditions": {
            "scope": "earth", "kind": "natural_hazard_events", "label": "Earth natural hazard events",
            "availability": "available", "delivery": "cached",
            "observed_from_utc": "2026-10-15T00:00:00Z", "observed_to_utc": "2026-11-14T00:00:00Z",
            "retrieved_utc": "2026-11-14T00:00:00Z",
            "items": [{"id": "MOCK_EONET_0001", "title": "MOCK wildfire event (fixture, not a real event)",
                       "category": "wildfires", "date_utc": "2026-11-10T00:00:00Z",
                       "coordinates": [-120.5, 38.2], "source_url": "https://eonet.gsfc.nasa.gov/docs/v3"},
                      {"id": "MOCK_EONET_0002", "title": "MOCK severe storm event (fixture, not a real event)",
                       "category": "severeStorms", "date_utc": "2026-11-12T06:00:00Z",
                       "coordinates": [135.0, 18.5], "source_url": "https://eonet.gsfc.nasa.gov/docs/v3"}],
            "note": "SYNTHETIC FIXTURE items. Real data: NASA EONET v3 dated events. An empty list is not an "
                    "all-clear; these observations do not describe the simulated mission epoch.",
            "provenance": {"mode": "synthetic", "source": MOCK_SOURCE},
        },
    }
    mars_info = {
        "schema_version": 1, "body_id": "499", "name": "Mars", "scene_epoch_jd_tdb": jd,
        "facts": [fact("diameter", "Diameter", 6792, "km"),
                  fact("mass", "Mass", 0.642e24, "kg"),
                  fact("surface_gravity", "Surface gravity", 3.7, "m/s^2"),
                  fact("length_of_day", "Length of day", 24.7, "h"),
                  fact("orbital_period", "Orbital period", 687.0, "days"),
                  fact("distance_from_sun", "Mean distance from Sun", 228.0e6, "km"),
                  fact("mean_temperature", "Mean temperature", -65, "degC", climate),
                  fact("moons", "Moons", 2, None)],
        "orbital_state": orbital(mars),
        "conditions": {
            "scope": "mars", "kind": "current_weather", "label": "Current Mars weather",
            "availability": "unavailable", "delivery": None,
            "observed_from_utc": None, "observed_to_utc": None, "retrieved_utc": None, "items": [],
            "note": "No current Mars surface weather source is integrated. NASA InSight ended in 2022; "
                    "its old measurements are not live data.",
            "provenance": {"mode": None, "source": None},
        },
    }
    return {"planet_info_399": earth_info, "planet_info_499": mars_info}


def build_input_fixtures() -> dict:
    context = {"schema_version": 1, "context_id": CONTEXT_ID, "revision": 7,
               "input_session_id": INPUT_SESSION_ID, "capability": "planet_explore",
               "screen": "planet_choice", "selected_body_id": None,
               "allowed_targets": ["planet.399", "planet.499"], "enabled": True, "expires_in_ms": 10000}
    info_context = dict(context, revision=8, screen="planet_info", selected_body_id="499",
                        allowed_targets=["planet.more_details", "navigation.back"])
    base = {"schema_version": 1, "input_session_id": INPUT_SESSION_ID, "context_id": CONTEXT_ID,
            "context_revision": 7, "target_id": "planet.499"}
    return {
        "planets": {"schema_version": 1, "planets": [
            {"body_id": "399", "name": "Earth", "target_id": "planet.399"},
            {"body_id": "499", "name": "Mars", "target_id": "planet.499"}]},
        "input_context_planet_choice": context,
        "input_context_planet_info": info_context,
        "selection_intent_mouse": dict(base, event_id="11111111-2222-4333-8444-555555555555", source="mouse"),
        "selection_intent_synthetic": dict(
            base, event_id="66666666-7777-4888-8999-aaaaaaaaaaaa", source="synthetic",
            evidence={"window_start_source_ms": 102000, "window_end_source_ms": 104000, "sample_count": 500,
                      "sample_rate_hz": 250, "winner_score": 0.71, "runner_up_score": 0.28, "quality": "valid"}),
        "intent_result_accepted": {"event_id": "66666666-7777-4888-8999-aaaaaaaaaaaa", "accepted": True,
                                   "reason": "accepted", "new_context_revision": 8},
        "intent_result_stale": {"event_id": "11111111-2222-4333-8444-555555555555", "accepted": False,
                                "reason": "stale_context", "new_context_revision": 8},
        "input_heartbeat": {"context_id": CONTEXT_ID, "context_revision": 7, "source_state": "ready",
                            "acquisition_age_ms": 40, "stimulus_ready": True},
    }


# ----------------------------------------------------------------- golden frames

def build_frames(wire_plan: p.Plan) -> tuple[list[dict], dict[str, bytes]]:
    T, D, R, S = p.MsgType, p.Detail, p.Result, p.State
    crc = wire_plan.crc16()
    after_dep = wire_plan.initial_fuel_g - wire_plan.departure_fuel_g
    entries: list[dict] = []
    blobs: dict[str, bytes] = {}

    def add(name, direction, msg_type, seq, session, payload, fields, note):
        data = p.encode_frame(msg_type, seq, session, payload)
        blobs[name] = data
        entries.append({"name": name, "valid": True, "direction": direction,
                        "type": T(msg_type).name, "type_hex": f"{msg_type:02X}", "sequence": seq,
                        "session_id": session, "payload_length": len(payload), "fields": fields,
                        "note": note, "hex": data.hex(" ").upper()})

    def host(name, msg_type, seq, session, payload=b"", fields=None, note=""):
        add(name, "host_to_board", msg_type, seq, session, payload, fields or {}, note)

    def ack(name, seq, original, result, detail, mission, tick, plan_crc, note, session=SESSION):
        a = p.Ack(original, result, detail, mission, tick, plan_crc)
        add(name, "board_to_host", T.ACK, seq, session, a.pack(),
            {"original_type": T(original).name, "result": R(result).name, "detail": D(detail).name,
             "mission_id": mission, "applied_tick": tick, "plan_crc16": plan_crc}, note)

    def status(name, tseq, session, st: p.Status, note):
        f = {k: getattr(st, k) for k in st.__dataclass_fields__}
        f["state"] = S(st.state).name
        f["safe_reason"] = p.SafeReason(st.safe_reason).name
        add(name, "board_to_host", T.STATUS, tseq, session, st.pack(), f, note)

    mission_fields = {"mission_id": MISSION}
    mid = p.pack_u32(MISSION)

    host("01_discover", T.DISCOVER, 0, 0, note="Read-only. Board answers with STATUS.")
    status("02_status_after_reset", 0, 0, p.Status(), "Reply to DISCOVER right after power-up: session 0, IDLE, no plan.")
    host("03_open_session", T.OPEN_SESSION, 0, 0, p.pack_u32(SESSION), {"new_session_id": SESSION},
         "Header session 0, sequence 0.")
    ack("04_ack_open_session", 0, T.OPEN_SESSION, R.APPLIED, D.OK, 0, 0, 0, "Header carries the new session.")
    host("05_get_status", T.GET_STATUS, 0, SESSION, note="Read-only, sequence 0.")
    host("06_load_plan", T.LOAD_PLAN, 1, SESSION, wire_plan.pack(),
         {k: getattr(wire_plan, k) for k in wire_plan.__dataclass_fields__}, "First mutation: sequence 1.")
    ack("07_ack_load_plan", 1, T.LOAD_PLAN, R.APPLIED, D.OK, MISSION, 0, crc, "Staged only. plan_crc16 of staged plan.")
    host("08_commit_plan", T.COMMIT_PLAN, 2, SESSION, p.pack_commit(MISSION, crc),
         {"mission_id": MISSION, "plan_crc16": crc})
    ack("09_ack_commit_plan", 2, T.COMMIT_PLAN, R.APPLIED, D.OK, MISSION, 0, crc, "State is now LOADED.")
    status("10_status_loaded", 17, SESSION,
           p.Status(MISSION, 0, S.LOADED, fuel_remaining_g=wire_plan.initial_fuel_g, plan_crc16=crc), "")
    host("11_arm", T.ARM, 3, SESSION, mid, mission_fields)
    ack("12_ack_arm", 3, T.ARM, R.APPLIED, D.OK, MISSION, 0, crc, "")
    host("13_start", T.START, 4, SESSION, mid, mission_fields)
    ack("14_ack_start", 4, T.START, R.APPLIED, D.OK, MISSION, 0, crc, "Tick counter reset; RUNNING.")
    status("15_status_running_before_departure", 30, SESSION,
           p.Status(MISSION, 5, S.RUNNING, fuel_remaining_g=wire_plan.initial_fuel_g, plan_crc16=crc), "")
    status("16_status_running_after_departure", 631, SESSION,
           p.Status(MISSION, 6000, S.RUNNING, p.MASK_DEPARTURE, fuel_remaining_g=after_dep,
                    departure_executed_tick=wire_plan.departure_tick, plan_crc16=crc), "")
    status("17_status_complete", 1233, SESSION,
           p.Status(MISSION, wire_plan.arrival_tick, S.COMPLETE, p.MASK_DEPARTURE | p.MASK_CAPTURE,
                    fuel_remaining_g=after_dep - wire_plan.capture_fuel_g,
                    departure_executed_tick=wire_plan.departure_tick,
                    capture_executed_tick=wire_plan.arrival_tick, plan_crc16=crc),
           "Capture executed at the planned tick; clock stops.")
    status("18_status_running_single_fault_masked", 640, SESSION,
           p.Status(MISSION, 6100, S.RUNNING, p.MASK_DEPARTURE, fuel_remaining_g=after_dep,
                    departure_executed_tick=wire_plan.departure_tick, masked_fault_count=1, plan_crc16=crc),
           "INJECT_SINGLE: majority held, counter incremented, mission continues.")
    status("19_status_safe_no_majority", 700, SESSION,
           p.Status(MISSION, 7000, S.SAFE, p.MASK_DEPARTURE, p.SafeReason.NO_MAJORITY, after_dep,
                    wire_plan.departure_tick, p.UNSET_TICK, 0, 1, 0, crc),
           "INJECT_DIVERGENCE after departure: burns inhibited, clock keeps running to end_tick.")
    host("20_abort", T.ABORT, 5, SESSION, mid, mission_fields)
    ack("21_ack_abort", 5, T.ABORT, R.APPLIED, D.OK, MISSION, 7200, crc, "applied_tick = board tick when applied.")
    status("22_status_aborted", 725, SESSION,
           p.Status(MISSION, 7250, S.ABORTED, p.MASK_DEPARTURE, fuel_remaining_g=after_dep,
                    departure_executed_tick=wire_plan.departure_tick, plan_crc16=crc), "")
    host("23_clear", T.CLEAR, 6, SESSION, mid, mission_fields)
    ack("24_ack_clear", 6, T.CLEAR, R.APPLIED, D.OK, MISSION, 0, 0, "Plan invalidated, IDLE.")
    ack("25_nack_start_bad_state", 3, T.START, R.REJECTED, D.BAD_STATE, MISSION, 0, crc,
        "START sent while LOADED (not ARMED). The sequence is still consumed.")
    ack("26_nack_arm_bad_session", 3, T.ARM, R.REJECTED, D.BAD_SESSION, MISSION, 0, crc,
        "Request used a wrong session; header shows the board's real session. Sequence not consumed.")
    ack("27_nack_arm_stale_seq", 2, T.ARM, R.REJECTED, D.STALE_SEQ, MISSION, 0, crc,
        "Request sequence lower than the last accepted one.")
    ack("28_nack_arm_seq_conflict", 3, T.ARM, R.REJECTED, D.SEQ_CONFLICT, MISSION, 0, crc,
        "Same sequence as the last command but different bytes.")
    ack("29_nack_commit_bad_plan_crc", 2, T.COMMIT_PLAN, R.REJECTED, D.BAD_PLAN_CRC, MISSION, 0, crc,
        "COMMIT carried a plan_crc16 that does not match the staged plan.")
    ack("30_nack_load_bad_plan", 1, T.LOAD_PLAN, R.REJECTED, D.BAD_PLAN, MISSION, 0, 0,
        "Plan broke a plan rule (e.g. arrival_tick <= departure_tick). Nothing staged.")

    # Frames the receiver must discard and count, with no reply.
    def invalid(name, data, error, note):
        blobs[name] = data
        entries.append({"name": name, "valid": False, "expected_error": error, "note": note,
                        "hex": data.hex(" ").upper()})

    good = blobs["13_start"]
    invalid("40_invalid_bad_crc", good[:-1] + bytes([good[-1] ^ 0xFF]), "BAD_CRC",
            "START with the last CRC byte inverted.")
    body = bytes([2]) + good[3:-2]
    invalid("41_invalid_bad_version", p.MAGIC + body + p.crc16_ccitt_false(body).to_bytes(2, "little"),
            "BAD_VERSION", "Version byte 2 with a correct CRC.")
    invalid("42_invalid_oversize_length", p.MAGIC + bytes([1, 0x10, 1, 0]) + p.pack_u32(SESSION) + bytes([129, 0]),
            "OVERSIZE", "Header claims a 129-byte payload. Reject from the header alone; do not wait for the body.")
    invalid("43_invalid_wrong_length_for_type", p.encode_frame(T.ARM, 3, SESSION, b""), "BAD_SHAPE",
            "ARM with an empty payload and a correct CRC. Integrity passes; exact-length check must discard it.")
    invalid("44_invalid_unknown_type", p.encode_frame(0x7E, 0, SESSION, b""), "BAD_SHAPE",
            "Unknown message type 0x7E with a correct CRC. Discard and count.")

    def stream(name, data, expected, note):
        blobs[name] = data
        entries.append({"name": name, "valid": None, "stream": True, "expected_frames": expected,
                        "note": note, "hex": data.hex(" ").upper()})

    stream("50_stream_garbage_then_valid",
           bytes([0x00, 0xFF, 0x13]) + p.MAGIC + bytes([0x07, 0x99]) + bytes([0xA5]) + blobs["05_get_status"],
           ["05_get_status"], "Noise, a false magic with a bad version, a stray A5, then one good frame.")
    stream("51_stream_two_frames", blobs["11_arm"] + blobs["13_start"], ["11_arm", "13_start"],
           "Two frames back to back in one read.")
    stream("52_stream_bad_crc_then_valid", blobs["40_invalid_bad_crc"] + blobs["05_get_status"],
           ["05_get_status"], "A corrupt frame must not block the next good one.")
    stream("53_stream_truncated_then_valid", blobs["11_arm"][:9] + blobs["05_get_status"],
           ["05_get_status"], "A frame cut off after 9 bytes, then a good frame.")
    return entries, blobs


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    plan = build_plan()
    w, t = plan["wire"], plan["ticks"]
    wire_plan = p.Plan(MISSION, t["departure_tick"], t["arrival_tick"], t["end_tick"],
                       w["initial_fuel_g"], w["departure_fuel_g"], w["capture_fuel_g"])
    assert wire_plan.problem() is None

    docs = {}
    docs.update(build_snapshots(plan, wire_plan))
    docs.update(build_planet_info(plan))
    docs.update(build_input_fixtures())
    del plan["_helpers"]
    docs["mission_plan_earth_mars"] = plan
    for name, obj in docs.items():
        write_json(FIXTURES / f"{name}.json", obj)

    entries, blobs = build_frames(wire_plan)
    for old in list(FRAMES.glob("*.bin")) + list(FRAMES.glob("*.hex")):
        old.unlink()
    for name, data in blobs.items():
        (FRAMES / f"{name}.bin").write_bytes(data)
        (FRAMES / f"{name}.hex").write_text(data.hex(" ").upper() + "\n", encoding="ascii", newline="\n")
    write_json(FRAMES / "manifest.json", {
        "protocol_version": 1,
        "note": "Golden frames generated by app/contracts/tools/generate.py. .bin = raw bytes; "
                ".hex = the same bytes as space-separated hex (usable with Verilog $readmemh).",
        "session_id": SESSION, "mission_id": MISSION, "plan_crc16": wire_plan.crc16(),
        "crc_check": {"ascii": "123456789", "value": p.crc16_ccitt_false(b"123456789")},
        "frames": entries})
    print(f"wrote {len(docs)} JSON fixtures and {len(blobs)} frame fixtures")


if __name__ == "__main__":
    main()
