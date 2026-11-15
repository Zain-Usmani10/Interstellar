# app/contracts/: the shared interfaces (leader-owned)

Owner: `@ANaceri26/claude`. Everyone else reads these and builds against them; **no one else edits this folder**. Request changes on the board.

Current version: **1.0.0** (see `CHANGELOG.md`). Wire protocol version 1, schema version 1.

## What is here

| File | Contents | Used by |
|---|---|---|
| `protocol_v1.json` | Frame layout, message types, payload layouts, enums, CRC, sequencing rules | FPGA, transport, runtime |
| `protocol_v1.py` | The same protocol as runnable Python (standard library only): CRC, encode/decode, payload pack/unpack, a reference stream parser | generator, simulator, tests |
| `fixtures/frames/*.bin`, `*.hex`, `manifest.json` | Golden frames, byte for byte. `01`–`30` valid, `40`–`44` must be discarded, `50`–`53` byte streams with the frames a parser must recover | FPGA testbenches, transport tests |
| `schemas/*.schema.json` | MissionPlan, MissionSnapshot, PlanetInfo, InputContext, SelectionIntent, IntentResult, InputHeartbeat (JSON Schema 2020-12) | planner, runtime, frontend, brain |
| `fixtures/*.json` | One valid example per schema | everyone's mocks |
| `transport.py` | The `Transport` interface between runtime and serial / delay / simulator | transport, runtime |
| `api_v1.md` | HTTP routes and WebSocket events | frontend, brain |
| `tools/generate.py` | Regenerates every fixture deterministically | leader |

## Using the golden frames

- `.bin` is the raw frame. `.hex` is the same bytes as space-separated hex, one frame per file (works with Verilog `$readmemh`).
- `manifest.json` lists every frame with its decoded fields, so you can check each field and not just the bytes.
- Golden values: session `0x1A2B3C4D`, mission `0x00C0FFEE`, CRC check `"123456789"` -> `0x29B1` (wire bytes `B1 29`).
- Your encoder must produce the valid frames exactly. Your decoder must accept them, discard `40`–`44`, and recover the expected frames from `50`–`53` for any chunking of the input.

## Honest labels

`fixtures/mission_plan_earth_mars.json` is **synthetic** (`data_mode: "synthetic"`): circular coplanar planets and a Hohmann-type ellipse, made so the shapes, units and arithmetic are consistent. It is not NASA data and not a validated route. The EONET items in `planet_info_399.json` are mock entries. The NASA owner supplies the real cached plan and facts.

## Commands (from the repo root)

```
python -m app.contracts.tools.generate      # rewrite fixtures
python -m pytest app/tests/contracts        # check frames, schemas and fixtures
```

## Rules

- Breaking change = version bump in `CHANGELOG.md` + `@all` board post with the commit.
- Schemas for output objects allow extra fields; input objects (`SelectionIntent`, `InputHeartbeat`, `InputContext`) do not.
- Brain-local stimulus contract lives in `app/brain/contracts/` (Affan), not here.
