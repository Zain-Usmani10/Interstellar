# Contracts changelog

Breaking change = version bump here + `@all` post on the board with the commit.

## 1.4.0 (2026-11-15): additive

- `GET /api/v1/planets/track?start_jd_tdb=&end_jd_tdb=&step_days=`: all eight planets over a date range in one call (`epochs_jd_tdb` plus, per planet, one `r_km` per epoch; at most 2000 samples). For the free-running calendar of plan section 19.3.
- Flight length for catalogue plans changes to 30 s (ticks 500 / 3500 / 3800) when the plans are regenerated; no field changes.

## 1.3.1 (2026-11-15): behaviour only, no shape change

- Automatic blackout: with `AUTO_BLACKOUT=true` (default from the environment) each flight enters a blackout once, when confirmed telemetry is 25 % into the flight. Any blackout now ends by itself when the estimate reaches 85 % of the flight (was: the arrival tick). `blackout_start` is refused after 85 %. Fields and commands are unchanged.

## 1.3.0 (2026-11-15): fleet and planet positions (plan sections 19 and 20)

- `GET /api/v1/fleet`: every shuttle with `id`, `name`, `class` (`standard` / `long_range`), `label` and `location` (`docked` at a `body_id`, `in_flight` or `lost` with a `mission_id`). `POST /api/v1/fleet/reset` (operator) restores the starting fleet; 409 while the controller holds a mission.
- `POST /api/v1/missions` accepts optional `shuttle_id`. **Behaviour change:** a mission now needs a docked shuttle of the plan's class at the plan's origin; otherwise HTTP 409 with detail `NO_SHUTTLE_DOCKED`. Without `shuttle_id` the backend picks one. MissionSnapshot gains `shuttle_id`.
- Shuttles move only on confirmed controller telemetry: departure burn -> `in_flight`; COMPLETE with capture -> `docked` at the destination; SAFE or ABORTED after departure -> `lost`; abort or clear before departure -> still docked. Nothing moves during a blackout.
- WebSocket event `fleet` carries the same body as `GET /api/v1/fleet` whenever it changes.
- `GET /api/v1/planets/positions?jd_tdb=` or `?date_utc=`: all eight planets (`body_id`, `r_km`) at one date from the checked-in NASA track, with the track's date range. 404 `DATE_OUTSIDE_TRACK` outside it.

## 1.2.0 (2026-11-15): additive, nothing breaks (plan section 18, Shuttle and CCS)

- Wire: new mutation `SET_TRIP_DAYS` (`0x16`, payload `mission_id:u32, trip_days:u32`, allowed in LOADED or ARMED, display only). Golden frames `31_set_trip_days`, `32_ack_set_trip_days`, `33_nack_set_trip_days_bad_value`. Every earlier frame is unchanged. `protocol_v1.py` adds `pack_trip_days`, `trip_days_from_tof` and the shared `days_to_arrival` formula.
- Backend behaviour: `upload` = LOAD_PLAN + COMMIT_PLAN + SET_TRIP_DAYS. The upload still counts as applied if only SET_TRIP_DAYS is refused; `trip.trip_days` is then null. A `GET_STATUS` keep-alive is sent every 0.5 s except during a blackout.
- Mission commands: `blackout_start` (only while RUNNING) and `blackout_end`. During a blackout nothing is sent, received frames are discarded, other commands answer HTTP 409, and contact returns by itself when the estimate reaches the arrival tick.
- MissionSnapshot gains `link.blackout`, `date_utc`, `trip`, `estimate`, `reconciliation`. During a blackout the old top-level fields keep the last received values.
- Not in this version yet: the fleet endpoints of plan section 20.

## 1.1.0 (2026-11-15): additive, nothing breaks

- `body_id` now allows all eight planets (199, 299, 399, 499, 599, 699, 799, 899), so a MissionPlan may connect any two planets. The wire protocol is unchanged: the board only receives ticks and fuel.
- `GET /api/v1/plans` summaries also carry `origin_body_id` and `destination_body_id`.
- Planet selection targets and information cards are still Earth and Mars only.

## 1.0.1 (2026-11-14): additive, nothing breaks

- `api_v1.md`: added `POST /sim/faults`, `GET /session`, heartbeat rules per source, and the adapter imports the backend looks for.

## 1.0.0 (2026-11-14): first freeze

- Wire protocol v1: `protocol_v1.json` and reference code `protocol_v1.py`.
- Golden frames: `fixtures/frames/` (30 valid, 5 that must be discarded, 4 byte streams) with `manifest.json`.
- Schemas v1: MissionPlan, MissionSnapshot, PlanetInfo, InputContext, SelectionIntent, IntentResult, InputHeartbeat.
- One valid fixture per schema in `fixtures/`. The MissionPlan fixture is **synthetic**, not NASA data.
- Transport interface: `transport.py`.
- HTTP/WebSocket surface: `api_v1.md`.

Decisions made here that the plan left open:

- OPEN_SESSION and read-only requests (DISCOVER, GET_STATUS) carry sequence 0. Mutations start at sequence 1.
- ACK `mission_id` echoes the request's mission id (0 for OPEN_SESSION). ACK `plan_crc16` is the board's staged plan CRC after LOAD, otherwise the active plan CRC, 0 if none.
- A CRC-valid frame with an unknown type or the wrong payload length is discarded and counted, with no reply.
- Planet targets are `planet.399` and `planet.499`. The only input capability is `planet_explore`; no input session can upload, arm or start a mission.
