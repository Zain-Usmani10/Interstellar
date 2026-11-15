# Synthetic planet selection — issue #7

**SYNTHETIC EEG — NO LIVE BRAIN INPUT.** Generated two-channel microvolt samples
pass through a causal filter, CCA decoder, quality/freshness gates and the core's
canonical input validation. An accepted intent opens the same planet information
state as ordinary input. No brain module imports serial, calls mission routes,
fetches NASA data or changes a mission destination.

This first milestone has no live or recorded adapter and deliberately has **no
flashing UI**. The widget's frequency selector configures the signal generator,
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

The core integration tests require the leader's contracts/backend from PRs #9/#10.
Until merged, `BRAIN_REFERENCE_ROOT` may point to a separate checkout containing
those `app/contracts` and `app/backend` trees. Tests import the real core validators
and API; this module does not provide a competing core implementation.

## Run with the app

1. Start the core backend in its own environment with `BRAIN_ENABLED=true`.
   Its default remains false. Use the backend runbook; default URL is
   `http://127.0.0.1:8000`.
2. Cursor mounts `BrainWidget` from `app/frontend/src/bci/BrainWidget.tsx` in the
   reserved `BciSlot`, passing `enabled={true}` only when explicitly enabled.
   No new frontend package is needed. Ordinary controls work without this component.
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

No headset, replay dataset, live calibration, physical FPGA, measured flashing
monitor, browser-observed end-to-end demo or recording has been validated here.
The frontend owner must mount the widget and confirm the shared planet-card flow
before marking the full issue integrated. Live/replay adapters should replace only
acquisition after device metadata, timing, units and separately reported held-out
evaluation pass; synthetic thresholds are not a live-device calibration.

## Sources and rights

Implementation follows the project plans and canonical contracts v1. No sponsor
starter code or dataset was copied/downloaded. Synthetic signals are generated
locally. NumPy/SciPy provide numerical operations/filtering; jsonschema validates
contracts; HTTPX/websockets provide local transports. Retain their distributed
licenses. No raw EEG, participant identifiers or restricted datasets are committed.
