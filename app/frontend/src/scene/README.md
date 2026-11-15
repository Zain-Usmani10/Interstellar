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
cached at 512x256. The 60 fps at 1080p demo-laptop target still needs measurement
on the final integrated build; it is not a verified performance claim.

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
