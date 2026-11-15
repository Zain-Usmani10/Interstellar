# Planet surface geometry (#75)

Mount `PlanetSurfaceView` at the planet centre, with identity rotation, alongside
the existing textured planet. Its pads and station follow the sphere's normals;
they are actual local geometry in the existing canvas, not a screen overlay.
Do not attach dressing to the rotating texture mesh. The caller owns the camera,
the background starfield, the fleet and all flight state.

```tsx
import { PlanetSurfaceView, surfaceCameraPose } from './surface';
const pose = surfaceCameraPose(radius, width / height, 0.16);
// Add the planet centre to pose.position and pose.lookAt. Smoothly move the
// existing camera to those world positions and pose.fov (35 degrees).
// Reverse that same move on Overview/Launch. No second canvas is needed.
<group position={planetCentre}>
  <PlanetSurfaceView bodyId={bodyId} radius={radius} shuttles={dockedFleet}
    approach={zoomApproach} launchingShuttleId={launchingShuttleId}
    launchProgress={confirmedLaunchProgress} />
</group>
```

Props:

- `bodyId`: one of the eight planet-centre IDs; sets the accent.
- `radius`: the existing scene's illustrative planet radius, required.
- `shuttles`: `{id, name, class: 'standard'|'long_range'}[]`, already filtered for this planet. One pad per item, plus an empty landing pad. Keep a departing/arriving shuttle in this list while its local motion is displayed.
- `aspect`: optional viewport width/height override; defaults to canvas size.
- `sagitta`: peak-to-edge horizon rise as a fraction of view height; default 0.16, range 0.08–0.30. Pass the same value to the camera helper.
- `approach`: 0–1, default 1. Dressing scales in over the last 35% of the zoom; no camera mutation occurs here.
- `launchingShuttleId`, `landedShuttleId`: optional IDs selecting local lift-off/touch-down motion.
- `launchProgress`, `landingProgress`: 0–1 from the caller; defaults 0 and 1. No independent flight clock. At launch progress 1 the local shuttle hides; the existing flight spacecraft takes over. Aborts/reconciliation remain the caller's responsibility.
- `showLabels`: false by default. Only when true are provided shuttle names shown.
- `renderSurface`: false by default. Set true only if this component replaces the original sphere (or in the isolated preview). Reuses existing planet textures; gas giants are an illustrative cloud deck, not a physical landing claim.

Camera near clipping should be at most `radius * 0.001`. The helper solves the
perspective silhouette so the peak is at NDC y=-0.25 and both viewport edges
are lower by twice `sagitta`. This is the actual spherical horizon, not flattened
geometry. `surfaceAnchor` exposes the same placement calculation if the flight
code needs a lift-off origin. It returns planet-local surface coordinates.

The station has a scanning dish and beacon. Shuttles have a subtle idle exhaust
shimmer. No external assets/packages added; texture rights remain in the existing
`public/textures` licence record. No selection, route, telemetry or API calls.

Run `npm run dev` from `app/frontend`, then open
`/src/scene/surface/preview.html`. All eight planet buttons, continuous zoom and
a mock lift-off slider are available. This page is development-only.

Checks: `npm run build`, `npm run lint`, and
`node --experimental-strip-types --test src/scene/*.test.mjs src/scene/surface/*.test.mjs`.
Visual evidence and measured performance must be reported separately from these tests.

Review evidence (2026-11-15): `evidence/earth.png`, `mars.png` and `jupiter.png`
capture the isolated mock-fleet preview at 1920x1080; `earth-900.png` captures
900x700. In the visible in-app browser, the preview's rolling frame counter
reported 114–141 fps during these checks (DPR 1). This is a local development
preview observation, not an integrated-app or hardware performance guarantee.
Zoom-out was visually checked to return to the full sphere. Build and lint pass
with existing unrelated warnings; all 20 scene tests pass, including two new
geometry checks. Cursor still needs to mount the component in the main scene
and wire its camera and confirmed flight progress.
