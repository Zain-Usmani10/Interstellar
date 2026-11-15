# Solar system scene

`OrbitScene` retains the existing selection props and adds optional `plan` and
`snapshot` views defined in `types.ts`. The parent owns API calls, freshness/order
gates and selection state. The scene calls `onSelect` only for Earth and Mars.

Earth/Mars and the nominal route use supplied kilometres, mapped once to x,z,-y
at 10 units per AU. Other planets are illustrative; their distances are compressed
to fit the overview. Marker sizes, station and rocket are deliberately enlarged.
The legend states these limitations. No orbital propagation runs in the browser.

Departure requires executed bit 0. Capture requires bit 1, captured phase,
COMPLETE state and captured outcome. SAFE/ABORTED retain the reported position
and show uncaptured coast. Unknown or mismatched telemetry hides the spacecraft.
Disconnected positions are marked stale and never extrapolated. Position easing
lasts 180 ms between received points. A short exhaust effect runs only when a
departure transition is observed, not when opening an already-running mission.
The captured rocket has an illustrative local offset so the enlarged planet
does not hide it; its parent anchor remains at the reported position.

Textures and meshes are original procedural code. No external models, textures,
reference-repository code or new runtime packages are used. WebGL rendering stops
when `document.hidden` is true. Pixel ratio is capped at 1.5 and textures are
cached at 512x256. An opt-in development probe (`/?scenePerf=1`) measures actual
scene frames after five seconds of warmup, reporting each fifteen-second window.
It is removed from the production build. Resize/visibility changes restart the
sample. The probe does not alter mission timing or state.

On 2026-11-14, the Codex in-app browser at a 1920x1080 viewport measured 127 fps
and a 10.8 ms p95 frame interval (1905 frames / 15 seconds), with the live local
simulator API and the 512-point NASA_CACHED least-fuel route selected. Canvas
size was 1567.2x865.3 CSS pixels, DPR 1, renderer string `WebKit WebGL`. An earlier
synthetic-plan overview window measured 130.4 fps. This is a browser development
run, not a final demo-machine or full-mission performance guarantee.

## Verification

Run `node --test app/frontend/src/scene/flightState.test.mjs` (Node 24), then the
frontend build and lint scripts. With Vite running, open
`/src/scene/preview.html` for a development-only, explicitly labelled fixture
viewer. It is not an application entry point and makes no backend requests.
Check Docked -> Coast -> Captured, SAFE, ABORTED and Stale; selecting Earth/Mars
checks camera fly-in. The fixture viewer intentionally allows contradictory
RUNNING-without-departure data to verify the visual launch gate.

Browser checks on 2026-11-14: backend-down normal selection showed Earth with
station and docked rocket; fixture coast/capture/SAFE/ABORTED/stale labels and
capture camera were verified. These checks are synthetic, not live FPGA or EEG.

Combined locally with mission-controls PR #25 at de94dc1, the live simulator API
also passed Create -> Upload -> Arm -> Start -> COMPLETE/captured (tick 12010,
executed mask 3) through the browser controls. A second mission was aborted after
departure and displayed ABORTED / uncaptured coast with mask 1. These runs used
the synthetic plan, an isolated database and SIM_SPEED=100; they are software
simulator checks, not real hardware. The combined frontend production build passed.
