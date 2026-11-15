# INTERSTELLAR — core implementation contract and task plan

> **Repo note (added at setup, 2026-11-14):** `AGENTS.md` is authoritative for roles, ownership and git policy; it overrides this file where they differ. All code paths in this file live under `app/` (e.g. `backend/api/` means `app/backend/api/`, `contracts/` means `app/contracts/`). Plan files are in `docs/plan/`. Agents: `@ANaceri26/claude` (leader/integrator), `@ANaceri26/codex` (XIAO/transport), `@sadattanzim01/claude` (NASA/physics), `@sadattanzim01/cursor` (frontend), `@AffanSyed07/codex` (brain). **The FPGA is owned by Zain (`@Zain-Usmani10`) and his agent `@Zain-Usmani10/claude`.** The board bugs in TEAM_AGENT_PROMPTS.md section 3 are fixed in `tools/board`.

Version: 1.4, 2026-11-15 (adds section 18, Shuttle and CCS; section 19, time scaling; section 20, fleet; routes between a validated set of planet pairs; VGA cockpit allowed). Wire protocol remains v1 with one additive message (`0x16`, section 18.3).

> **Changes since 1.2 (2026-11-15):** Zain has a Claude agent (`@Zain-Usmani10/claude`) for the FPGA. The NASA/physics folders moved from Sadat's Claude to `@AffanSyed07/codex`. `@sadattanzim01/cursor` owns the whole GUI including the 3D scene. Where a section below still says "Sadat's Claude" for NASA/physics, read "Affan's Codex". `AGENTS.md` remains authoritative for ownership. Owner: core integration lead.

Final role assignment: your Claude owns integration/backend, Zain's Claude owns FPGA, your Codex owns XIAO/transport. Preserve existing branches/work during handoff.

Latest scope: `TEAM_AGENT_PROMPTS.md` maps the actual six agents (five core now, Affan on brain when available). The brain milestone is read-only planet selection/information in the same 3D app. No game features; EEG route orders/upload/start are deferred. Sections describing future EEG mission confirmation are design context, not authorization to build that later phase now.

## 1. Read this first

Build a **NASA-data-based mission simulator controlled by a real FPGA mission sequencer**. The laptop calculates trajectories and simulates physics. The DE10-Lite decides when the simulated departure/capture events happen and supplies authoritative execution time/status. There are no motors, actual spacecraft, or physical propulsion.

This file is the authoritative core specification. `BRAIN_CONTROL_TASKS.md` extends its input interface; brain control must not change the physics, serial protocol, or FPGA design. These are implementation requirements and proposed acceptance gates, **not a claim that the hardware or software has already passed them**.

User-confirmed resources: two DE10-Lite boards, two Seeed XIAO ESP32S3 boards, Raspberry Pi 5 (8 GB), Pi 3 (1 GB), monitor, breadboard/wires, Quartus available, approximately 15 hours remaining when planning began. Use one FPGA, one XIAO, and one laptop. Keep duplicates as spares. The borrowed EEG model is not yet confirmed.

The supplied `CONTEXT.md` is a vision draft. This document deliberately reduces its scope. The local event hacker packet and Mind and Machine guide were also read: the packet requires project code to be written during the event, and the brain guide explicitly permits recorded datasets and synthetic streams without a headset. The existing Intersteller-Highway-V2 repo is inspiration/reference, not project code to copy. Use documented dependencies and sponsor starter resources under their terms; clarify any ambiguous reuse with organizers. Latest organizer updates override printed schedule details. [S16, S17]

### What ships

1. Route search between planets using NASA/JPL Horizons planetary state vectors. Earth → Mars is the reference route; other pairs ship only when they have stored, validated plans in the route catalogue (`data/search/planet_pairs.json`). Pairs without one are shown as not available, never animated.
2. Two clearly defined recommendations: least required propellant and earliest feasible arrival **within the searched grid**.
3. Browser orbit/transfer view, route comparison, plan upload, start, status, faults, and source/model details.
4. Actual FPGA execution of a small uploaded schedule, with USB/UART communication through XIAO.
5. One-register-lane fault masking, a specifically defined unrecoverable divergence demonstration, and autonomous execution during loss of ground communication.
6. Cached NASA-backed offline demo, labelled simulated-controller fallback, reproducible startup, meaningful test results, and a recorded hardware demo.
7. Ordinary-input Earth/Mars information panels with a stable optional EEG selection interface; dated Earth hazard information is an independent enrichment, not a prerequisite for orbital execution.
8. The Shuttle and CCS storyline of section 18: blackout after launch, labelled estimate on the CCS, days-to-arrival countdown on both sides, sync at arrival.

### Explicit exclusions

No quantum, Gemini, ElevenLabs, MongoDB, authentication service, MQTT, Raspberry Pi deployment, accelerometer control, joystick, SDRAM controller, soft CPU, asteroid routing, refueling, gravity assists, continuous thrust, automatic recovery replanning, or routes that are not in the validated catalogue. Add none until the core acceptance gates pass. An FPGA VGA cockpit is allowed as a display-only addition (section 18.6).

NASA data is essential; optional sponsor integrations are not. Main track target: Beyond the Horizon. Mind and Machine is conditional on the extension and confirmed event rules. [S1]

## 2. Architecture and authority

```text
NASA/JPL Horizons → backend cache → Lambert search → validated immutable MissionPlan
                                              ↘ browser route preview

mouse/keyboard ─┐
optional EEG ──┴→ core input/action validation → command dispatcher + delay emulator
                                                     ↓ USB serial
                                                XIAO bridge
                                                     ↓ 3.3 V UART
                                            DE10-Lite mission sequencer
                                                     ↓ status / executed burns
                  browser ← physics/state reconstruction ← delayed telemetry
```

| Component | Owns | Must not own |
|---|---|---|
| NASA adapter | Planet vectors, metadata, verified cache | Mission optimization or spacecraft physics |
| Planner | Transfer solution, masses, immutable plan | Runtime mission clock |
| FPGA | Mission ticks, executed-event mask, fuel ledger, controller state, fault outcomes | NASA requests, floating-point orbital integration |
| XIAO | Transparent bounded byte forwarding | Fake telemetry, duplicate timing/delay simulation |
| Backend runtime | Command validation, orbital reconstruction from board evidence, source labels | Silently inventing hardware execution |
| Browser | Display and input | Advancing a mission independently of telemetry |
| EEG extension | Selection proposals | Serial access, direct mission commands, physics changes |

**Core truth:** changing the FPGA's executed events must change the simulated mission result. A prerecorded route animation that reaches Mars regardless of the FPGA is a failed implementation.

## 3. Software choices and environment gate

Target one Windows x64 laptop for the actual demo. Use a separate Python virtual environment for EEG so device dependencies cannot break the core.

| Area | Choice | Compatibility requirement |
|---|---|---|
| Backend | Python 3.11 x64, FastAPI, Uvicorn, Pydantic | Existing local Python was 3.10.11; install/select 3.11 explicitly or validate a complete 3.10 lock before changing the baseline |
| Numerics | NumPy, SciPy, Astropy, `lamberthub==1.0.0` | Resolve and lock compatible NumPy/SciPy/Numba versions on the demo machine; no moving Git branches |
| NASA HTTP | HTTPX or requests, one application-wide request queue | A single outbound NASA request at a time |
| Serial | pyserial | Exactly one backend process opens the XIAO port |
| Persistence | Python SQLite + local JSON/binary artifacts | No cloud dependency |
| Browser | TypeScript, React, Three.js, Vite | Node 22 LTS >=22.12 or another supported even-numbered LTS; lock npm dependencies |
| FPGA | Existing working Quartus Lite + MAX 10 support | Device `10M50DAF484C7G`; preserve working setup |
| Bridge | Arduino-ESP32, XIAO ESP32S3 board definition | Native USB CDC enabled, explicit UART pins |

Vite documents Node minimums; avoid updating the existing FPGA toolchain under deadline. Quartus Lite 25.1 with matching MAX 10 support is a documented fallback, not a requirement to upgrade. [S6, S7, S15]

`lamberthub` release 1.0.0's actual LICENSE is GPL-3.0, despite contradictory package metadata. Treat it as GPL-3.0, retain notices, and choose compatible project distribution terms before publishing. Do not describe it as Apache/permissive. Current repository main has different Python requirements; pin the release. [S5]

First 30-minute gate: import all numeric libraries; run one Lambert calculation; launch API/UI; compile/program FPGA heartbeat; identify the XIAO COM port. Produce `requirements-core.lock.txt`, `package-lock.json`, bridge tool versions, and Quartus version records after this succeeds. Do not invent a dependency lock from untested version guesses.

Core startup must not import BrainFlow, pylsl, vendor EEG packages, or require an EEG device. Do not use Uvicorn reload/multiple workers with an active serial owner.

## 4. Hardware compatibility, wiring and FPGA build

### Board resources

DE10-Lite: MAX 10 `10M50DAF484C7G`, approximately 50K logic elements and 1,638 Kbit internal M9K memory. The proposed controller needs a tiny plan buffer and three small register banks, not a complete triplication of the application. Capacity is plausible; only compilation proves fit and timing. Use internal registers/M9K, not external SDRAM. USB-Blaster is a **JTAG programmer**, not a normal application UART port. [S6]

### Wiring — verify physical orientation before connecting

| Signal | XIAO ESP32S3 | DE10-Lite JP1 | FPGA assignment |
|---|---|---|---|
| Host to FPGA | D6 / GPIO43 / TX | Physical pin 1, GPIO0 | RX input `PIN_V10` |
| FPGA to host | D7 / GPIO44 / RX | Physical pin 2, GPIO1 | TX output `PIN_W10` |
| Ground | GND | Physical pin 12 or 30, GND | Common reference |
| FPGA clock | Not connected to XIAO | Onboard 50 MHz oscillator | `MAX10_CLK1_50`, `PIN_P11` |

These assignments are from the Terasic manual and Seeed pin map. Cross-check the board revision, header drawing and pin-1 mark before wiring. TX connects to RX. Use 3.3-V LVTTL FPGA I/O. Power each board by its own USB connection; connect only the signal wires and common ground between boards. Do not join 5 V/3.3 V power rails. Turn power off before changing wiring. No 5 V UART. [S6, S8]

XIAO firmware explicitly initializes `Serial1.begin(115200, SERIAL_8N1, 44, 43)`. `Serial` is native USB CDC; `Serial1` is the physical FPGA UART. Enable USB CDC on boot. Never wait forever for a USB terminal, and never print debug text into the binary data stream. Use a separate debug channel or counters. Firmware upload may change COM enumeration; reconnect through a configured port and protocol handshake. [S9]

### FPGA requirements

- Commit RTL, `.qpf`, `.qsf`, `.sdc`, testbenches and a build command. Ignore generated databases/output except intentionally packaged release artifacts.
- One 50 MHz clock with a 20 ns timing constraint. Generate clock-enable pulses, not additional fabric clocks.
- Mission clock enable: exactly 100 Hz, one pulse per 500,000 input clocks.
- UART: 115200, 8 data bits, no parity, one stop bit. Integer divisor 434 gives approximately 115207 baud. Synchronize RX, sample near bit centers, reject invalid stop bits.
- Two-flop synchronize switches/buttons; debounce and edge-detect. Verify asynchronous reset assertion and synchronous release.
- Explicit pin locations/directions. Unused pins input/high impedance. UART must idle high.
- Use onboard LEDs for READY/RUNNING/SAFE and a latched fault indicator. Seven-segment cockpit and link-lost indication as in section 18.6.
- `.sof` programming is volatile. Reprogram/re-upload after power loss. Persistent flash configuration is not a core requirement.

## 5. NASA data contract

NASA supplies **planet positions and velocities**, not the custom trajectory or a certification that it is flyable.

Use the backend-only Horizons endpoint `https://ssd.jpl.nasa.gov/api/horizons.api`. No NASA API key is needed for this endpoint. For each body request use:

```text
format=json
COMMAND='399'                  # Earth; Mars='499'; optional Venus='299'
OBJ_DATA='YES'
MAKE_EPHEM='YES'
EPHEM_TYPE='VECTORS'
CENTER='500@10'                 # Sun center
REF_SYSTEM='ICRF'
REF_PLANE='ECLIPTIC'
OUT_UNITS='KM-S'
TIME_TYPE='TDB'
VEC_CORR='NONE'
VEC_TABLE='2'
CSV_FORMAT='YES'
TLIST_TYPE='JD'
TLIST='<explicit requested Julian dates>'
```

Use an HTTP parameter encoder, not manually concatenated shell/URL text. Parse the returned text table between `$$SOE` and `$$EOE`; JSON `result` is not already a structured vector array. Validate target, Sun center, frame, units, timescale, row count, requested epochs, finite numbers and increasing unique timestamps. Reject error payloads even when HTTP status is 200. Record/check signature version; unexpected formats fail closed. [S2]

Internal numerical time is Julian date TDB. Convert UTC date input using `astropy.time.Time`; do not relabel UTC numbers as TDB. Display dates in UTC and label them. Every vector carries frame, center, units and epoch metadata. [S3]

Fetch unique departure epochs for Earth and unique arrival epochs for Mars **before** the grid solve. Batch bounded lists (initially 32 epochs per GET) and reuse cached rows. For large lists use the documented file POST API instead of excessive URL lengths. No per-cell network calls. [S2, S4]

SSD fair use requires one request at a time, caching and backoff. Use an application User-Agent identifying version/contact, a 30-second request timeout, at most three attempts, exponential backoff, and honor Retry-After. Do not parallelize NASA calls across workers or agents. These APIs are not meant to be directly embedded in browser requests. [S4]

### Offline behavior

Store raw response, normalized rows, full canonical request, retrieval UTC, API signature, source URL and SHA-256 in `data/ephemeris/`. Cache keys include body, center, frame, units, time type and epochs. A stale cache is not automatically wrong for a fixed historical/future epoch, but its provenance must remain visible.

An offline demo may use the same previously fetched NASA rows, labelled `NASA/JPL cached`, with its supported date bounds locked in the UI. If the requested epochs are absent, return `EPHEMERIS_UNAVAILABLE`; never silently substitute circular orbits. Synthetic test fixtures require a distinct `synthetic` mode and persistent banner.

Before a selected plan becomes mission-ready, enrich its cache with **both Earth and destination vectors over the complete run interval `epoch(0)` through `epoch(end_tick)`**, including exact departure/arrival epochs. Initial approach: daily TDB nodes with position/velocity cubic Hermite interpolation. Validate intermediate positions against held-out Horizons epochs (proposed <10 km error), refine spacing if necessary, and prohibit extrapolation. This supports moving planets, predeparture display, Earth distance during cruise and the postarrival uncaptured coast. Grid boundary vectors alone are insufficient. Fetch enrichment through the same serialized NASA queue and save it with the plan.

### Planet explorer: read-only data surface for the EEG milestone

The track's resource list is a menu of sources, not a requirement to use all of them or two named APIs. Begin with Earth (`399`) and Mars (`499`): select a planet by ordinary input, highlight it in 3D, open a card, then connect the optional EEG intent to that same action. Affan's decoder never fetches NASA data directly.

Use existing Horizons states for orbital information at the labelled scene epoch, and a small checked-in facts dataset with NASA/JPL source links for radius, atmosphere and other stable facts. Mean temperature/climate facts are not current weather readings. Expose their individual units and provenance.

Second live-data source: NASA EONET v3 for **Earth** storm/wildfire event metadata. Start with a bounded backend request such as `https://eonet.gsfc.nasa.gov/api/v3/events?category=severeStorms,wildfires&status=open&days=30&limit=20`. Preserve event IDs, dates, locations and source links; cache responses for 15 minutes with a bounded timeout/retry policy. Do not make data refresh part of the signal-processing loop. [S18]

Label the panel “Earth natural hazard events.” An empty result is not an all-clear, and an API error is not zero hazards. EONET is not a local weather forecast, a complete event census or a generic planetary-health score. It does not provide Mars weather. Show unsupported current Mars weather as unavailable; InSight ended in 2022 and its old measurements cannot be labelled live. [S19]

Event observation time is distinct from the selected/future mission epoch. Present recent observations in a separate card section; never imply they describe the future simulated launch date. Do not use these Earth events to fabricate Mars risk, FPGA radiation errors or transfer Δv. Later DONKI integration would concern space-weather events, not surface weather on arbitrary planets; it is not required now.

PlanetInfo fields: `schema_version`, `body_id`, `name`, `scene_epoch_jd_tdb`, `facts[]` with value/unit/source, `orbital_state` with frame/units/epoch/provenance, and `conditions` with `scope`, `kind`, `availability` (`available|empty|unavailable|error`), `delivery` (`live_fetch|cached`), observed/retrieved timestamps and `items[]`. Null/unavailable is valid. Retain per-section provenance so cached facts cannot be mislabelled as live measurements. Data failures must not block selecting/highlighting a planet or operating the mission core.

## 6. Orbital model and solver

### Scope and units

- Sun-centered, two-body interplanetary coast; zero-revolution, prograde Lambert solution.
- Impulsive departure/capture estimates from declared circular parking orbits with 12-hour periods.
- No atmosphere, ascent, staging, plane matching, finite burn duration, third-body perturbations, detailed sphere-of-influence transitions, or operational navigation accuracy.
- Orbital units: km, s, km/s, km³/s². Mass: kg. Specific impulse `Isp`: seconds.
- Obtain gravitational parameters directly from JPL/Horizons, store their provenance; do not derive them from rounded masses and G. Distinguish body GM from a planet-system GM. Constants `c=299792.458 km/s`, `1 au=149597870.7 km`.

For a candidate `(departure_jd_tdb, arrival_jd_tdb)`:

```python
tof_s = (arrival_jd_tdb - departure_jd_tdb) * 86400
v1, v2 = izzo2015(
    mu_sun, r_earth_depart, r_mars_arrive, tof_s,
    M=0, prograde=True, low_path=True,
    maxiter=35, atol=1e-5, rtol=1e-7,
)
```

The pinned function has no `full_output` parameter. Low/high-path does not create two meaningful solutions for this zero-revolution core. Distinct recommendations come from different date/duration grid candidates. [S5]

```text
v_inf_depart = norm(v1 - v_earth_depart)
v_inf_arrive = norm(v2 - v_mars_arrive)
r_park = (mu_planet * (43200 / (2*pi))^2)^(1/3)
dv_depart = sqrt(v_inf_depart^2 + 2*mu_earth/r_park_earth)
            - sqrt(mu_earth/r_park_earth)
dv_capture = sqrt(v_inf_arrive^2 + 2*mu_mars/r_park_mars)
             - sqrt(mu_mars/r_park_mars)
dv_total = dv_depart + dv_capture
```

Validate parking radius above each body's surface. These are idealized energy-based parking-orbit burn estimates, not complete launch guidance. **Do not add `dv_depart` as a scalar to the heliocentric velocity.** The coast starts with the Lambert velocity `v1`; the parking-orbit formula is used for propellant/capability estimates. [S10]

Vehicle default for initial validation: dry mass 1,000 kg, payload 100 kg, Isp 450 s, propellant capacity 10,000 kg. Label this a hypothetical chemical vehicle, not a NASA spacecraft. UI changes must preserve finite positive physical inputs.

```text
m_final = dry_mass + payload_mass
m_prop_required = m_final * expm1(dv_total_km_s*1000 / (Isp_s*9.80665))
feasible = required_propellant <= capacity
m_after_burn = m_before_burn * exp(-dv_burn_km_s*1000 / (Isp_s*9.80665))
```

The model loads just the required propellant, with no reserve. Calculate departure and capture consumptions sequentially from that loaded mass. Coast consumes no propellant. Convert each positive consumption to integer grams by rounding upward for the FPGA ledger; initial loaded grams equal the sum of the two rounded costs. Recheck capacity after rounding. Preserve high-precision values and rounded ledger values separately. [S11]

### Search definition

Initial upper bound: 25 departure dates × 25 durations = 625 cells. Start with a smaller grid for the first integration. Suggested initial search bounds: departure 2026-11-15 through 2027-02-15 UTC, flight duration 120–360 days. These are proposed search bounds, **not a verified winning route**; acceptance requires at least one independently validated feasible candidate.

- Least fuel: minimum required propellant over feasible grid cells.
- Earliest arrival: minimum arrival epoch over feasible cells; tie-break by required propellant.
- Shortest flight duration is not the same objective; do not label it earliest arrival.
- Same candidate may win both objectives. Show that honestly.
- Reject negative/zero flight time, nonfinite or degenerate geometry, solver failure, infeasible fuel and solar-intersecting arcs. A failed solve is an invalid cell, never a zero-cost cell.
- The UI must say “best within this grid” and expose its bounds/resolution.

For each selected candidate, independently integrate the heliocentric initial state using SciPy DOP853; use 512 timestamped samples/dense output for the displayed nominal arc. Also integrate the unburned coast through `epoch(end_tick)` for SAFE/ABORTED cases; never extrapolate dense output or the preview polyline beyond its computed interval. Normal endpoint validation still uses the exact arrival epoch. Start with `rtol=1e-10`, position absolute tolerance `1e-3 km`, velocity absolute tolerance `1e-9 km/s`, and verify convergence. Check heliocentric minimum radius across the actual arc, including an interior extremum when present; reject intersection with the adopted solar radius. [S12]

Only publish a mission-ready route after endpoint position residual <10 km and velocity residual <1e-5 km/s against its Lambert target. These are numerical consistency targets for the simplified model, not real-world accuracy claims. Test an independent published Lambert case and conserved coast energy/angular momentum. Warm the JIT solver before measuring UI performance.

## 7. Execution and physical simulation contract

### Two event schedule, no variable mission language

The core uploads exactly two events: departure and capture. Use integer 100 Hz board ticks; the board does not need dates, floating-point seconds or vectors.

```text
departure_tick = 10
arrival_tick   = 12010                  # approximately two minutes; catalogue plans use 500 / 6500 / 6800 (section 19.1)
end_tick       = 12610                  # six extra real seconds for a missed-capture coast
seconds_per_tick = tof_s / (arrival_tick - departure_tick)
epoch_jd_tdb(tick) = departure_jd_tdb
                  + (tick - departure_tick)*seconds_per_tick/86400
```

Use a signed subtraction on the laptop for the predeparture ticks. Both boundary epochs remain exact despite demo-time compression. Store the mapping in the immutable plan. Configurable run length is allowed before upload, not while running; require `0 < departure_tick < arrival_tick < end_tick <= 360000`. Real FPGA tick rate is always 100 Hz. Physical duration and real demonstration duration must be labelled separately.

### States and invariants

Wire state IDs: `IDLE=0`, `LOADED=1`, `ARMED=2`, `RUNNING=3`, `SAFE=4`, `COMPLETE=5`, `ABORTED=6`.

| Trigger | Required state | Result |
|---|---|---|
| Successful commit | IDLE with valid staged plan | LOADED, tick 0, mask 0 |
| ARM | LOADED, matching mission | ARMED |
| START | ARMED, matching mission | RUNNING; reset tick divider and counter |
| Departure due | RUNNING, not executed, enough fuel | Emit departure; set mask bit 0 and actual tick; deduct once |
| Capture due | RUNNING, departure executed, enough fuel | Emit capture; set bit 1 and actual tick; deduct once; COMPLETE |
| Defined no-majority / illegal state / insufficient fuel | Armed or executing | SAFE latch; inhibit new burn events |
| ABORT command or labelled local abort button | Any loaded/armed/executing mission | ABORTED; inhibit future burns |
| CLEAR | Non-RUNNING state, explicit user reset | Stop tick generation for this mission, invalidate plan, IDLE |
| Power/program reset | Any | IDLE, no session, no plan; never auto-resume |

For started missions, a separate run-clock latch keeps ticks advancing in SAFE/ABORTED until `end_tick`. COMPLETE stops the simulation at capture. SAFE before START does not start the clock. CLEAR intentionally ends the simulation; it is not a spacecraft recovery maneuver.

Use `tick >= scheduled_tick` plus executed flags, not an equality-only event check. Each event fires at most once. An invalid transition changes no mission data. Do not automatically resume from SAFE or re-fire a missed capture.

### How motion follows hardware

1. Before confirmed departure, show the vehicle at the origin planet/parking-orbit abstraction for the board epoch.
2. After the board reports departure, initialize the interplanetary coast from the selected Lambert boundary state. Under normal operation the emitted tick must match the plan's departure tick.
3. Evaluate gravity-driven coast at the latest board epoch. Browser interpolation may interpolate between received snapshots; it must not invent a future authoritative tick.
4. Capture succeeds only when the FPGA reports the capture event at its planned epoch **and** the backend validates the matching mission/trajectory endpoint. If runtime event timing does not match the validated plan, label the plan invalid; do not substitute a successful endpoint.
5. SAFE/ABORTED after departure inhibits future burns but leaves the spacecraft coasting. A missed capture remains an uncaptured heliocentric pass; it must not become an automatic arrival. This simplified model omits Mars flyby gravity, so call it an “uncaptured coast,” not a precise flyby simulation.
6. No telemetry means “last received state; stale.” Holding that last image is a communications display behavior, not a claim that the spacecraft physically stopped. During an operator-started blackout the CCS may additionally show a labelled estimate beside the last received state, exactly as defined in section 18.5; the estimate never replaces confirmed values.
7. After reconnect, reconcile mission ID, tick, executed mask and actual event ticks before rendering the recovered state. Two retained event records are enough to reconstruct this fixed mission; an unbounded event log is unnecessary.

## 8. Canonical wire protocol v1

Freeze this before independent FPGA/bridge/backend work. `contracts/protocol_v1.json` and binary fixtures are the implementation source of truth, owned by Agent 1. Changes require its version bump and coordination. The bridge forwards bytes without interpreting this protocol.

### Frame layout

All multibyte numbers are unsigned little-endian. Maximum payload 128 bytes; maximum frame 142 bytes.

```text
offset  size  field
0       2     magic bytes A5 5A (literal order)
2       1     version = 1
3       1     message type
4       2     sequence
6       4     session_id
10      2     payload_length <= 128
12      N     payload
12+N    2     CRC16
```

CRC is CRC-16/CCITT-FALSE: polynomial `0x1021`, init `0xFFFF`, no reflection, xorout `0x0000`; cover bytes from version through final payload byte, excluding magic and CRC. Serialize CRC little-endian. Independent check: ASCII `123456789` → numeric `0x29B1`, wire bytes `B1 29`.

UART parser must handle fragmented/multiple frames, false magic inside corrupt frames, oversized lengths, bad CRC and invalid version. Bound buffering, use a 100 ms incomplete-frame timeout, rescan for the next candidate magic, and count errors. Test recovery after garbage followed by a valid frame. Do not dispatch until the entire CRC-valid frame is available. Validate the exact payload length for its type before accessing any field: 0 bytes for DISCOVER/GET_STATUS; 4 for OPEN_SESSION/ARM/START/ABORT/CLEAR; 28 for LOAD; 6 for COMMIT; 16 for ACK; 40 for STATUS.

### Message table

| Type | Name | Payload |
|---|---|---|
| `0x01` | DISCOVER | Empty; session 0, read-only |
| `0x02` | OPEN_SESSION | New nonzero session ID `u32`; header session 0; IDLE only |
| `0x03` | GET_STATUS | Empty; read-only, accepts session 0 |
| `0x10` | LOAD_PLAN | Fixed 28-byte plan below; stage only, IDLE only |
| `0x11` | COMMIT_PLAN | `mission_id:u32, plan_crc16:u16` |
| `0x12` | ARM | `mission_id:u32` |
| `0x13` | START | `mission_id:u32` |
| `0x14` | ABORT | `mission_id:u32` |
| `0x15` | CLEAR | `mission_id:u32` |
| `0x16` | SET_TRIP_DAYS | `mission_id:u32, trip_days:u32`; LOADED or ARMED; display only (section 18.3) |
| `0x80` | ACK/NACK | Fixed 16-byte reply below |
| `0x81` | STATUS | Fixed 40-byte telemetry below |

DISCOVER/GET_STATUS reply with STATUS; the header exposes the active session (0 after reset). OPEN_SESSION ACK reports the new session. Backend chooses a random nonzero 32-bit session ID and persists it with the active mission. Session IDs prevent accidental stale traffic, not malicious access; this is a local wired protocol.

After ordinary link loss, read status and resume the **existing** session; do not open a replacement or replay a queued START. A reset produces session 0 and no mission; report lost execution. OPEN_SESSION is allowed only in IDLE and clears the command replay cache. No automatic takeover while a mission is active.

Mission mutations require matching nonzero session. Stop-and-wait: only one unacknowledged mutation. Mutating sequences increase from 1 through 65535; require a fresh IDLE session before wrap. Exact retry of the last sequence and identical full command bytes returns the cached result without applying again. Same sequence with different bytes rejects `SEQ_CONFLICT`; older sequences reject `STALE_SEQ`. Keep the last command bytes, not just a collision-prone checksum. Read-only discovery/status queries do not change mutation sequencing. Telemetry uses its own wrapping sequence.

Validation order: frame integrity/type/length → session → duplicate/conflict/stale sequence → mission/state/value guards → atomic application. After valid shape/session/sequence, both APPLIED and REJECTED results consume/cache that new sequence. Thus repeating a successful START returns its original ACK even though the board is now RUNNING. Integrity, shape, session, conflict and stale failures do not advance the valid-session sequence high-water mark. OPEN_SESSION is handled separately: an identical repeat while IDLE with the same requested active session returns success without resetting sequence history.

### Plan payload, exactly 28 bytes

Seven `u32` fields, in order:

```text
mission_id, departure_tick, arrival_tick, end_tick,
initial_fuel_g, departure_fuel_g, capture_fuel_g
```

`mission_id` is nonzero and unique within the session. The backend also has a UUID and full SHA-256 plan digest; it stores their mapping to wire IDs. `plan_crc16` covers these exact 28 payload bytes with the CRC algorithm above, not the whole upload frame.

LOAD_PLAN fills a staging buffer only after CRC and bounds validation. COMMIT checks matching mission ID/staged payload CRC and atomically activates the plan. Incomplete/invalid upload never becomes LOADED. Reject invalid ordering, zero costs, sum overflow, or fuel costs exceeding initial fuel; widen sum arithmetic before comparison. New LOAD is allowed only in IDLE and replaces the staged image. Active missions require explicit CLEAR first.

### ACK/NACK payload, exactly 16 bytes

```text
original_type:u8, result:u8, detail:u16,
mission_id:u32, applied_tick:u32, plan_crc16:u16, reserved:u16=0
```

Result `0=APPLIED`, `1=REJECTED`. Detail codes: `0=OK`, `1=BAD_STATE`, `2=BAD_MISSION`, `3=BAD_SESSION`, `4=BAD_PLAN`, `5=BAD_PLAN_CRC`, `6=SEQ_CONFLICT`, `7=STALE_SEQ`, `8=INSUFFICIENT_FUEL`, `9=UNSUPPORTED`. For LOAD, APPLIED means staged; COMMIT means active; START means execution initiated. A USB write is never treated as an FPGA acknowledgment. Invalid frame CRC gets discarded/counted rather than acknowledged using untrusted fields.

Every ACK/NACK header echoes the request sequence and uses the board's current active session ID. Successful OPEN_SESSION therefore returns the new session ID; BAD_SESSION reports the actual board session, never endorses the incorrect request ID. The host correlates original type, sequence, session and mission before accepting a result. STATUS has independent telemetry sequence numbers. Malformed-length frames are discarded/counted without speculative payload reads.

### STATUS payload, exactly 40 bytes

```text
mission_id:u32, tick:u32,
state:u8, executed_mask:u8, safe_reason:u8, reserved0:u8=0,
fuel_remaining_g:u32, departure_executed_tick:u32, capture_executed_tick:u32,
masked_fault_count:u32, no_majority_count:u32, rx_error_count:u32,
plan_crc16:u16, reserved1:u16=0
```

Unset event tick is `0xFFFFFFFF`; mask bit 0 is departure, bit 1 capture. Safe reasons: `0=NONE`, `1=NO_MAJORITY`, `2=ILLEGAL_STATE`, `3=FUEL`, `4=INTERNAL_INVARIANT`. ABORTED is distinct from SAFE. Status fields must form one atomic snapshot. Emit at 10 Hz and immediately after transitions/events. ACK frames take output priority; bounded telemetry queues may coalesce status snapshots because event flags/ticks persist.

Retry timeout without artificial delay: 500 ms, three attempts. With delay: `500 ms + 2*maximum_demo_one_way_delay`, then three attempts of the exact same frame. On failure enter a host transport-error condition and reconcile status before any new mutation. Never retry indefinitely.

## 9. FPGA fault-tolerance implementation

Triplicate the **small execution control tuple**: state, next-event index/executed mask, remaining fuel and retained burn records. Keep the common schedule, UART, clock divider and supervisory logic simple; disclose that these are not triplicated.

Use whole-tuple majority: if any two tuples are equal, choose that tuple; if all differ, latch SAFE through the supervisor. Whole-tuple voting avoids constructing a nonsensical state from per-bit votes across three distinct tuples. Feed the validated voted state back into all three next-state computations to repair a transient divergent lane. Retain mismatch counters so a one-cycle correction is visible.

Preserve replicated registers using supported `preserve`/`dont_merge` and appropriate net attributes. **Inspect the compiled netlist**: three named modules alone do not prove the compiler kept three register banks. Confirm the actual installed Quartus Lite supports the attributes used. [S13]

Define two independent demo controls:

- `INJECT_SINGLE`: one debounced switch edge flips one specified bit in lane A's stored tuple, once. Correct majority remains; clock/events continue; correction counter increments.
- `INJECT_DIVERGENCE`: one edge injects two different masks into lanes A and B simultaneously, leaving all three complete tuples different. Supervisor detects no majority and inhibits future burn outputs.

Do not implement divergence by checking the switch directly in safety logic. It must respond to the actual corrupted register tuples. Two switches toggled sequentially are not a valid simultaneous double-fault test because feedback may repair the first fault before the second.

The supervisor retains the last validated ledger/event records, gates new burn strobes, and forces all lanes into SAFE on no-majority. The shared clock latch continues simulation time for an already started mission. Clock-edge priority: reset/explicit clear → safety fault/local abort → validated command → scheduled burn. An injection edge defers a due burn commit by one 50 MHz cycle so the actual corrupted tuple registers can be voted before execution; single-fault masking may still execute at the same 100 Hz mission tick, while no-majority suppresses it. Commit fuel, mask, event tick and emitted event atomically from the validated voted transition, never from one lane. Test faults at the event boundary; no direct switch-to-SAFE shortcut.

**Limits:** two wrong lanes that agree can outvote the correct lane. Shared clock/reset, plan memory, voter, supervisor and I/O remain single points. This is a scoped fault-injection demonstration, not radiation qualification, full spacecraft safety, or three independent computers. FPGA configuration-error detection is a separate feature and is out of scope. [S13]

## 10. Communication delay and disconnect semantics

Place delay in exactly one backend component, `DelayTransport`, wrapping the real serial transport. XIAO and FPGA do not add a second artificial delay.

Compute a displayed approximate physical one-way delay from simultaneous Earth/spacecraft positions at the applicable board epoch: `distance_km / 299792.458`. This is a geometric estimate, not a retarded-time communications solution. Predeparture range may be nearly zero under the parking-orbit abstraction.

Demonstration mode: `delay_demo_s = clamp(delay_physical_s/300, 0.1, 3.0)`. Label compression and clamp explicitly. Assign a monotonic release timestamp once when a frame enters a queue; do not reschedule it every animation frame or multiply by mission time compression. For commands use the latest known spacecraft state and mark the estimate's age. Preserve FIFO ordering by making each release time no earlier than its predecessor.

Apply delay to mission commands, their ACKs, and downlink telemetry. Administrative DISCOVER/OPEN_SESSION/GET_STATUS may bypass it only in a visibly labelled local diagnostics panel; they must not silently refresh the ground display. Ground UI observes delayed telemetry. Optional onboard diagnostics may show immediate telemetry only with an explicit “local onboard instrument” label.

Bound queues: at most 128 frames per direction; keep every pending mutation/ACK or fail explicitly; coalesce telemetry snapshots when necessary. Coalescing drops an old snapshot and enqueues the new one with its own release time; never replace its contents while preserving an earlier release time. Backend outage/reconnect drops queued unsent mutations and requires reconciliation. Already sent mutations may have applied: report unknown status until the board answers. No stale queued START is delivered after reconnect.

Test a software blackout and closing/reopening the host serial connection while **both boards stay powered**. A physical data-only disconnect is optional if verified to preserve power to both boards. Do not unplug one board's power while the other drives its UART pins; this can back-power the unpowered device. Loss of ground communication must not halt board execution. Onboard LED/retained event records provide evidence of autonomy.

## 11. Backend API and shared input contract

Run loopback only (`127.0.0.1`); serve the built browser from the backend for the demo. During development allow only the chosen localhost Vite origin. Check HTTP/WebSocket origins and use a random local session token for mutation/extension connections. This is a local demo deployment, not an Internet-ready service. Never expose serial control through an unauthenticated public tunnel.

Suggested paths are implementation commitments; Agent 1 creates schemas and fixtures before other agents depend on them:

| Method/path | Purpose |
|---|---|
| `GET /api/v1/health` | Backend/dependencies/cache/transport mode and current health |
| `POST /api/v1/planning/jobs` | Validate bounded inputs; return job ID immediately |
| `GET /api/v1/planning/jobs/{id}` | Progress, candidates, failures and source metadata |
| `DELETE /api/v1/planning/jobs/{id}` | Cancel pending search; no mission side effects |
| `GET /api/v1/plans/{id}` | Immutable validated plan, samples and provenance |
| `GET /api/v1/planets` | Supported planet IDs and selectable targets; initially Earth399 and Mars499 |
| `GET /api/v1/planets/{body_id}/info` | PlanetInfo for a validated scene epoch; read-only, cached/partial responses permitted |
| `POST /api/v1/missions` | Create runtime mission from validated plan and selected transport |
| `POST /api/v1/missions/{id}/commands` | Typed upload/arm/start/abort/clear; mouse/core use only |
| `GET /api/v1/missions/{id}` | Last authoritative observed board state and freshness |
| `GET /api/v1/input/context` | Current selection screen, revision, allowed target IDs |
| `POST /api/v1/input/intents` | Mouse/keyboard/EEG generic selection proposals |
| `POST /api/v1/input/sessions` | Register optional source and receive source session ID |
| `POST /api/v1/input/sessions/{id}/heartbeat` | Every 500 ms; return session-scoped context, revision and expiry |
| `DELETE /api/v1/input/sessions/{id}` | Disable input source and clear uncommitted proposals |
| `WS /api/v1/events` | Typed snapshots, job updates, input context and transport events |

Use one serial worker, one mission mutation lock, and a worker/thread/process for the bounded numerical solve. The event loop must remain responsive while NumPy/Numba starts or NASA requests wait. Serial command queue and planning queue are bounded. Only one mission may control the board at once.

### Canonical objects

`MissionPlan`: schema version, UUID, SHA-256, model version, origin/destination IDs, UTC labels and TDB boundaries, frame/units, planet boundary vectors, Lambert velocities, numerical residuals, grid/objective metadata, vehicle and masses, unrounded and integer fuel costs, tick mapping, sampled path, complete NASA/cache provenance. Hash canonical serialization without the digest field. No edits after validation; changes create a new plan.

`MissionSnapshot`: server sequence, mission/session/wire IDs, plan digest/CRC, controller source (`fpga` or `simulator`), state, board tick, executed mask/actual event ticks, remaining fuel, fault counts, observed age, transport state, delayed/local view label, reconstructed spacecraft/planet states, and failure details. Keep raw serial/physics schema version traceable in logs.

`InputContext`:

```json
{
  "schema_version": 1,
  "context_id": "uuid",
  "revision": 7,
  "input_session_id": "uuid",
  "screen": "planet_choice",
  "allowed_targets": ["planet.399", "planet.499"],
  "enabled": true,
  "expires_in_ms": 10000
}
```

`SelectionIntent`:

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "input_session_id": "uuid",
  "context_id": "uuid",
  "context_revision": 7,
  "target_id": "planet.499",
  "source": "live_eeg",
  "evidence": {
    "window_start_source_ms": 102000,
    "window_end_source_ms": 104000,
    "sample_count": 500,
    "sample_rate_hz": 250,
    "winner_score": 0.71,
    "runner_up_score": 0.28,
    "quality": "valid"
  }
}
```

Source enum: `mouse`, `keyboard`, `live_eeg`, `replay`, `synthetic`. Scores are evidence, not probabilities. Source monotonic timestamps are meaningful only inside that source process; do not subtract them from another process's clock. Backend records receipt time, sets short context expiry (10 seconds renewed during an active selection period), requires a current source heartbeat (<=2 seconds old), and rejects a source that cannot attest fresh evidence from the current context. Heartbeat payload is `{context_id, context_revision, source_state, acquisition_age_ms, stimulus_ready}`; the backend ignores requests to enable forbidden actions and returns the authoritative current context. A fresh heartbeat renews the same valid context expiry without incrementing its revision; a changed screen/action set does increment it. GET context and event subscriptions are scoped to the authenticated input session. Mouse/keyboard use the same semantic validation without requiring EEG evidence fields.

On context change, the extension must clear its sample/decision window and wait for entirely new evidence. Context revisions increase on selection, mission-state changes, reconnection, and disabled input. Core rejects stale/expired contexts, unknown targets, inactive sessions, duplicates and forbidden actions. Return `{event_id, accepted, reason, new_context_revision}`. Cache event IDs for the active input session. Stable target IDs are semantic, not screen coordinates.

Fresh windows alone do not prevent a continuously held gaze from selecting the next screen. Require an explicit release/rearm step: the extension observes a calibrated no-control interval of at least one second at a neutral fixation point before enabling a consequential confirmation, and places the confirm target opposite the previous selected target. If the no-control gate is unreliable, require operator rearm and disclose that the flow is assisted. The core accepts at most one intent per context revision.

**Current capability is `planet_explore` only.** Accepted `planet.399`/`planet.499` intents update the selected body and open its information card; they never change the mission destination, launch a planning job or upload/start a mission. Information-screen targets are `planet.more_details` and `navigation.back`. Guard async response rendering by selected body/context revision so an old Earth response cannot overwrite a newly selected Mars card. No direct FPGA commands are exposed to the extension's token.

Future-only design: EEG route selection and upload/start would require explicit added capability, a distinct confirm/cancel context and fresh release/rearm evidence. `start` would retain the matching-plan, ARMED-state and hardware-ACK guards used by mouse. These actions are disabled for EEG in this round. Abort/reset remain available through ordinary operator controls regardless of EEG state.

Current `synthetic`/`replay` inputs may operate read-only planet exploration with clear source labels, but no EEG source can command the physical FPGA in this round. A later mission-input phase could add explicit operator-enabled synthetic/replay hardware test mode with a persistent banner and log. The core simulator transport remains accessible without any hardware and must implement identical plan/protocol/state semantics; it is always labelled `SIMULATED CONTROLLER`.

## 12. Frontend requirements that prevent integration failure

- One primary page: route inputs/comparison, orbit view, mission actions, hardware status, fault history and source/model drawer.
- Normalize coordinates for rendering only: e.g. 1 au = 10 display units. Declare axis mapping once (`x,y,z` scientific → `x,z,-y` Three.js); apply it to planets, ship and paths consistently. Physics remains in km.
- Planet marker sizes are illustrative and labelled; do not imply displayed radii are to scale.
- Plot supplied timestamps and trajectories, not a decorative spline that misses the target. Keep physics/scene epochs synchronized.
- Show both planned preview and executed mission distinctly. Rejected upload or missing board acknowledgment cannot switch to RUNNING.
- Persistent indicators: FPGA/simulator, NASA live-fetch/cached/synthetic, source input, link freshness, mission status, compressed time/delay.
- A reconnect requests a full snapshot before incremental events. Ignore older server sequence updates; avoid applying the same burn twice.
- Stop expensive rendering work when hidden. Core FPGA execution continues; hidden browser must not stall the backend.
- Reserve a two-choice selection panel for the optional brain extension, but do not include flashing or EEG dependencies in normal core UI startup.
- Provide keyboard operation and readable status/error text even if 3D rendering fails. No WebGPU requirement; normal Three.js WebGL is sufficient.

## 13. Current six-agent division and ownership

Use the full copy-paste prompts in `TEAM_AGENT_PROMPTS.md`. The user confirmed five agents available now and Affan's Codex busy in workshops; Affan owns brain control when available. These are coding-agent assignments, not six human team members. Human board/headset handling still needs the relevant teammate.

| Agent | Exclusive implementation ownership | Must deliver first | Depends on |
|---|---|---|---|
| 1 — your Claude: integration/backend | `contracts/`, `backend/api/`, `backend/runtime/`, root manifests/start scripts/tools/docs | Frozen schemas, protocol fixtures, mock transport, source labels | Nothing; coordinates all contract changes |
| 2 — Sadat's Claude: NASA/physics/data | `backend/ephemeris/`, `backend/planner/`, `backend/physics/`, `backend/planet_data/`, numerical/data tests | Cached known route + PlanetInfo fixture | Agent 1 plan/data schemas |
| 3 — Zain's Claude: FPGA | `hardware/fpga/`, RTL tests | Heartbeat then UART STATUS, then schedule | Agent 1 protocol bytes; real board owner |
| 4 — your Codex: bridge/transport | `hardware/xiao/`, `backend/transport/`, transport tests | Transparent USB/UART, golden-frame round trip | Agent 1 protocol; Agent 3 UART |
| 5 — Sadat's Cursor: browser | `frontend/` except `frontend/src/bci/` | Mock-driven planet cards and ordinary-input mission flow | Agent 1 APIs; Agent 2 samples/data |
| 6 — Affan's Codex: brain + BCI widget | `brain/`, `frontend/src/bci/`, EEG tests | Synthetic planet-selection intent opens matching card, then device integration | Agents 1/5 interface, brain file, actual workshop device |

Agent 5 creates an agreed optional-widget insertion point and reserves `frontend/src/bci/` for Agent 6. Agent 1 owns shared schemas/root dependency edits; component owners request changes explicitly. Each owner tests its own boundary. The team lead publishes this table and the agreed PR policy into the actual repository's AGENTS.md before agents rely on them.

Suggested human responsibility: Abderrahmene owns physical FPGA/XIAO bring-up; the team lead owns integration and scope. Assign other human owners based on actual experience, not assumed names. One identified human must own any live EEG experiment.

Use feature branches/worktrees from an agreed current integration branch; no agents committing over each other in one working directory. The lead first publishes the current policy into the actual repo: task PRs into dev, lead integrates after boundary checks, lead alone promotes tested dev to main. This replaces the ZIP's author-self-merge policy. Integrate small passing changes early rather than one final merge of every branch. Every handoff includes schema version, command to run, fixture, test result and known limitation. No silent shared-contract edits.

## 14. Fifteen-hour execution plan

Times are relative to implementation start; rebase against the **actual** remaining time and organizer deadline.

| Window | Core milestone | Optional EEG work |
|---|---|---|
| 0–0.5 h | Toolchain/board heartbeat, dependency smoke test, schemas and planet fixtures frozen | Affan joins when available; confirm workshop device/path |
| 0.5–2 h | UART round trip, mock mission/planet flow, first NASA cache/validated route | Synthetic intent -> selected planet -> information card |
| 2–4 h | Actual plan upload/start/status with browser; math and hardware meet | Separate live acquisition attempt; swap adapter without core changes |
| 4–7 h | Nominal full mission; stale/reconnect behavior; single fault | Tune isolated two-choice selection; no core disruption |
| 7–10 h | Divergence/uncaptured coast; offline run; integrated tests | Merge read-only widget once ordinary planet UI/API and isolation tests pass |
| 10–12 h | Full system soak, clean startup, repeated demo | Keep only demonstrated reliable EEG actions |
| 12–15 h | Freeze features, record demo, verify submission/package and rehearse | No new paradigm, hardware family or dependencies |

Cut order if behind: brain → Venus → seven-segment extras → delay embellishments → large search grid. Do not cut truthful hardware authority, numerical validation, source labels, fault limits or basic reconnect handling.

Hardware checkpoint at hour 4: if no reliable end-to-end board mission, stop optional work and fix the minimal core. A simulator-only fallback can ship honestly, but it does not satisfy the intended hardware result. Do not disguise it as FPGA operation.

## 15. Acceptance tests and definition of done

Record actual results in `artifacts/acceptance.md` during implementation. All thresholds below are proposed gates until measured.

### NASA and physics

- Reject HTTP-200 error text, missing table markers, wrong body/center/frame/units and nonfinite vectors.
- UTC/TDB round-trip preserves selected dates; boundary epoch arrays exactly match requests.
- One published Lambert reference case passes; selected NASA-backed route passes independent propagation residuals.
- Coast energy/angular momentum conservation and solver-tolerance convergence checked.
- Required fuel rises with payload/Δv and falls with Isp; capacity and gram-rounding edge cases checked.
- Earliest arrival and shortest duration intentionally differ in a test fixture; failed cells cannot win.
- Offline cached search reproduces the same candidate and provenance; out-of-cache dates fail explicitly.

### Protocol, FPGA and bridge

- CRC known vector and cross-language golden frames agree byte-for-byte; packet size/layout assertions pass.
- At least 100 valid request/reply exchanges without unexplained framing errors.
- Fragmented, concatenated, corrupt, oversized and timed-out packets recover without executing garbage.
- Same sequence retry does not reapply a mutation; conflict/older sequence rejected.
- Uncommitted, bad-CRC and invalid-bounds plans cannot arm. START in wrong state fails.
- Positive 50 MHz timing slack; no unreviewed unconstrained logic paths; three control register banks confirmed after compilation.
- Correct departure/capture masks, ticks and integer fuel ledger in an ordinary full mission.
- Single lane upset is masked and visibly counted; defined divergence inhibits capture; test injection at a burn boundary.
- Identical wrong-lane test demonstrates/documented TMR limit; no claim that it is detected.
- Host serial closure/blackout while both boards remain powered; board advances; reconnect recovers ticks/events without re-start.
- Reset invalidates plan/session; replaying the old START cannot resume it.
- At least ten-minute idle/mission-cycle soak without buffer growth, duplicate events or UI/API hang.

### Integrated product

- Five consecutive full nominal hardware runs, including clean relaunch and one serial disconnect/reconnect with both boards powered.
- SAFE after departure produces continued coast and no successful capture; before departure produces no launched transfer.
- Browser never completes without matching board event evidence and numerical consistency checks.
- Ground view is stale during blackout; local diagnostics, if shown, are distinctly labelled.
- Core launches and operates with brain environment uninstalled/disabled.
- Planet selection/highlight/card works with both ordinary input and a canonical synthetic intent; sources, dates and unsupported Mars weather are labelled accurately.
- All GUI actions available without EEG. Synthetic source cannot silently operate hardware.
- Cached NASA data, frontend assets, locked packages/install instructions, `.sof` and XIAO firmware/source are available locally for demo recovery.
- Team can explain NASA inputs vs computed trajectories, FPGA authority, compressed time, approximations and TMR limits.

“Ready” means these gates pass on the actual demo laptop and wired board. Source research alone cannot establish readiness.

## 16. Required implementation deliverables and runbook

```text
contracts/                      canonical JSON schemas + protocol binary fixtures
backend/{api,runtime,ephemeris,planner,physics,transport}/
frontend/                       locked TypeScript/React/Three.js application
hardware/fpga/                  RTL, constraints, tests, build instructions
hardware/xiao/                  bridge firmware + board/core configuration
data/ephemeris/                 bounded verified demo cache + provenance
tests/                          numerical, API, protocol, integrated fixtures
scripts/                        bootstrap, start-demo, smoke-test scripts
artifacts/                      release binaries, build info, acceptance record
README.md                       exact setup, run, recovery and model limitations
THIRD_PARTY_NOTICES.md           dependency/data notices and applicable licenses
```

Provide commands that actually exist in the finished repo; do not leave placeholder startup paths in README. Scripts must select the intended Python environment, fail clearly on missing dependencies/COM port, avoid duplicate serial owners, and offer explicit `fpga` or `simulator` mode. Store no credentials, local tokens or EEG recordings in Git.

Demo startup: power/program FPGA → connect XIAO → launch backend and browser → verify FPGA label/session/status → open cached validated route → upload/commit/arm → start → inject single fault → verify progression → run separate divergence case → inspect uncaptured coast/reconnection evidence. Keep a spare set of known-good cables and the second boards available; do not wire both into the live protocol simultaneously.

Suggested two-minute presentation: explain NASA route and fuel tradeoff; show actual board execution; demonstrate masked fault and delayed/stale ground state; show the defined safe-mode case. Use two short mission presets if needed rather than racing through a confusing single run. Record a backup of a real hardware run and label playback honestly.

Submission checklist from the hacker packet: draft due Sunday November 15 at 12:00 AM Eastern; final due November 15 at 12:00 PM Eastern; no late entries. Public repository, every teammate, project/problem description, chosen tracks, disclosed AI tools and demo video no longer than three minutes. Demo session 1:15–2:15 PM Eastern; aim for about two minutes of explanation/live operation. Check organizer updates for changes. Never publish partner keys or restricted EEG datasets. g.tec hardware users additionally submit to g.tec by November 30 using the organizers' instructions. [S16, S17]

## 17. Primary sources and verification notes

Reviewed 2026-11-14. Exact hardware operation, package installation and compilation are still implementation gates.

- **S1 — Event:** https://hackthenest.tech/ (public track descriptions; current organizer updates take precedence over printed schedules).
- **S2 — Horizons API:** https://ssd-api.jpl.nasa.gov/doc/horizons.html
- **S3 — Frames/time:** https://ssd.jpl.nasa.gov/horizons/manual.html and https://docs.astropy.org/en/stable/time/index.html
- **S4 — NASA fair use/batching:** https://ssd-api.jpl.nasa.gov/doc/ and https://ssd-api.jpl.nasa.gov/doc/horizons_file.html
- **S5 — Pinned solver:** https://pypi.org/project/lamberthub/1.0.0/ ; https://raw.githubusercontent.com/jorgepiloto/lamberthub/v1.0.0/src/lamberthub/universal_solvers/izzo.py ; https://raw.githubusercontent.com/jorgepiloto/lamberthub/v1.0.0/LICENSE
- **S6 — Terasic specifications/manual:** https://www.terasic.com.tw/cgi-bin/page/archive.pl?CategoryNo=218&Language=English&No=1021&PartNo=2 ; https://www.mouser.com/datasheet/3/996/1/DE10-Lite_User_Manual.pdf (Terasic-authored manual; GPIO/clock tables).
- **S7 — Quartus fallback:** https://www.altera.com/downloads/fpga-development-tools/quartus-prime-lite-edition-design-software-version-25-1-windows
- **S8 — XIAO pin map:** https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- **S9 — ESP32 serial/USB:** https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html ; https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html
- **S10 — Model/constants:** https://trajbrowser.arc.nasa.gov/user_guide.php ; https://ssd.jpl.nasa.gov/astro_par.html
- **S11 — Rocket equation:** https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/
- **S12 — Numerical propagation:** https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- **S13 — Register preservation/fault limits:** https://cdrdv2-public.intel.com/653789/quartusii_handbook_10_0_1.pdf ; https://ntrs.nasa.gov/api/citations/19780015853/downloads/19780015853.pdf ; https://docs.altera.com/r/docs/683865/current/max-10-fpga-configuration-user-guide/seu-mitigation-and-configuration-error-detection
- **S14 — API events:** https://fastapi.tiangolo.com/advanced/websockets/
- **S15 — Browser toolchain:** https://vite.dev/guide/
- **S16 — Local event packet:** `C:/Users/Naceri/Downloads/Hack The Nest 2026 Hacker Packet.pdf`, especially pages 9, 16, 19, 21 and 23.
- **S17 — Local BCI guide:** `C:/Users/Naceri/Downloads/Hack_The_Nest_2026_Mind_and_Machine_Guide.pdf`, especially pages 1–6. Explicitly allows no-headset dataset/simulation participation; source mode must still be described honestly.
- **S18 — Earth event API:** https://eonet.gsfc.nasa.gov/docs/v3 (event metadata and bounded category/date queries; not arbitrary planetary weather).
- **S19 — Planet facts/Mars data limits:** https://science.nasa.gov/mars/facts/ ; https://science.nasa.gov/mission/insight/ (mission ended in 2022).

## 18. Shuttle and Central Control Station (CCS): adopted 2026-11-15

Adopted by the humans from Zain's proposal, with the changes listed in 18.9. This section is the single reference for the backend, the GUI, the FPGA and the VGA display. Where an older sentence in this file disagrees, this section wins. Status: **specified, not yet implemented or tested** except where 18.8 says otherwise.

### 18.1 Roles and story

- **CCS** = the laptop (backend + browser GUI). **Shuttle** = the DE10-Lite. **Radio link** = the XIAO bridge (unchanged, transparent).
- The CCS plans the route, uploads it, arms and launches. After launch the operator starts a **blackout**. The shuttle flies and burns alone from its stored plan and counts down the days to arrival on its own displays. The CCS has no telemetry and shows only a labelled **estimate**. Contact returns **at the planned arrival** and the CCS replaces the estimate with what the shuttle really did.
- Target presentation split: about 1 minute planning on the CCS, about 1 minute of flight on the shuttle. Run length is only a plan value (18.2); no code depends on a particular length.

### 18.2 Timing

- The board tick is always 100 Hz. `departure_tick`, `arrival_tick` and `end_tick` come from the uploaded plan (section 7 bounds unchanged). The required values for every catalogue plan are 500 / 6500 / 6800 (section 19.1). Plans generated before that rule use 5 / 6005 / 6305 or 10 / 12010 / 12610 and are to be regenerated.
- Ticks before `departure_tick` are a real-time T-minus countdown: 5 s (section 19.1).
- `trip_days = max(1, min(9999, floor(tof_s / 86400 + 0.5)))`, computed by the backend from the plan.

### 18.3 Protocol addition: `SET_TRIP_DAYS` (type `0x16`), contracts 1.2.0

Additive. Every existing frame, ACK and STATUS stays byte for byte the same.

| Field | Value |
|---|---|
| Direction, kind | Host to board; mutation: active session, next sequence, one 16-byte ACK (`original_type = 0x16`) |
| Payload | 8 bytes, little-endian: `mission_id:u32`, `trip_days:u32` |
| Allowed when | Active plan with the same `mission_id`, state `LOADED` or `ARMED` |
| ACK detail | `OK`; `BAD_STATE` (no active plan or wrong state); `BAD_MISSION`; `BAD_PLAN` (`trip_days` 0 or above 9999); session/sequence errors as for any mutation |
| Lifetime | Forgotten on CLEAR, on a new COMMIT_PLAN and on reset. Not reported in STATUS |
| Retry | An identical retry (same sequence) returns the cached ACK and is not applied twice, like every mutation |

When the backend sends it: as the **third step of `upload`**, directly after the COMMIT_PLAN ACK, while the board is `LOADED`. `upload` succeeds only if LOAD_PLAN, COMMIT_PLAN and SET_TRIP_DAYS are all applied. ARM and START are unchanged.

Golden frame (session `0x1A2B3C4D`, sequence 3, mission `0x00C0FFEE`, 300 days), to be added to `contracts/fixtures/frames/` with its ACK:

```text
A5 5A 01 16 03 00 4D 3C 2B 1A 08 00 EE FF C0 00 2C 01 00 00 58 85
```

### 18.4 Days to arrival: one formula on both sides (integers only)

```text
trip_ticks = arrival_tick - departure_tick
if tick <= departure_tick:   elapsed_days = 0
elif tick >= arrival_tick:   elapsed_days = trip_days
else:                        elapsed_days = floor((tick - departure_tick) * trip_days / trip_ticks)
days_to_arrival = trip_days - elapsed_days
```

Display value only: it never gates a burn. It keeps counting in SAFE and ABORTED until the planned arrival, then shows 0.

### 18.5 Keep-alive, blackout, estimate, sync (backend, `@ANaceri26/claude`)

1. **Keep-alive.** While the link is open and no blackout is active, send `GET_STATUS` every 0.5 s. The shuttle declares the link lost after 2 s without a valid frame.
2. **Blackout is a button, never a pulled cable** (unplugging the XIAO removes its power while the FPGA still drives its pins). New mission commands `blackout_start` and `blackout_end` on `POST /api/v1/missions/{id}/commands`. `blackout_start` is accepted only in `RUNNING`. During a blackout the backend sends **nothing** to the board (no keep-alive, no commands; other commands are refused with a clear "no contact" error) and **discards** every frame it receives. The serial port stays open.
3. **Estimate.** `tick_est = min(end_tick, last_tick + floor((now - last_status_time) * 100))`. From it the backend derives estimated epoch, estimated position on the plan's `nominal_path`, `days_to_arrival` (18.4) and expected events. Fuel changes only at the two burns, so the fuel estimate is the last confirmed value plus "capture burn expected" at `arrival_tick`; it is not a continuous gauge.
4. **Sync at arrival.** The backend ends the blackout by itself when `tick_est >= arrival_tick` (the operator may end it earlier). It resumes the keep-alive; the first valid STATUS replaces the estimate completely. It then reports what happened out of contact: events whose executed tick lies inside the blackout, and every difference between the estimate and the truth (for example: estimate "arrived", truth SAFE with no capture).
5. **Never** turn an estimate into a result. Until a STATUS confirms it, capture is "expected", not "done". `outcome` stays `pending` during a blackout.
6. `LINK_DELAY_DEMO` stays **off** for this storyline (an added delay of seconds would trip the 2 s watchdog).

Snapshot additions (MissionSnapshot, contracts 1.2.0; names are fixed here so the GUI can be built against them):

| Field | Meaning |
|---|---|
| `link.blackout` | `true` while a blackout is active |
| `trip` | `{ "trip_days": int or null, "days_to_arrival": int or null }` from confirmed telemetry |
| `estimate` | `null`, or during a blackout `{ "tick", "epoch_jd_tdb", "days_to_arrival", "spacecraft": { "phase", "r_km" }, "fuel_remaining_g", "expected_events": ["departure" / "capture"] }` |
| `reconciliation` | `null`, or after a sync `{ "blackout_start_tick", "blackout_end_tick", "events_during_blackout": [...], "estimate_matched": bool, "differences": [text] }` |

During a blackout the existing top-level fields (`state`, `tick`, `spacecraft`, `fuel_remaining_g`) keep the **last received** values. Only `estimate` moves.

### 18.6 Shuttle (FPGA and VGA, Zain and `@Zain-Usmani10/claude`)

Already in `dev` (simulation only, not proven on the board): `link_watchdog`, `SET_TRIP_DAYS` handling, `trip_clock`, seven-segment cockpit. Required behaviour, to check against this section:

- `SET_TRIP_DAYS` exactly as 18.3, including the cached-ACK retry and the golden frame above.
- Link lost = a link was seen and then no CRC-valid frame for 2.00 s. Any valid frame clears it. The flag is display only: it never changes state, ticks, burns or STATUS bytes.
- Days counter exactly as 18.4.
- Seven-segment: `HEX5 HEX4` state (`Id Ld Ar rn SF Co Ab`, alternating with `nL` once per second while the link is lost); `HEX3..HEX0`: `----` in IDLE, trip days in LOADED/ARMED, T-minus `SS.cc` before departure, days to arrival after departure.
- **VGA cockpit is now allowed** (Zain builds it). It is display only and must show nothing that is not one of these board values: state, tick, executed mask, departure and capture executed ticks, fuel remaining (g), safe reason, masked-fault and no-majority counts, link-lost flag, trip days, days to arrival, T-minus. Same source registers as STATUS (the voted values), so the monitor and the CCS can never disagree after a sync. It must not change timing of the UART or the 100 Hz tick, and the build must still meet timing.
- Still required before anything is called working: the real round trip through the XIAO on the board (probe output posted), then a full mission, then a blackout run.

### 18.7 GUI (`@sadattanzim01/cursor`)

Built only from the snapshot fields above; the browser computes no mission values of its own.

- Days-to-arrival readout from `trip.days_to_arrival` (from `estimate.days_to_arrival` during a blackout).
- T-minus countdown before departure, from `tick` and the plan's `departure_tick`.
- **Start blackout** control, enabled only in `RUNNING`; sends `blackout_start`.
- While `link.blackout` is true: a "Contact lost" banner; the confirmed shuttle marker stays at its last confirmed position; a second **ghost marker** and a **dashed line** along the plan's `nominal_path` show `estimate`; every estimated number carries the word "estimate". Mission actions other than ending the blackout are disabled.
- On sync: remove banner, ghost and dashes; show `reconciliation` as a short "While out of contact" summary, with differences highlighted.
- Never show "Arrived" from an estimate.

### 18.8 What exists today

| Part | State |
|---|---|
| FPGA watchdog, `0x16`, days counter, seven-segment | Merged, simulation only |
| VGA cockpit | Not built |
| Contracts 1.2.0 (golden frame, snapshot fields, commands) | Not written |
| Backend keep-alive, blackout, estimate, sync; simulator support for `0x16` | Not built |
| GUI elements of 18.7 | Not built |
| Real board round trip | Not done |

### 18.9 Differences from Zain's original proposal

- Contact returns **at arrival**, not before it.
- Blackout by button only; no cable pulling.
- `SET_TRIP_DAYS` is sent inside `upload` (state LOADED), not as a separate operator step.
- Keep-alive every 0.5 s rather than 1 s.
- The launch countdown is 5 s (section 19.1), not 10 s.
- Fuel is not estimated continuously (18.5 item 3).
- Boot from flash stays out of scope.

## 19. Time scaling: one rule for every trip (adopted 2026-11-15)

Whatever the route maths produces, it ends in one number: the trip length in days. Everything below follows from it. Status: specified; presentation plans today still use a 5-tick countdown and must be regenerated to this rule.

### 19.1 The rule

| Phase | Board ticks (100 Hz) | Real time | Simulated time |
|---|---|---|---|
| Launch countdown | `departure_tick = 500` | 5 s | 1 : 1 with real time (5 simulated seconds) |
| Flight | `arrival_tick = departure_tick + 6000` | 60 s | the whole trip: `sim_days_per_second = trip_days / 60` |
| After planned arrival | `end_tick = arrival_tick + 300` | 3 s | room to show a missed capture |

- Every catalogue plan uses exactly these three tick values, whatever its trip length. A 3-year trip and a 4-month trip both fly in 60 s; only `sim_days_per_second` differs.
- `trip_days` is the value of section 18.2. Sim days per tick = `trip_days / 6000`. The shuttle never receives this fraction: it receives `trip_days` (`SET_TRIP_DAYS`) and already knows its ticks, and counts days with the integer formula of 18.4.
- The numbers 500 / 6000 / 300 live in **one place** (`backend/timescale/`); planner, backend and tests import them. Changing the demo length is a one-line change followed by regenerating the plans.

### 19.2 What each clock shows

- **CCS (laptop):** an absolute calendar date (day, month, year). It is the real date of the plan's NASA data (`epoch_jd_tdb` of the confirmed tick; of `estimate.tick` in a blackout). Plans currently depart in 2026 to 2027; moving the story to another year means refetching and revalidating the NASA data, so it is not done by relabelling.
- **Shuttle (FPGA):** relative time only: days to arrival, starting at `trip_days` and counting down uniformly to 0 (18.4). No calendar.

### 19.3 When time moves (GUI behaviour)

1. **Browsing and planet close-up:** time stands still. The date is the fixed scene date; planets do not run ahead and no counter spins.
2. **Launch approved:** the calendar and the planets fast-forward to the departure date (a short GUI animation, about 3 s, while the backend uploads and arms). This is presentation only; nothing is sent to the board about it.
3. **START:** a 5 s real-time countdown (the 500 predeparture ticks), with the launch animation. Sim time equals real time.
4. **After the departure burn is confirmed:** sim time takes over at `sim_days_per_second`. The date, the days-to-arrival readout, the planets and the shuttle all advance together from the confirmed tick; none of them has its own clock.
5. **Arrival or end:** time stops at the confirmed final tick.

All eight planets move by the same date (real angles from NASA positions; display distances may stay compressed and are labelled).

## 20. Fleet: shuttles are tracked, not assumed (adopted 2026-11-15)

Status: specified, not built. Laptop-side bookkeeping only; the board and the wire protocol are unaffected.

- The world starts with a fixed fleet from `data/fleet.json`. Default: Earth 1 Standard + 1 Long-range; Venus 1 Standard; Mars 1 Standard; Mercury 1 Long-range; Jupiter 1 Long-range. Each shuttle has an id, a name, a class (`standard` = the 450 s model, `long_range` = the 900 s model) and a location.
- Location is exactly one of: `docked` at a body, `in_flight` on a mission, `lost` (left on an uncaptured coast).
- **Launch rule:** a mission can be created only if a shuttle of the plan's vehicle class is docked at the plan's origin. That shuttle is bound to the mission.
- **Moves happen only on board evidence:** departure burn confirmed → `in_flight`; COMPLETE with capture confirmed → `docked` at the destination; SAFE or ABORTED after departure → `lost`; abort or clear before departure → still `docked` at the origin.
- One flight at a time (one FPGA).
- The fleet persists across backend restarts and has an explicit operator reset to the starting fleet.
- UI names: **Standard shuttle** and **Long-range shuttle**, same styling. Model numbers stay in the details drawer. Routes with no plan are shown as **Out of range for this shuttle** (fuel) or **Route not computed**; no other explanation on screen.
- API (contracts 1.2.0): `GET /api/v1/fleet`; `POST /api/v1/fleet/reset` (operator); `POST /api/v1/missions` gains `shuttle_id` and refuses with `NO_SHUTTLE_DOCKED` when the rule fails; MissionSnapshot gains `shuttle_id`.
