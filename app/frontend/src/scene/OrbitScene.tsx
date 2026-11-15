import { Component, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import { AdditiveBlending } from "three";
import type { PlanetTargetId } from "../api/types";
import { BlackHole } from "./BlackHole";
import { PlanetMesh } from "./PlanetMesh";
import { CameraRig } from "./CameraRig";
import { ScenePerformance } from "./ScenePerformance";
import { Spacecraft } from "./Spacecraft";
import { PlanetSurfaceView } from "./surface";
import { countdownProgress, dockedShuttles, estimatePosition, MOCK_FLEET } from "./dockState";
import { VISUAL_PLANETS, planetPosition } from "./planets";
import { flightView, routePoints, splitRouteAtCraft } from "./flightState";
import { Starfield } from "./Starfield";
import { sunGlow } from "./surfaces";
import { loadTexture } from "./textureMaps";
import type {
  SceneBodyId,
  ScenePlan,
  SceneSnapshot,
  SceneShuttle,
  ScenePlanetPosition,
  Vec3,
} from "./types";
import { kmToScene } from "./axes";
import { finiteVector } from "./flightState";
import { positionQuery } from "./planetPositions";
import { usePlanetPositions } from "./usePlanetPositions";
import "./scene.css";

export type { ScenePlan, SceneSnapshot } from "./types";

export type OrbitSceneProps = {
  selectedId: PlanetTargetId | null;
  selectionEnabled?: boolean;
  onSelect: (target: PlanetTargetId) => void;
  onFocusName?: (name: string) => void;
  focusName?: string | null;
  /** Force whole-system camera (Overview). */
  overview?: boolean;
  /** Compact inset: fewer stars, lower dpr, no HUD chrome. */
  compact?: boolean;
  plan?: ScenePlan | null;
  snapshot?: SceneSnapshot | null;
  fleet?: SceneShuttle[];
  mockFleet?: boolean;
  planetPositions?: ScenePlanetPosition[];
  dateUtc?: string | null;
  fetchPositions?: boolean;
};

const BLACK_HOLE_POS: Vec3 = [Math.cos(5.1) * 92, 0, -Math.sin(5.1) * 92];

function Sun({ showLabel }: { showLabel: boolean }) {
  const map = useMemo(() => loadTexture("/textures/2k_sun.jpg"), []);
  return (
    <group>
      <mesh>
        <sphereGeometry args={[1.35, 64, 48]} />
        <meshBasicMaterial map={map} color="#fff0c8" />
      </mesh>
      <sprite scale={[18, 18, 1]}>
        <spriteMaterial
          map={sunGlow()}
          blending={AdditiveBlending}
          depthWrite={false}
          opacity={0.95}
        />
      </sprite>
      <sprite scale={[34, 34, 1]}>
        <spriteMaterial
          map={sunGlow()}
          blending={AdditiveBlending}
          depthWrite={false}
          opacity={0.35}
        />
      </sprite>
      <pointLight color="#ffe1b3" intensity={110} decay={2} />
      {showLabel ? (
        <Html
          position={[0, 2.6, 0]}
          center
          sprite
          distanceFactor={28}
          style={{ pointerEvents: "none" }}
        >
          <span
            style={{
              color: "#f0e0b8",
              font: "600 11px/1 Avenir Next, Segoe UI, sans-serif",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              textShadow: "0 2px 12px rgba(0,0,0,0.85)",
            }}
          >
            Sun
          </span>
        </Html>
      ) : null}
    </group>
  );
}

class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="scene-fallback">
        3D view unavailable. Planet buttons and information cards remain
        available.
      </div>
    ) : (
      this.props.children
    );
  }
}

export function OrbitScene({
  selectedId,
  selectionEnabled: _selectionEnabled = true,
  onSelect,
  onFocusName,
  focusName = null,
  overview = false,
  compact = false,
  plan,
  snapshot,
  fleet = [],
  mockFleet = false,
  planetPositions,
  dateUtc,
  fetchPositions = true,
}: OrbitSceneProps) {
  const [visible, setVisible] = useState(() => !document.hidden);
  const [surfaceApproach, setSurfaceApproach] = useState(0);
  const [performanceReport, setPerformanceReport] = useState(
    "Development frame probe: 5s warmup + 15s sample.",
  );
  const performanceEnabled =
    import.meta.env.DEV &&
    new URLSearchParams(location.search).has("scenePerf");
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  const view = flightView(snapshot, plan);
  const query = fetchPositions && !planetPositions ? positionQuery(dateUtc, plan, snapshot) : null;
  const datedPositions = usePlanetPositions(query);
  const positions = planetPositions ?? datedPositions?.data?.planets;
  const ghost = estimatePosition(snapshot, plan);
  const launchProgress = countdownProgress(snapshot, plan);
  const ships = mockFleet ? MOCK_FLEET : fleet;
  const points = useMemo(() => routePoints(plan), [plan]);
  const craftKey =
    view.departed && view.position ? view.position.join(",") : "";
  const { flown, remaining } = useMemo(
    () =>
      splitRouteAtCraft(
        points,
        view.departed && view.position ? view.position : null,
      ),
    // craftKey tracks confirmed r_km without new-array identity churn
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [points, craftKey, view.departed],
  );
  const blackout = Boolean(snapshot?.link?.blackout);
  const planets = VISUAL_PLANETS.map((body) => ({
    body,
    position: positions?.find(p => p.body_id === body.bodyId && finiteVector(p.r_km))
      ? kmToScene(positions.find(p => p.body_id === body.bodyId)!.r_km)
      : planetPosition(
      body,
      plan,
      view.mode === "unavailable" ? null : snapshot,
    ),
  }));
  const selected = planets.find((p) => p.body.target === selectedId);
  const focused = focusName
    ? planets.find((p) => p.body.name === focusName)
    : null;
  const origin = planets.find(
    (p) => p.body.bodyId === (plan?.origin_body_id ?? "399"),
  ) ?? planets.find((p) => p.body.bodyId === "399")!;

  const captured = view.mode === "captured";
  const sceneSnapshot = view.mode === "unavailable" ? null : snapshot;
  const destination = planets.find(p => p.body.bodyId === plan?.destination_body_id);
  const followCraft = Boolean(
    !overview && view.departed && view.position && !captured,
  );
  // Visit camera always follows the focused body (A1). Never force Earth/origin
  // just because a snapshot exists — that made outer-planet bar clicks open Earth.
  const visitTarget =
    overview
      ? null
      : focusName === "Black Hole"
      ? { position: BLACK_HOLE_POS, body: { radius: 1.2 } }
      : (focused ?? selected);
  const surfaceVisit = Boolean(
    !overview &&
      !followCraft &&
      !compact &&
      visitTarget &&
      focusName !== "Black Hole" &&
      (focused ?? selected)?.body.bodyId,
  );
  const cameraFocus = overview
    ? null
    : followCraft
      ? view.position
      : captured && !focused && !selected
        ? destination?.position ?? view.position
        : ((visitTarget?.position as Vec3 | null) ?? null);
  const transitionKey = `${overview ? "overview" : focusName ?? selectedId ?? "overview"}:${snapshot?.mission_id ?? "preview"}:${view.mode}:${followCraft ? "follow" : surfaceVisit ? "surface" : "visit"}:${positions ? "dated" : "fallback"}`;
  const launchingId =
    snapshot?.shuttle_id &&
    view.mode === "docked" &&
    launchProgress > 0 &&
    !view.departed
      ? snapshot.shuttle_id
      : null;
  const landedId =
    view.mode === "captured" && snapshot?.shuttle_id
      ? snapshot.shuttle_id
      : null;

  return (
    <div
      className={compact ? "orbital-scene compact" : "orbital-scene"}
      aria-label="Three-dimensional solar system"
    >
      {performanceEnabled && !compact ? (
        <pre
          aria-label="Scene frame measurement"
          style={{
            position: "absolute",
            zIndex: 20,
            right: 12,
            top: 12,
            padding: 12,
            pointerEvents: "none",
            background: "#07121cee",
            color: "#bce8dc",
            font: "11px monospace",
          }}
        >
          {performanceReport}
        </pre>
      ) : null}
      <SceneBoundary>
        <Canvas
          camera={{ position: [320, 500, 750], fov: 42, near: 0.03, far: 3000 }}
          dpr={compact ? [1, 1] : [1, 1.25]}
          frameloop={visible ? "always" : "never"}
          gl={{ antialias: !compact, powerPreference: "high-performance" }}
        >
          <color attach="background" args={["#01030c"]} />
          <fog attach="fog" args={["#03061a", 420, 2100]} />
          <ambientLight intensity={0.28} color="#8aa0c0" />
          <hemisphereLight args={["#b8d4ff", "#1a1010", 0.4]} />
          <directionalLight
            position={[40, 25, 10]}
            color="#fff4e0"
            intensity={2.8}
          />
          <Starfield compact={compact} />
          <Sun showLabel={!compact} />
          {performanceEnabled && !compact ? (
            <ScenePerformance onSample={setPerformanceReport} />
          ) : null}
          {planets.map(({ body, position }) => {
            const isFocus =
              !overview &&
              (focusName === body.name ||
                (body.target != null && selectedId === body.target));
            return (
            <group key={body.name}>
              <PlanetMesh
                body={body}
                position={position}
                selected={isFocus}
                interactive={!compact}
                onSelect={onSelect}
                onFocus={() => onFocusName?.(body.name)}
                showLabel={!compact}
              />
              {body.bodyId ? (
                <group position={position}>
                  <PlanetSurfaceView
                    bodyId={body.bodyId as SceneBodyId}
                    radius={body.radius}
                    shuttles={dockedShuttles(
                      ships,
                      body.bodyId,
                      sceneSnapshot,
                    ).map((ship) => ({
                      id: ship.id,
                      name: ship.name,
                      class: ship.class,
                    }))}
                    approach={
                      isFocus && surfaceVisit ? surfaceApproach : 0
                    }
                    launchingShuttleId={
                      isFocus && body.bodyId === plan?.origin_body_id
                        ? launchingId
                        : null
                    }
                    landedShuttleId={
                      isFocus && body.bodyId === plan?.destination_body_id
                        ? landedId
                        : null
                    }
                    launchProgress={
                      isFocus && body.bodyId === plan?.origin_body_id
                        ? launchProgress
                        : 0
                    }
                    landingProgress={
                      isFocus && body.bodyId === plan?.destination_body_id && landedId
                        ? 1
                        : 1
                    }
                    showLabels={false}
                    renderSurface={false}
                  />
                </group>
              ) : null}
            </group>
            );
          })}
          <BlackHole
            position={BLACK_HOLE_POS}
            selected={!overview && focusName === "Black Hole"}
            onSelect={() => onFocusName?.("Black Hole")}
            showLabel={!compact}
          />
          {/* Part B: solid = flown (confirmed), dotted = still expected. */}
          {flown.length > 1 && (
            <Line
              points={flown}
              color="#8cdece"
              lineWidth={2}
              transparent
              opacity={0.92}
            />
          )}
          {remaining.length > 1 && !blackout && (
            <Line
              points={remaining}
              color="#8cdece"
              lineWidth={1.5}
              transparent
              opacity={0.55}
              dashed
              dashSize={0.28}
              gapSize={0.18}
            />
          )}
          {snapshot && <Spacecraft
            view={view}
            snapshot={snapshot}
            origin={origin.position}
            originRadius={origin.body.radius}
            destination={destination?.position}
            destinationRadius={destination?.body.radius}
            launchProgress={launchProgress}
          />}
          {/* Blackout ghost: own gold dashed remaining (18.7), not the cyan dots. */}
          {ghost && <>
            {remaining.length > 1 ? (
              <Line
                points={remaining}
                color="#e8b875"
                dashed
                dashSize={0.22}
                gapSize={0.15}
                lineWidth={2}
              />
            ) : points.length > 1 ? (
              <Line
                points={points}
                color="#e8b875"
                dashed
                dashSize={0.22}
                gapSize={0.15}
                lineWidth={2}
              />
            ) : null}
            <group position={ghost}>
              <mesh><octahedronGeometry args={[0.24]} /><meshBasicMaterial color="#e8b875" transparent opacity={0.45} wireframe /></mesh>
            </group>
          </>}
          <CameraRig
            focus={cameraFocus}
            focusRadius={
              followCraft
                ? 0.55
                : focusName === "Black Hole"
                  ? 1.4
                  : ((visitTarget as { body?: { radius: number } })?.body
                      ?.radius ?? 1)
            }
            transitionKey={transitionKey}
            extent={Math.max(95, ...planets.map(p => Math.hypot(...p.position) + p.body.radius))}
            follow={followCraft}
            surface={surfaceVisit}
            overviewDistanceScale={1.05}
            onApproach={setSurfaceApproach}
          />
        </Canvas>
      </SceneBoundary>
      <div className="scene-vignette" aria-hidden="true" />
      <div className="scene-nebula" aria-hidden="true" />
      {fetchPositions && !planetPositions && !compact && <div className="scene-position-status" role="status">
        {datedPositions?.data ? `NASA/JPL cached · ${datedPositions.data.date_utc}${snapshot?.link.blackout ? " · estimate" : ""}${datedPositions.error ? " · update unavailable" : datedPositions.pending ? " · updating" : datedPositions.held ? " · date held" : ""}`
          : datedPositions?.error ? "Planet positions unavailable · illustrative overview"
          : query ? "Loading dated planet positions · illustrative overview"
          : "Scene date unavailable · illustrative overview"}
      </div>}
      {mockFleet && !compact && <div style={{ position: "absolute", bottom: 12, left: 12, color: "#efce8e", font: "11px monospace" }}>MOCK FLEET · PREVIEW</div>}
    </div>
  );
}
