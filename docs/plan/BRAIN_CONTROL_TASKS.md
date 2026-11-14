# INTERSTELLAR — optional brain-control implementation contract

> **Repo note (added at setup, 2026-11-14):** `AGENTS.md` is authoritative for roles, ownership and git policy; it overrides this file where they differ. All code paths in this file live under `app/` (e.g. `backend/api/` means `app/backend/api/`, `contracts/` means `app/contracts/`). Plan files are in `docs/plan/`. Agents: `@ANaceri26/claude` (leader/integrator), `@ANaceri26/codex` (XIAO/transport), `@sadattanzim01/claude` (NASA/physics), `@sadattanzim01/cursor` (frontend), `@AffanSyed07/codex` (brain). **The FPGA is owned by Zain (`@Zain-Usmani10`, human) working directly in Quartus; there is no Zain board agent.** Read "Zain's Claude" below as "Zain". The board bugs in TEAM_AGENT_PROMPTS.md section 3 are fixed in `tools/board`.

Version: 1.2, 2026-11-14. Depends on `MAIN_BACKEND_FPGA_TASKS.md` v1.2; shared input schema remains v1. Operational owner: Affan's Codex. Full team prompts are in `TEAM_AGENT_PROMPTS.md`.

## 1. Purpose and priority

Current milestone: **a headset/signal selects Earth or Mars in the same 3D Interstellar app and opens that planet's sourced information panel**. First prove this connection end to end. The user explicitly deferred games, route orders and EEG-controlled mission upload/start. This is a discrete selection tool, not thought reading, continuous spacecraft steering, a medical device, or a proven accessibility solution.

**Keep core development independent; Affan develops this extension in parallel when available.** Start with synthetic inputs and a mock core API. Integrate the read-only widget once ordinary planet selection/API behavior and extension-isolation tests pass; headset availability must not block FPGA work. Removing this module must require no FPGA changes and must not break ordinary operation. Full hardware mission acceptance remains a separate core release gate.

Main track remains Beyond the Horizon. Mind and Machine is the additional track. No quantum work is included.

### Planet data and what “looking at a planet” means

EEG does not automatically identify an arbitrary object that a person looks at. For the initial SSVEP implementation, associate two stable visual targets with Earth and Mars, classify the elicited response, then highlight/open the matching planet. A sponsor-working P300 selector can use the same semantic targets. Free-gaze eye tracking is a separate technique and is not included.

First bridge: `signal adapter → decoder → SelectionIntent(planet.399 or planet.499) → core validation → selected planet + information panel`. The normal mouse/keyboard selection uses the same action. Choosing a planet for information must not silently change the mission destination or start planning/execution.

The NASA owner provides `PlanetInfo`, not Affan's decoder. Reuse Horizons orbital states and sourced stable facts. After the basic card works, EONET v3 adds Earth storm/wildfire event metadata; this is dated Earth hazard information, not planetary health or Mars weather. Display observation/retrieval dates separately from the mission epoch. Current Mars weather remains unavailable unless a separately verified source is added; InSight ended in 2022. [B15]

Do not build APOD, asteroid, Landsat, MODIS, Worldview, Prithvi and exoplanet integrations merely because the track lists them. The first milestone needs a correct selected-body data card, not a catalogue of sponsor APIs.

Future route/order controls described below are explicitly deferred design material. Keep them absent from the current EEG allowed-target list and token capability.

### Event guide correction: a headset is not required

The local `Hack_The_Nest_2026_Mind_and_Machine_Guide.pdf` explicitly permits recorded datasets and simulated signals without hardware (page 1), explains PiEEG Cloud simulated streams (page 5), and gives a local simulator starter (page 6). The earlier context's interpretation that only live-headset work can enter is incorrect. The guide also asks for a signal-driven outcome at the demo: show the selection changing the product, not merely a waveform. [B1]

There are three valid but different product modes:

| Mode | What it demonstrates | Honest label |
|---|---|---|
| Live headset/board | Current participant's EEG processed into selection | `LIVE EEG` |
| Recorded EEG | Classifier processes real previously recorded EEG into replayed actions | `RECORDED EEG REPLAY` |
| Synthetic signal | Development/validation of signal-processing and interaction pipeline | `SYNTHETIC EEG — NO LIVE BRAIN INPUT` |

Eligibility is not a guarantee of competitiveness. A polished, measured replay/simulation experiment is more credible than an unreliable live demonstration or mislabelled fake control. Live EEG remains the preferred extension if it passes the gates below.

## 2. Fixed integration boundary

```text
device / recorded samples / synthetic samples
                  ↓
        acquisition adapter + quality checks
                  ↓
          calibrated two-choice decoder
                  ↓
           generic SelectionIntent
                  ↓
        core context/action validation
                  ↓
       selected planet → sourced PlanetInfo panel
```

The separate mission backend → XIAO → FPGA path remains unchanged. EEG dispatch into that path is deferred.

The brain module never opens the FPGA/XIAO COM port, computes trajectories, changes mission ticks, edits fuel values or sends wire commands. The core owns all execution. EEG can request the same allowed actions as mouse/keyboard; it cannot grant itself new ones.

Read main-file sections 7, 11–15 before coding. Agent 1 owns the actual shared JSON schemas. This file describes the extension's use of them, not a competing schema. If a change is necessary, update the canonical contract and both plans together.

Run acquisition/decoder in a separate Python 3.11 x64 environment/process on the laptop. Choose one working device path, not every SDK. Core startup must work without the brain environment installed. A separate process also isolates device crashes and Bluetooth driver problems from mission execution.

## 3. Device compatibility and decision tree

### A. g.tec Unicorn Hybrid Black — preferred when supplied working

The event guide names Hybrid Black: 8 EEG channels, 250 samples/s, Bluetooth. Obtain the exact serial number, supplied Bluetooth dongle, charged headset, fitted electrodes and a working vendor signal-quality demonstration from the booth. Every teammate handling it signs the equipment waiver. Borrowed equipment is shared and returned before leaving. [B1, B2]

Use the sponsor's already-working interface first. If none is established, try BrainFlow's documented Windows Unicorn adapter (`BoardIds.UNICORN_BOARD`), selecting the exact device serial number. Confirm pairing and acquire actual samples before developing the decoder. BrainFlow returns auxiliary rows as well as EEG; ask its board metadata for EEG channel indices and sample rate. Do not treat every matrix row as a scalp signal. [B3]

Alternative: vendor LSL or UDP output already demonstrated at the booth. For LSL, identify the exact source ID, channel metadata, units and sampling rate, not simply the first stream named EEG. Do not build a Bluetooth protocol from scratch. Do not assume a paid Python license is available or required; verify the event installation and usable API. [B2]

### B. Unicorn BCI Core-8/Core-4 — different hardware family

If the booth provides a Core device, do not use the Hybrid Black driver by assumption. Start with the vendor's matching g.Pype/g.NEEDaccess example or a working vendor LSL outlet. Confirm OS, Python and runtime licensing before using it. Current g.Pype platform documentation includes Windows x64; do not move it onto Raspberry Pi ARM Linux without explicit support. [B4]

Keep the same normalized acquisition/intent interfaces. Switching the hardware adapter must not change the mission app.

### C. PiEEG Octopus 16 — supported alternative

This is a compact wireless 16-channel sensor using a **XIAO ESP32-S3**, not the PiEEG Raspberry Pi HAT. No Raspberry Pi is required. It uses BLE; its closely spaced pins do not equal sixteen widely separated scalp locations. Nominal rate is about 250 samples/s; some firmware/oscillator combinations run at approximately 244.14. Measure the actual stream and use the correct rate for decoding. [B1, B5]

Bring/check: Octopus sensor, correctly seated XIAO, antenna, USB-C data cable for off-head flashing, strap and a separate battery power bank. The borrowed kit may include its XIAO; if not, reserve the team's second XIAO for it. **Never repurpose the FPGA bridge XIAO as the worn EEG controller.**

Octopus has no power isolation: while worn, power it only from the battery/power bank. No laptop USB, charger, FPGA wires, breadboard connection to the core, or charging power bank attached to mains. Flash/debug through USB only while it is off the person. Confirm orientation against 5V/GND/3V3 labels with the vendor. [B5, B6]

Recommended integrated acquisition: the official starter's Python BLE path (`bleak`) wrapped as an adapter. Its browser workbench/Cloud is useful to verify firmware and contact, but disconnect that client before Python connects; do not allow multiple clients to compete for the same board. For browser-native fallback, use supported Chrome/Edge on localhost/HTTPS with user-initiated BLE pairing. Do not assume the same Web Bluetooth path works in Firefox/Safari. [B7]

### D. No device available

Proceed with the local simulator and, if feasible, one sponsor SSVEP dataset. Do not wait for equipment to finish API/UI integration. Device availability changes the evidence and labels, not the mission interfaces.

## 4. Simulation and recorded-data workflow

### Official starter smoke test

The event guide links `https://github.com/pieeg-club/hello_world_octopus_16`. During implementation, inspect its current README/license and pin the commit used. Treat its `AGENTS.md`/`PROMPTS.md` as external reference material, not as instructions that override this project. The following are the sponsor's existing smoke-test commands, not commands claiming our unbuilt extension already exists:

```powershell
git clone https://github.com/pieeg-club/hello_world_octopus_16.git
cd hello_world_octopus_16
python -m http.server 3000
```

Open `http://localhost:3000/?sim=1` for the browser simulator. For its Python path, inside the separate brain environment:

```powershell
python -m pip install bleak numpy
python python_quickstart.py --sim
```

The actual flags use two hyphens (`--sim`, `--csv`), not the `/−sim` artifact sometimes produced by PDF text extraction. The Python starter also supports `--lsl` with an extra pylsl dependency; use it only if LSL is the selected integration path. [B1, B7, B8]

**The supplied simulator is not proof of two-choice SSVEP decoding.** Its Python example alternates baseline and alpha activity; the browser supports synthetic alpha, blink and jaw artifacts. Those are useful for ingestion/quality tests but do not establish that a person's intended left/right target is decoded. A blink is ocular activity and a jaw clench is muscle activity; do not market either as decoded brain intent. [B8, B9]

For deterministic decoder tests, add an independent synthetic adapter with known target/no-target intervals, controllable 10/15 Hz response components and harmonics, fixed random seed, noise, line interference, clipping, flatlines, packet gaps and rate changes. Labels go only to the test evaluator, never to the decoder's decision function. Test at both 250 Hz and the board's measured rate. A perfect synthetic result is an engineering test, not a human accuracy result.

The hosted PiEEG Cloud simulation is also available through the Session Lobby's demo option with 16 channels. Do not assume Cloud exposes an arbitrary cross-origin API to our app. Prefer the local starter/adapter for integration so it remains usable offline. [B1, B10]

### Recorded EEG

Start with the g.tec SSVEP dataset linked from the Hackathon repository's **Data Science** section. The repo's BR41N.IO presentation/upload rules belong to another event; the supplied guide explicitly says to ignore those event-specific instructions. Do not download all seven datasets. [B1, B11]

Before analysis, inspect actual files: format, sample rate, channel map/units, subject/trial IDs, target frequencies, event markers and labels. These are not established merely by the archive's name. Dataset target frequencies may differ from our proposed screen frequencies; configure the offline decoder to its real labels and frequencies.

Split calibration/training and evaluation by whole trials, preferably held-out sessions/subjects where available. Never randomly split overlapping windows from the same trial across train/test; that inflates results. Preserve source timestamps/order and replay samples through the same acquisition/decoder boundary. Do not read the ground-truth label and emit it directly as the predicted command.

Sponsor datasets are for Hack The Nest projects and the guide says not to repost them. Keep raw archives/recordings out of public Git and submissions; provide a source link, import instructions and permitted derived metrics. Retain local hashes and trial-selection notes for reproducibility. [B1]

## 5. Normalized acquisition interface

Implement adapters behind one Python interface:

```text
start(config) -> DeviceInfo
read_batch()  -> SampleBatch
stop()       -> releases resources even after failure
```

`DeviceInfo` fields: adapter name/version, exact device model/identifier, source mode (`live_eeg`, `replay`, `synthetic`), nominal/effective sampling rate, EEG channel names and locations when known, sample units, firmware/runtime versions, clock source and available device counters. Log configuration without exposing identifying participant information.

`SampleBatch` fields: monotonically increasing batch ID, channel-major numeric EEG array, per-sample relative times or counter-derived sample indices, source-clock anchor, effective sample rate, validity/gap flags, receive monotonic time and source mode. Use float64 microvolts in the normalized decoder interface; perform raw-count conversion once in the adapter using the verified device gain/reference. Do not double-scale BrainFlow or vendor data already in microvolts.

BLE notification arrival times are not evenly spaced sample times. Derive a uniform sample timeline from verified device sample counts/rate; track receive time separately for freshness. Do not hide lost samples by compressing time. A discontinuity invalidates the current decision window and resets necessary filter/window state. If the firmware lacks enough timing metadata, state that limitation and use conservative window gating.

Use a bounded ring buffer (e.g. 10 seconds), bounded event queues, explicit cancellation and `try/finally` cleanup. Decoder work must not block acquisition. Stop on device disconnect; never silently swap a failed live source for synthetic while retaining the LIVE label.

Quality checks: finite values, expected channel count, sample continuity, contact/flatline heuristics, clipping, unusual amplitude and large motion/artifact bursts. Set thresholds using that device and participant, not one copied universal microvolt cutoff. The starter's RMS “good pin” display is a heuristic, not proof of valid intent. Invalid data yields **no selection**.

## 6. Choose one decoding paradigm

Use a working sponsor-provided P300 selector if the booth can already demonstrate reliable labels and explain its event timing. Adapt its outputs without pretending to have implemented its classifier. Otherwise build a modest two-target SSVEP prototype. Do not build both P300 and SSVEP, motor imagery or an “attention throttle” during this deadline.

SSVEP means matching EEG responses to periodic visual targets; it requires looking at a stimulus. It is not a reading of arbitrary thoughts and is not suitable for every user. [B12]

### Proposed SSVEP baseline

These are starting parameters, not verified performance claims:

| Setting | Starting choice |
|---|---|
| Targets | Earth and Mars initially; two choices per screen |
| Stimuli | Nominal 10 Hz and 15 Hz on a measured 60/120 Hz monitor |
| Channels | Verified usable posterior channels; select from actual device metadata/placement |
| Analysis window | 2.0 seconds, update every 250 ms |
| Settling after context/stimulus change | 500 ms, then collect an entirely new full window |
| Filter | Stateful bandpass roughly 6–40 Hz; documented design/sample rate |
| Reference signals | Sine/cosine at actual target frequency and second harmonic |
| Method | Canonical correlation analysis (CCA), with rank/conditioning checks |
| Decision | Winner score + margin + quality + stability + armed selection period |

Implement CCA with a tested library or a clear NumPy/SciPy QR/SVD formulation: demean time-by-channel EEG `X`; form sinusoidal reference matrix `Y` for each target; compute rank-aware orthonormal bases; largest singular value of `Qx.T @ Qy` gives the score. Reject empty/flat/rank-deficient unusable windows rather than generating NaNs or arbitrary winners. Unit-test against known synthetic signals and a reference implementation. The coefficient is **not a probability of intended action**.

Apply exactly the same preprocessing in calibration and live operation. Stateful causal filters need startup/reset warmup; discard transient samples. Do not evaluate future samples in a “live” filter or interpolate across dropouts to manufacture evidence. Additional 60 Hz notch filtering is optional and only if the selected passband/data justify it.

Choose the best target only when its score and separation from the runner-up pass calibrated thresholds. An argmax always picks something, even pure noise; it is not a no-control detector. Require stable evidence over several updates, but do not count overlapping windows as statistically independent confirmations. Emit once per context, then lock out until context revision changes and fresh data have been collected.

For first live operation, use explicitly cued short selection periods rather than always-on control. If no-control tests fail, keep that restriction and describe it. Do not loosen thresholds merely to force a live demo to produce a selection.

## 7. Stimulus timing, browser performance and participation

Use `requestAnimationFrame`, not `setInterval`, for frame-driven stimuli. For a true 60 Hz display, six frames per full cycle gives 10 Hz and four gives 15 Hz; at 120 Hz use twelve/eight. Measure actual frame timing (e.g. 59.94 Hz) and use the effective frequency in references. Count **full cycles**, not transitions, to avoid a factor-of-two error.

Use two small, fixed targets rather than flickering entire planets/scene. While selecting, freeze or reduce expensive 3D rendering so it cannot disrupt stimulus cadence. The FPGA and backend continue independently.

Stop stimuli and disarm decisions on hidden tab, focus loss, display mode/refresh changes, stale browser heartbeat or excessive dropped frames. Proposed engineering gate: no frame gaps >50 ms and <1% missed frames in the current selection interval, measured on the actual monitor. This is a timing gate, not a medical safety certification.

For frequency-only CCA, relative phase can be handled by sine/cosine references and a settling period; do not claim submillisecond synchronization from browser/USB clocks. P300 requires tightly controlled stimulus markers and a validated timing pipeline, so use the sponsor's established implementation rather than improvising it.

Flashing is opt-in and off by default. Use sponsor-supervised participation, a clear immediate stop control, and no spectator-facing flashing display. Do not use it for a participant with a known photosensitivity concern; stop on discomfort. A flashing interface is not universally accessible, and a nominal frequency alone does not establish compliance with flash-safety guidance. Keep a nonflashing mouse/keyboard mode always available. [B13]

## 8. Shared core input protocol

Canonical definitions live in `contracts/` and main-file section 11. Use schema version 1. Do not implement alternative target names or route directly to `/missions/.../commands` with the extension token.

### Session lifecycle

1. Operator explicitly enables the extension and chooses `live_eeg`, `replay` or `synthetic`.
2. `POST /api/v1/input/sessions` registers its adapter/device/source configuration and returns `input_session_id` plus a token scoped to input-context/intent/heartbeat operations.
3. Read `GET /api/v1/input/context` and subscribe to the session-scoped `WS /api/v1/events` stream.
4. Every 500 ms, post `/api/v1/input/sessions/{id}/heartbeat` with `{context_id, context_revision, source_state, acquisition_age_ms, stimulus_ready}`. The response contains the current authoritative context and expiry. A missed heartbeat for >2 seconds disables that source.
5. Send one `POST /api/v1/input/intents` for a valid decision. Await acceptance/rejection; do not retry with a new event ID merely because the HTTP response is delayed. An exact retry uses the same event ID and returns the same result.
6. On disconnect, context mismatch, stale acquisition or stop, disarm immediately and clear pending evidence. Reconnect obtains a fresh context before any decision.
7. `DELETE /api/v1/input/sessions/{id}` releases the source. Mission execution continues independently.

Context expiry is 10 seconds, renewable while the same selection period remains valid. Renewal does not change its revision; semantic context changes do. Source timestamps belong to the source clock, not a shared browser/backend clock. Core receipt age, heartbeat age and context revision determine freshness; preserve source timestamps for debugging without subtracting unrelated clocks.

### Intent example

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

Core acknowledgment: `{event_id, accepted, reason, new_context_revision}`. Rejection reasons include stale context, expired context, duplicate/conflicting event, inactive source, invalid target, unavailable action, invalid quality and source-mode restrictions. Agent 1 freezes exact enums in the shared schema before implementing both clients.

### Context and confirmation behavior

Current stable targets, registered by the core only when their actions are available. The input session capability is `planet_explore`:

| Screen | Targets |
|---|---|
| Planet choice | `planet.399`, `planet.499` |
| Selected-planet information | `planet.more_details`, `navigation.back` |

On acceptance, the core emits the selected body/context revision immediately. The browser highlights that planet and loads its card through `GET /api/v1/planets/{body_id}/info`; ordinary selection and EEG take exactly this path. Render loading/error/partial/cached states. Ignore out-of-order responses for an older body/context. Do not block EEG acceptance waiting for an external API fetch or display a fabricated “healthy” condition when data is missing.

Future-only target design (DO NOT enable or implement mission dispatch for EEG in this round):

| Screen | Targets |
|---|---|
| Route choice | `route.least_fuel`, `route.earliest_arrival` |
| Selected-route review | `plan.request_upload`, `navigation.back` |
| Upload confirmation | `confirmation.confirm`, `confirmation.cancel` |
| Armed mission | `mission.request_start`, `navigation.back` |
| Start confirmation | `confirmation.confirm`, `confirmation.cancel` |
| Executing mission | `view.status`, `view.faults` |

If the later mission-input phase is authorized, the core would perform upload/commit/arm sequentially and expose the start screen only after matching hardware acknowledgments. A slow upload would produce a disabled/waiting context, not a fake ready state. A route change would invalidate pending confirmation. None of this is required to pass the planet-explorer milestone.

On new context, stop stimulus, clear accumulated candidate/decision evidence, wait for settling, and collect a complete new window. The window that selected “start” cannot also confirm it. Persisting gaze must not trigger a chain of actions across screens. A mouse action also increments the context revision and cancels stale EEG proposals.

Implement `WAIT_RELEASE → ARMED → DECISION_SENT` explicitly. On a consequential confirmation screen, require at least one second of calibrated no-control evidence while the participant looks at a neutral fixation point; use the same active-stimulus quality checks during that release measurement. Then rearm with fresh samples, placing confirm opposite the previously chosen target and cancel in the previous position. Merely waiting through a blank screen is not evidence that gaze was released. If no-control cannot be measured reliably, require operator rearm and describe the flow as assisted. The core accepts at most one intent per revision.

For future mission actions, two-stage EEG confirmation would reduce accidental chaining but would not be an independent physical safety guarantee. Operator abort/reset remains available through normal controls; emergency stopping never depends on EEG classification. Current EEG scope is read-only planet exploration, not mission dispatch or every setup step.

Synthetic/replay sources may operate the read-only planet explorer regardless of whether a separate FPGA mission is connected; they cannot alter it. Physical-FPGA mutation through synthetic/replay would require a future explicit operator test mode and persistent labels, as described in the core design. The source never changes itself to live. Event eligibility does not justify hiding the source.

## 9. Browser-to-decoder stimulus bridge

Keep raw EEG out of the main mission API. The optional Python process exposes a separate loopback-only endpoint at a configured port (default 8766), authenticated by a short-lived token and restricted to the local app origin. Only the optional widget connects. Do not expose it on the public network.

Affan freezes one extension-local WebSocket schema in `brain/contracts/stimulus_v1.json` between his decoder and widget before Cursor integrates the optional insertion point. Messages:

- `configure`: schema version, input session, context ID/revision, two allowed target IDs, measured refresh and assigned stimulus frequencies.
- `stimulus_state`: sequence, context ID/revision, active/visible/focused flags, cumulative frame count, dropped-frame count, largest frame gap, measured effective frequencies. Send at least every 250 ms while active.
- `stop`: immediate disarm for this context.
- Decoder → widget `status`: acquiring/calibrating/ready/no-control/invalid-data, quality reason, source mode and scores; scores alone must not animate a committed action.
- Decoder → widget `decision_result`: event ID and the actual core acknowledgment; a local classifier guess is not an accepted command.

Do not compare browser `performance.now()` with Python monotonic time directly. Python uses its own receive time for the stimulus heartbeat and requires a full new sample window after the received start/settling boundary. At >500 ms without valid stimulus-state updates, disarm. A context mismatch clears the buffer even if frames are still arriving.

Core and extension-local session tokens are separate. Do not put permanent secrets in frontend source. The operator launch flow supplies transient local tokens. If this bridge is unavailable, render a disabled brain widget while the normal app remains operational.

## 10. Calibration and evaluation

Record device, effective sample rate, EEG channels, montage/placement, monitor refresh, actual target frequencies, preprocessing, window size and thresholds with each calibration. Switching devices, participants, electrode placement or screen refresh invalidates the prior calibration.

Suggested first calibration: 10 randomized cued trials per target, approximately 4–6 seconds of attention per trial with rest intervals, plus at least 60 seconds of no-target/idle data. Use this to choose channels/thresholds. Then freeze settings before the separate test trials. Do not tune on the held-out results and still report them as held out.

Proposed live demo gate after calibration:

- 20 randomized held-out requested selections; at least 18 correct within a proposed 8-second trial timeout.
- Count **all 20** in the denominator. Report wrong selections and no-decisions separately; do not drop failed trials to inflate accuracy.
- Report median and slowest/90th-percentile selection time, actual sample count and trial count.
- At least two minutes of idle/no-control trials with zero accidental consequential actions. If failing, restrict selection to explicit cued periods or do not ship live control.
- Five complete supported planet-choice -> matching information -> back workflows after setup without mouse assistance. Report any assisted rearm/setup steps honestly. Route-to-start workflows are not part of this milestone.

These are small hackathon acceptance tests, not evidence of clinical efficacy or generalization. Recorded-dataset metrics and live-participant metrics must be reported separately. Synthetic success rates must never be labelled human classification accuracy.

Failing the 90-minute hardware-to-repeatable-selection checkpoint means freeze live-device work and finish the replay/synthetic extension. This does not automatically disqualify the project from Mind and Machine, because the guide allows those modes. It does mean the team cannot claim live brain control.

## 11. Agent tasks and handoffs

This is the same current six-agent allocation as the core file, not additional agents. Affan owns the extension because he attended the workshops; the other five work on the core while he is unavailable.

| Agent | Work | Acceptance handoff |
|---|---|---|
| 1 — your Claude: core integration | Input schemas, read-only capability, contexts/heartbeat, deduplication, planet endpoint wiring | Valid planet selection accepted; stale/duplicate/mission-dispatch bypass rejected |
| 2 — Sadat's Claude: NASA/data | PlanetInfo adapter, sourced facts/Horizons/EONET, data fixtures | Correct per-body scope, dates, units and unavailable/error labels |
| 5 — Sadat's Cursor: browser | Ordinary planet selection/card + optional widget insertion point | Same card works without widget or EEG process |
| 6 — Affan's Codex: full BCI extension | `brain/`, `frontend/src/bci/`, acquisition/decoder/stimulus/tests | Canonical planet intents, source labels, correct freshness/stop/reconnect behavior |
| 3/4 — Zain's Claude / your Codex | No EEG-specific FPGA/transport changes required | Hardware contracts remain unchanged |

Affan owns `brain/contracts/`; Your Claude owns shared core `contracts/`. Cursor reserves `frontend/src/bci/` for Affan and agrees its insertion boundary. Neither agent edits the other's subtree without a handoff. Shared schema changes go through your Claude; the entire task can begin against synthetic/mocked fixtures before hardware is available.

First handoff: no hardware required. Use synthetic samples → decoder → valid planet intent → mock/core API → matching highlighted planet and information card. Demonstrate 10 repeatable synthetic selections plus duplicate/stale rejection. Next replace only the acquisition adapter with replay or hardware. This read-only integration makes no FPGA firmware changes and can be validated before the hardware mission is complete.

No agent may claim a live test based only on a generated log, simulator, vendor screenshot or prerecorded trial. One human owns headset setup, consent/participation and observed test evidence.

## 12. Required tests and release gate

### Acquisition and decoder

- Synthetic target A/B/no-target cases and corrupted input: decoder follows samples, not hidden labels.
- Distinct configured nominal/measured sampling rates produce correct frequency references.
- Missing samples, disconnect, flatline, clipping and stale data produce no new intent.
- Unit scaling tested with known adapter values; non-EEG channels excluded.
- Device change forces recalibration and visibly changes metadata/source status.
- Recorded evaluation uses disjoint trials and logs no-decision outcomes.

### Interaction and integration

- Same event ID retried applies once; same ID with changed content rejects.
- Previous-screen evidence cannot select or confirm on a new screen.
- Hidden tab, focus loss, frame stalls and stimulus heartbeat loss stop decisions.
- EEG process failure does not stop FPGA time or crash normal app startup.
- Late EEG intent after mouse action or backend reconnect rejects as stale.
- Selecting a planet for information does not change mission destination, start a planner job or send an FPGA command.
- Extension token cannot call hardware command endpoints.
- Live device loss never silently becomes synthetic data.
- Synthetic/replay read-only selection stays visibly labelled and cannot mutate any connected FPGA mission.
- Planet-selection behavior is identical whether the independent core transport is simulator, FPGA or disconnected; no EEG serial backdoor.

### Release evidence

Produce `brain/README.md`, `requirements-brain.lock.txt`, adapter configuration examples, calibration/evaluation script, anonymized aggregate results, source/rights notes and a short observed demo recording. Raw EEG recordings are opt-in, local by default, and never committed automatically. Use synthetic fixtures in the public tests.

Core README includes a single explicit feature flag, e.g. `BRAIN_ENABLED=false` by default. Startup scripts exist and are tested; document exact hardware acquisition steps separately from synthetic quickstart. A new teammate must be able to run the synthetic demonstration without a borrowed headset or a sponsor login.

## 13. Final demonstration and submission framing

Live example: “The headset measures EEG. We compare the response to Earth and Mars visual targets; selecting one opens its sourced information in Interstellar. The FPGA mission system is independent.” Show signal → accepted planet selection → matching data card, with dates and source labels visible.

Recorded example: “This is recorded EEG replayed through our decoder. The resulting selections open planetary information in Interstellar. This is not current-user mind control.” Include held-out metrics and limits.

Synthetic example: “This simulator lets us test the brain-interface pipeline and failure handling without a headset. The signal is generated; it is not a live person's EEG.” Demonstrate a useful quality/stale-context failure case as well as the happy path.

Do not claim NASA endorsement, medical efficacy, mental-state diagnosis, unrestricted thought reading, radiation-hardening or quantum benefit. The extension adds a tested input path; it does not make the orbital model more accurate.

Event obligations: team members handling g.tec equipment sign its waiver; borrowed equipment returns before departure. Teams using g.tec hardware submit to the organizer-provided g.tec destination by November 30, in addition to the normal Devpost submission. Do not use the unrelated BR41N.IO upload deadline from the shared resource repo. Preserve the hacker packet's three-minute video limit and normal submission deadlines. [B1, B14]

## 14. Sources and remaining uncertainties

Reviewed 2026-11-14. The event PDFs were text-extracted and relevant pages visually checked. Device/software support was checked against primary vendor/project sources. No headset connection, participant calibration or human accuracy test has been performed for this plan.

- **B1 — Event BCI guide:** `C:/Users/Naceri/Downloads/Hack_The_Nest_2026_Mind_and_Machine_Guide.pdf`, pages 1–6. This resolves the simulation/no-headset participation question.
- **B2 — g.tec device/interfaces:** https://www.gtec.at/product/unicorn-hybrid-black-bci-platform/ ; https://www.gtec.at/2026/11/03/raw-eeg-data-access-with-g-tec-real-time-streams-apis-and-file-formats-in-one-place/
- **B3 — BrainFlow Unicorn support:** https://brainflow.readthedocs.io/en/stable/SupportedBoards.html#unicorn
- **B4 — g.Pype platforms/licensing:** https://gpype.gtec.at/content/1_basic_concepts/supported_devices.html ; https://gpype.gtec.at/content/5_faq/index.html
- **B5 — Octopus hardware:** https://docs.pieeg.com/hardware/devices/Octopus_16/specification/ ; https://docs.pieeg.com/hardware/devices/Octopus_16/software/
- **B6 — Octopus safety:** https://docs.pieeg.com/hardware/devices/Octopus_16/safety/
- **B7 — Sponsor starter:** https://github.com/pieeg-club/hello_world_octopus_16
- **B8 — Actual Python starter and flags:** https://raw.githubusercontent.com/pieeg-club/hello_world_octopus_16/main/python_quickstart.py
- **B9 — Actual browser SDK/source:** https://raw.githubusercontent.com/pieeg-club/hello_world_octopus_16/main/pieeg.js
- **B10 — Cloud simulation:** https://docs.pieeg.com/cloud/
- **B11 — g.tec data/tools:** https://github.com/unicorn-bi/Hackathon (Data Science section; do not adopt the other event's submission instructions).
- **B12 — CCA/no-control research:** https://pubmed.ncbi.nlm.nih.gov/19494422/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC11026332/
- **B13 — Flashing guidance:** https://www.w3.org/WAI/WCAG21/Understanding/three-flashes
- **B14 — Event packet:** `C:/Users/Naceri/Downloads/Hack The Nest 2026 Hacker Packet.pdf`, pages 9, 21 and 23.
- **B15 — Planet/data scope:** https://ssd-api.jpl.nasa.gov/doc/horizons.html ; https://eonet.gsfc.nasa.gov/docs/v3 ; https://science.nasa.gov/mars/facts/ ; https://science.nasa.gov/mission/insight/ .

Remaining real-world gates: exact borrowed model and availability, working vendor runtime, electrode contact, monitor timing, live selection reliability, dependency lock on the actual machine, and final organizer updates. These require observation; no written plan can certify them in advance.
