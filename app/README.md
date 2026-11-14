# app/: all Interstellar project code

Every part of the system lives under this folder and comes together here. Owners create their own subfolders; see `AGENTS.md` section 4 for who owns what. The specs are in `docs/plan/`.

```text
app/
├── contracts/        shared JSON schemas, protocol v1, golden frames, mock fixtures   @ANaceri26/claude (leader)
├── backend/
│   ├── api/          FastAPI routes + WebSocket                                       @ANaceri26/claude
│   ├── runtime/      mission state, single serial owner, input validation             @ANaceri26/claude
│   ├── transport/    serial framing/CRC, DelayTransport, simulator transport          @ANaceri26/codex
│   ├── ephemeris/    NASA/JPL Horizons fetch + cache                                  @sadattanzim01/claude
│   ├── planner/      Lambert grid search, least-fuel / earliest-arrival              @sadattanzim01/claude
│   ├── physics/      propagation, fuel, residual checks                               @sadattanzim01/claude
│   └── planet_data/  PlanetInfo (facts, orbital state, EONET Earth events)            @sadattanzim01/claude
├── frontend/         TypeScript + React + Three.js UI                                 @sadattanzim01/cursor
│   └── src/bci/      optional EEG selection widget                                    @AffanSyed07/codex
├── hardware/
│   ├── fpga/         DE10-Lite RTL, .qpf/.qsf/.sdc, testbenches                       @Zain-Usmani10 (human)
│   └── xiao/         XIAO ESP32S3 USB<->UART bridge firmware                          @ANaceri26/codex
├── brain/            EEG acquisition + decoder (separate Python env)                  @AffanSyed07/codex
├── data/ephemeris/   verified NASA cache + provenance                                 @sadattanzim01/claude
├── tests/<area>/     tests owned by the matching area owner (tests/integration: leader)
├── scripts/          bootstrap / start-demo / smoke-test                              @ANaceri26/claude
└── artifacts/        .sof, firmware builds, acceptance.md                             @ANaceri26/claude
```

How the parts connect (from `docs/plan/MAIN_BACKEND_FPGA_TASKS.md` section 2):

```text
NASA Horizons -> ephemeris cache -> planner (Lambert) -> MissionPlan -> browser preview
mouse/keyboard + optional EEG -> runtime input validation -> transport (+ delay) -> USB serial
  -> XIAO bridge -> 3.3 V UART -> DE10-Lite sequencer -> STATUS -> runtime -> browser
```
