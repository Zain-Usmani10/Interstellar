import { Component, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Line, Stars } from "@react-three/drei";
import { AdditiveBlending } from "three";
import type { PlanetTargetId } from "../api/types";
import { BlackHole } from "./BlackHole";
import { PlanetMesh } from "./PlanetMesh";
import { CameraRig } from "./CameraRig";
import { ScenePerformance } from "./ScenePerformance";
import { Spacecraft, Station } from "./Spacecraft";
import { VISUAL_PLANETS, planetPosition } from "./planets";
import { flightView, routePoints, type FlightView } from "./flightState";
import { scenicPath, scenicPosition } from "./scenicFlight";
import { sunGlow } from "./surfaces";
import { loadTexture } from "./textureMaps";
import type { ScenePlan, SceneSnapshot, Vec3 } from "./types";
import "./scene.css";

export type { ScenePlan, SceneSnapshot } from "./types";

export type ScenicTour = {
  destination: string;
  progress: number; // 0..1
};

export type OrbitSceneProps = {
  selectedId: PlanetTargetId | null;
  selectionEnabled?: boolean;
  onSelect: (target: PlanetTargetId) => void;
  onFocusName?: (name: string) => void;
  focusName?: string | null;
  plan?: ScenePlan | null;
  snapshot?: SceneSnapshot | null;
  /** Illustrative Earth→destination flight (not MissionSnapshot). */
  scenic?: ScenicTour | null;
};

const BLACK_HOLE_POS: Vec3 = [Math.cos(5.1) * 92, 0, -Math.sin(5.1) * 92];

function Sun() {
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
    </group>
  );
}

function OrbitGuide({ radius }: { radius: number }) {
  const points = useMemo(
    () =>
      Array.from({ length: 181 }, (_, i) => {
        const angle = (i / 180) * Math.PI * 2;
        return [Math.cos(angle) * radius, 0, Math.sin(angle) * radius] as [
          number,
          number,
          number,
        ];
      }),
    [radius],
  );
  return (
    <Line
      points={points}
      color="#526578"
      lineWidth={0.65}
      transparent
      opacity={0.27}
    />
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
  selectionEnabled = true,
  onSelect,
  onFocusName,
  focusName = null,
  plan,
  snapshot,
  scenic = null,
}: OrbitSceneProps) {
  const [visible, setVisible] = useState(() => !document.hidden);
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

  const telemetryView = flightView(snapshot, plan);
  const points = useMemo(() => routePoints(plan), [plan]);
  const planets = VISUAL_PLANETS.map((body) => ({
    body,
    position: planetPosition(
      body,
      plan,
      telemetryView.mode === "unavailable" ? null : snapshot,
    ),
  }));
  const selected = planets.find((p) => p.body.target === selectedId);
  const focused = focusName
    ? planets.find((p) => p.body.name === focusName) ??
      (focusName === "Black Hole" ? null : null)
    : null;
  const origin = planets.find(
    (p) => p.body.bodyId === (plan?.origin_body_id ?? "399"),
  )!;
  const destinationPlanet = scenic
    ? scenic.destination === "Black Hole"
      ? { position: BLACK_HOLE_POS, body: { name: "Black Hole", radius: 1.2 } }
      : planets.find((p) => p.body.name === scenic.destination)
    : null;

  const scenicPts = useMemo(() => {
    if (!destinationPlanet) return [] as Vec3[];
    return scenicPath(origin.position, destinationPlanet.position);
  }, [
    destinationPlanet?.position[0],
    destinationPlanet?.position[1],
    destinationPlanet?.position[2],
    origin.position[0],
    origin.position[1],
    origin.position[2],
    scenic?.destination,
  ]);

  const scenicView: FlightView | null =
    scenic && scenicPts.length > 1
      ? {
          mode: scenic.progress >= 1 ? "captured" : "coast",
          position: scenicPosition(scenicPts, scenic.progress),
          departed: scenic.progress > 0.02,
          stale: false,
          label:
            scenic.progress >= 1
              ? `ILLUSTRATIVE ARRIVAL · ${scenic.destination}`
              : `ILLUSTRATIVE FLIGHT · ${scenic.destination}`,
        }
      : null;

  // Real MissionSnapshot wins over scenic tour when a live mission has departed.
  const view =
    scenicView && !(telemetryView.departed && snapshot)
      ? scenicView
      : telemetryView;

  const captured = view.mode === "captured";
  const visitTarget =
    focusName === "Black Hole"
      ? { position: BLACK_HOLE_POS, body: { radius: 1.2 } }
      : (focused ?? selected);
  const cameraFocus = captured
    ? view.position
    : !view.departed
      ? ((visitTarget?.position as Vec3 | null) ?? null)
      : view.position;
  const transitionKey = `${focusName ?? selectedId ?? "overview"}:${snapshot?.mission_id ?? "preview"}:${scenic?.destination ?? "none"}:${view.mode}`;

  return (
    <div className="orbital-scene" aria-label="Three-dimensional solar system">
      {performanceEnabled ? (
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
          dpr={[1, 1.5]}
          frameloop={visible ? "always" : "never"}
          gl={{ antialias: true, powerPreference: "high-performance" }}
        >
          <color attach="background" args={["#02050c"]} />
          <fog attach="fog" args={["#02050c", 90, 1400]} />
          <ambientLight intensity={0.22} color="#8aa0c0" />
          <hemisphereLight args={["#b8d4ff", "#1a1010", 0.45]} />
          <directionalLight
            position={[40, 25, 10]}
            color="#fff4e0"
            intensity={3.2}
          />
          <directionalLight
            position={[-30, -10, -20]}
            color="#4060a0"
            intensity={0.55}
          />
          <Stars
            radius={1400}
            depth={700}
            count={4200}
            factor={3.4}
            saturation={0}
            fade
            speed={0}
          />
          <Sun />
          {performanceEnabled ? (
            <ScenePerformance onSample={setPerformanceReport} />
          ) : null}
          {planets.map(({ body, position }) => (
            <group key={body.name}>
              <OrbitGuide radius={body.displayOrbitAU * 10} />
              <PlanetMesh
                body={body}
                position={position}
                selected={
                  selectedId === body.target || focusName === body.name
                }
                interactive={selectionEnabled}
                onSelect={onSelect}
              />
            </group>
          ))}
          <BlackHole
            position={BLACK_HOLE_POS}
            selected={focusName === "Black Hole"}
            onSelect={() => onFocusName?.("Black Hole")}
          />
          {(scenicPts.length > 1 ? scenicPts : points).length > 1 && (
            <Line
              points={scenicPts.length > 1 ? scenicPts : points}
              color={scenicPts.length > 1 ? "#e0b06a" : "#8cdece"}
              lineWidth={1.6}
              transparent
              opacity={0.8}
            />
          )}
          <group position={origin.position}>
            <Station radius={origin.body.radius} />
          </group>
          <Spacecraft
            view={view}
            snapshot={scenicView ? null : snapshot}
            origin={origin.position}
            originRadius={origin.body.radius}
          />
          <CameraRig
            focus={cameraFocus}
            focusRadius={
              captured
                ? 0.65
                : focusName === "Black Hole"
                  ? 1.4
                  : ((visitTarget as { body?: { radius: number } })?.body
                      ?.radius ?? 1)
            }
            transitionKey={transitionKey}
            extent={95}
          />
        </Canvas>
      </SceneBoundary>
      <div className="scene-vignette" aria-hidden="true" />
    </div>
  );
}
