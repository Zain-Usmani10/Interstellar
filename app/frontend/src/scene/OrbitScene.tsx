import { Component, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { Line, Stars } from "@react-three/drei";
import { AdditiveBlending } from "three";
import type { PlanetTargetId } from "../api/types";
import { PlanetMesh } from "./PlanetMesh";
import { CameraRig } from "./CameraRig";
import { ScenePerformance } from "./ScenePerformance";
import { Spacecraft, Station } from "./Spacecraft";
import { VISUAL_PLANETS, planetPosition } from "./planets";
import { flightView, routePoints } from "./flightState";
import { sunGlow } from "./surfaces";
import type { ScenePlan, SceneSnapshot } from "./types";
import "./scene.css";

export type { ScenePlan, SceneSnapshot } from "./types";
export type OrbitSceneProps = {
  selectedId: PlanetTargetId | null;
  selectionEnabled?: boolean;
  onSelect: (target: PlanetTargetId) => void;
  /** Visit focus for the bottom planet bar (any of the eight names). */
  focusName?: string | null;
  plan?: ScenePlan | null;
  snapshot?: SceneSnapshot | null;
};

function Sun() {
  return (
    <group>
      <mesh>
        <sphereGeometry args={[1.3, 48, 32]} />
        <meshBasicMaterial color="#ffdba1" />
      </mesh>
      <sprite scale={[18, 18, 1]}>
        <spriteMaterial
          map={sunGlow()}
          blending={AdditiveBlending}
          depthWrite={false}
          opacity={0.95}
        />
      </sprite>
      <sprite scale={[32, 32, 1]}>
        <spriteMaterial
          map={sunGlow()}
          blending={AdditiveBlending}
          depthWrite={false}
          opacity={0.35}
        />
      </sprite>
      <pointLight color="#ffe1b3" intensity={95} decay={2} />
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
  focusName = null,
  plan,
  snapshot,
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
  const view = flightView(snapshot, plan);
  const points = useMemo(() => routePoints(plan), [plan]);
  const planets = VISUAL_PLANETS.map((body) => ({
    body,
    position: planetPosition(
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
  )!;
  const captured = view.mode === "captured";
  const visitTarget = focused ?? selected;
  const cameraFocus = captured
    ? view.position
    : !view.departed
      ? (visitTarget?.position ?? null)
      : null;
  const transitionKey = `${focusName ?? selectedId ?? "overview"}:${snapshot?.mission_id ?? "preview"}:${view.mode}`;
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
          <color attach="background" args={["#03060d"]} />
          <fog attach="fog" args={["#03060d", 120, 1600]} />
          <ambientLight intensity={0.55} />
          <directionalLight
            position={[20, 30, 15]}
            color="#e4efff"
            intensity={2.4}
          />
          <Stars
            radius={1400}
            depth={600}
            count={3200}
            factor={3.2}
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
          {points.length > 1 && (
            <Line
              points={points}
              color="#8cdece"
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
            snapshot={snapshot}
            origin={origin.position}
            originRadius={origin.body.radius}
          />
          <CameraRig
            focus={cameraFocus}
            focusRadius={
              captured ? 0.65 : (visitTarget?.body.radius ?? 1)
            }
            transitionKey={transitionKey}
            extent={80}
          />
        </Canvas>
      </SceneBoundary>
      <div className="scene-vignette" aria-hidden="true" />
    </div>
  );
}
