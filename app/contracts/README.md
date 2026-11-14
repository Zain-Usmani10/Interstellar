# app/contracts/: the shared interfaces (leader-owned)

Owner: `@ANaceri26/claude`. Everyone else reads these and builds against them; **no one else edits this folder**. Request changes on the board.

These files are the single source of truth wherever two areas meet. With them, every owner can build in parallel against fake data and the parts still fit when integrated.

## To be delivered first (spec: `docs/plan/MAIN_BACKEND_FPGA_TASKS.md` sections 5, 8, 11)

| File | Contents | Used by |
|---|---|---|
| `protocol_v1.json` | Serial frame layout, message types, payload layouts, ACK detail codes, state IDs, CRC-16/CCITT-FALSE | FPGA (Zain), transport (ANaceri26/codex), runtime |
| `fixtures/frames/*.bin` + `.hex` | Golden frames byte-for-byte (DISCOVER, LOAD_PLAN, COMMIT, ARM, START, ACK, STATUS, bad CRC) | FPGA testbenches, transport tests |
| `schemas/mission_plan.schema.json` | `MissionPlan` | planner, runtime, frontend |
| `schemas/mission_snapshot.schema.json` | `MissionSnapshot` | runtime, frontend |
| `schemas/planet_info.schema.json` | `PlanetInfo` | planet_data, frontend |
| `schemas/input_context.schema.json`, `selection_intent.schema.json` | EEG/mouse input contract; targets `planet.399`, `planet.499` | runtime, frontend, brain |
| `fixtures/*.json` | One valid example per schema (Earth->Mars plan, snapshots, Earth/Mars PlanetInfo) | everyone's mocks |
| `CHANGELOG.md` | Version + date + what changed | everyone |

## Rules
- Every file carries a `schema_version` / protocol version. Breaking change = version bump + `@all` board post with the commit.
- Brain-local stimulus contract lives in `app/brain/contracts/` (Affan), not here.
