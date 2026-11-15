# Contracts changelog

Breaking change = version bump here + `@all` post on the board with the commit.

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
