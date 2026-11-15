# Synthetic planet selection — issue #7

**SYNTHETIC EEG — NO LIVE BRAIN INPUT.** Generated two-channel microvolt samples
pass through a causal filter, CCA decoder, quality/freshness gates and the core's
canonical input validation. An accepted intent opens the same planet information
state as ordinary input. No brain module imports serial, calls mission routes,
fetches NASA data or changes a mission destination.

The demonstration bridge is synthetic-only and deliberately has **no flashing
UI**. A separate Octopus 16 acquisition adapter is available for qualification;
it is not enabled in the widget. The widget's frequency selector configures the signal generator,
not a predicted command; the decoder only sees samples. Operator rearm is required
for every new context. Nothing here demonstrates human classification accuracy.

## Setup (separate Python 3.12 environment)

From the repository root, using Python 3.12 explicitly:

```powershell
py -3.12 -m venv .venv-brain
.venv-brain/Scripts/python.exe -m pip install -r app/brain/requirements-brain.lock.txt
.venv-brain/Scripts/python.exe -m pytest app/tests/brain -q
.venv-brain/Scripts/python.exe -m app.brain.evaluate --rate 250
.venv-brain/Scripts/python.exe -m app.brain.evaluate --rate 244.14
```

If the launcher cannot find Python, replace `py -3.12` with the full path to the
installed Python 3.12 executable. Tested here with Windows x64 Python **3.12.10**.
The lock records packages actually installed in this environment, including API
test dependencies. It does not alter the core's dependency lock.

The core integration tests use the leader's contracts/backend, now merged into
`dev` through PRs #9/#10. `BRAIN_REFERENCE_ROOT` may optionally point to a separate
checkout when testing a future core revision. Tests import the real core validators
and API; this module does not provide a competing core implementation. All 28 brain
tests pass against merged dev on Python 3.12.10.

## Quick controller simulator (no headset)

Start the app's backend with `BRAIN_ENABLED=true` and open its normal frontend.
From the repository root, run:

```powershell
.venv-brain/Scripts/python.exe -m app.brain.controller
```

Press **E** for Earth, **M** for Mars, **B** for Back, or **Q** to quit in the
terminal (on non-Windows, press Enter too). A selection takes about four seconds;
switching from an open card takes about eight seconds because Back is decoded
first. These controls generate signals that pass through CCA and the real core
input API. They do not directly set a frontend selection or issue mission commands.
The app receives the normal selection events, so keep its browser open. No widget
token or flashing is needed for this terminal simulator.

For an automatic, finite demo or a single selection:

```powershell
.venv-brain/Scripts/python.exe -m app.brain.controller --demo
.venv-brain/Scripts/python.exe -m app.brain.controller --planet mars
```

`--demo` selects Earth -> Mars -> Earth and exits. All inputs remain labeled
**synthetic**. The terminal tool intentionally has no live-mode switch: bringing
a headset online is the separate qualification step below, not proof that the
synthetic classifier works on a person.

## Run with the app's optional widget

1. Start the core backend in its own environment with `BRAIN_ENABLED=true`.
   Its default remains false. Use the backend runbook; default URL is
   `http://127.0.0.1:8000`.
2. Cursor's frontend PR #12 mounts `BrainWidget` from
   `app/frontend/src/bci/BrainWidget.tsx` in `BciSlot` when built with
   `VITE_BRAIN_ENABLED=true`. Default is disabled. The combined TypeScript/Vite
   build passes with that flag. No new frontend package is needed. Ordinary
   controls work without this component.
3. Start the separate process:

   ```powershell
   .venv-brain/Scripts/python.exe -m app.brain.service --origin http://localhost:5173
   ```

4. Paste its temporary launch token into the widget. It is valid for ten minutes
   for new connections; restart the process for a new token. Only one widget may
   connect. No token is stored in source, URL, browser storage or a committed file.
5. Choose generated 10 Hz or 15 Hz (or noise), then **Arm one selection**. Keep
   the tab visible/focused. Expect roughly four seconds to a valid decision.
   The status shows the actual core acknowledgment. The normal frontend's core
   `selection` event handler must update the planet highlight and load the card.
6. On the information screen, targets are details/back. Explicitly arm again;
   no previous samples carry into the next context. Stop/disconnect is immediate.

`--origin` must match the page origin exactly, including port. For a backend-served
build use `--origin http://127.0.0.1:8000`. The bridge binds only `127.0.0.1:8766`.
Wrong origins/tokens are rejected; messages and queues are bounded. Core session
tokens stay in the Python process and have only `planet_explore` capability.

Widget props: `enabled=false`, `bridgeUrl='ws://127.0.0.1:8766'`,
`onDecision(result)` (actual accepted/rejected core acknowledgment),
`onActiveChange(active)` (owner may reduce expensive rendering). Classifier scores
never commit a UI action. Mounting the reserved slot and normal app event/card
handling remain Cursor-owned; they are not edited by this PR.

## Processing and failure behavior

- Acquisition boundary: `start(config) -> DeviceInfo`, `read_batch() -> SampleBatch`,
  `stop()`. Float64 microvolts, channel-major EEG only, sample-counter timeline,
  receive monotonic timestamp, explicit source and validity. Source labels never
  enter the classifier. Source/device changes require a fresh configuration.
- Synthetic profile: 250 Hz (also tested at 244.14 Hz), 10/15 Hz components and
  second harmonics, fixed seed, noise and 60 Hz interference. Fault fixtures cover
  clipping, nonfinite samples, flatlines and dropped samples.
- Fourth-order Butterworth 6–40 Hz SOS filter, causal state, 500 ms discarded
  filter warmup after the separate 500 ms context settling period. Two-second
  bounded rolling window; updates after at least 250 ms of fresh samples.
- Demeaned SVD bases and largest singular value of `Qx.T @ Qy` give CCA scores.
  Rank-zero EEG/reference degeneracy rejects. Scores are **not probabilities**.
  Synthetic thresholds: score >= .80, margin >= .20, three consistent updates.
  Overlapping windows are stability checks, not independent confirmations.
- `WAIT_RELEASE -> ARMED -> DECISION_SENT`: operator-assisted rearm, once per
  context revision. Exact backend event retry is tested; the service does not
  automatically retry after an uncertain HTTP result or invent a new event ID.
- Input heartbeat every 500 ms; core response is authoritative. Core events,
  changed context, hidden tab, focus loss, frame gaps >35 ms, missing widget
  updates >500 ms, stale acquisition, changed sample rate/source, discontinuity
  or invalid data clear evidence and disarm. Reconnect registers a fresh session.
- Source sample times, browser frame clock and Python receive clock are separate.
  Synthetic UI frame reports are liveness guards, **not measured SSVEP stimuli**.
  Real flashing, refresh measurement and live-device calibration are deferred.

The schema in `contracts/stimulus_v1.json` freezes widget-to-decoder messages.
First frame authenticates with `{token}`. Server `status` carries schema version,
source/label, gate state, reason, optional scores and authoritative core context;
`decision_result` carries schema version, event ID and the unchanged core result.
Neither payload includes raw EEG. Invalid messages cannot enable mission targets.

## Evidence and remaining gates

See `results/` for reproducible synthetic aggregate results. The API test performs
ten alternating decoded planet selections, validates every intent against the
canonical schema, reads each matching PlanetInfo, tests exact retry, conflicting
duplicate and stale-context rejection, and verifies the input token cannot create
a mission. Back navigation in that ten-trial test is explicitly ordinary input.
The bridge test uses a real loopback WebSocket and the core API in-process.

Browser smoke against frontend `481c6ba` passed: generated Earth selection, back,
fresh Mars selection, then brain disconnect and ordinary Close -> Earth selection.
See [browser evidence](results/browser_smoke.md) and its screenshot. This used
synthetic core fixtures and a simulated controller, not the unmerged NASA adapter.
Widget/card layout and unavailable picker targets need frontend polish as recorded.

No headset, replay dataset, live calibration, physical FPGA, measured flashing
monitor or video recording has been validated here. Live/replay adapters should replace only
acquisition after device metadata, timing, units and separately reported held-out
evaluation pass; synthetic thresholds are not a live-device calibration.

## Octopus 16 acquisition qualification

No device is connected for this implementation. The tests use fabricated packets
and a mocked BLE client, not a headset or a participant. This adapter targets
**Octopus 16 BLE**, not arbitrary PiEEG boards.

Install the optional driver in the separate brain environment, then run only
after verifying the device identifier and following the manufacturer's
[wearing and power instructions](https://docs.pieeg.com/hardware/devices/Octopus_16/safety/):

```powershell
.venv-brain/Scripts/python.exe -m pip install -r app/brain/requirements-octopus.txt
.venv-brain/Scripts/python.exe -m app.brain.octopus --scan
.venv-brain/Scripts/python.exe -m app.brain.octopus --address VERIFIED_DEVICE_ID --seconds 30 --rate 250
```

This command uses the same `OctopusAdapter.start/read_batch/stop` implementation
as library callers. It prints aggregate delivery timing only, never raw EEG,
and makes no core calls. The rate argument is a configured sample-clock rate;
BLE delivery timing is not a measurement of the ADC clock. Confirm the effective
rate separately before setting decoder frequencies or reporting performance.

The event's Mind and Machine guide (pages 4–6) identifies Octopus 16 as the
PiEEG BLE board. While worn, power it **only from its power bank**, never a laptop
or wall charger. Follow the vendor setup for firmware and fitting; do not flash
it while worn. Close any PiEEG Cloud connection before the Python test so the
board is available. `--scan` lists candidate names/identifiers without connecting;
verify yours and pass its identifier to `--address`. The g.tec Unicorn mentioned
elsewhere in that guide uses a different interface and is not supported by this
Octopus adapter.

The adapter returns channel-major float64 microvolts, unwrapped sample indices,
monotonic receive timestamps and `source=live_eeg`. `channels` selects zero-based
hardware channels (default 0 and 1); these are **not an assumed O1/O2 montage**.
Use the participant's verified electrode placement when configuring channels.
It assembles roughly 100 ms batches because the decoder needs multiple samples
for quality checks. `read_batch` blocks for at most 500 ms: call it off the
heartbeat/UI event loop. Start/stop must be serialized by the caller.

Malformed packets, ADC rails, skipped/repeated counters, queue overflow, stale
data and disconnects invalidate the run. No automatic reconnect, resampling,
recording or synthetic fallback occurs. Stop and start explicitly after fixing
the source, with a fresh context and calibration. An 8-bit counter cannot prove
that exactly 256 packets were not lost; receive-stall checks reduce that blind
spot but do not certify transport continuity under arbitrary buffering.

Fabricated 10/15 Hz packets exercise the existing `SelectionGate` and produce
the same Earth/Mars `SelectionIntent` shape. This proves software compatibility,
not live classification. The service and widget remain synthetic-only because
their frame reports do not measure actual SSVEP stimuli. Enabling live selection
still requires measured visual stimuli with explicit opt-in, device/rate/montage
and person-specific calibration, then the plan's held-out trial and idle tests.
Route choice and mission commands are outside this extension.

## Sources and rights

Implementation follows the project plans and canonical contracts v1. No sponsor
starter code or dataset was copied/downloaded. Synthetic signals are generated
locally. NumPy/SciPy provide numerical operations/filtering; jsonschema validates
contracts; HTTPX/websockets provide local transports. Retain their distributed
licenses. No raw EEG, participant identifiers or restricted datasets are committed.

Octopus packet constants (51-byte framing, signed 24-bit channels, 250 Hz nominal
rate and ADC conversion) were checked against the vendor's
[Python quickstart](https://github.com/pieeg-club/hello_world_octopus_16/blob/main/python_quickstart.py).
The parser and lifecycle code here are independently implemented; no vendor
source or EEG recordings are bundled. BLE lifecycle uses the documented
[Bleak client API](https://bleak.readthedocs.io/en/latest/api/client.html).
Bleak 3.1.0 installs in the isolated Windows Python 3.12 environment; real BLE
operation remains untested.
