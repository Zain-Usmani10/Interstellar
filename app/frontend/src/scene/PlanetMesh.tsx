import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import {
  AdditiveBlending,
  BackSide,
  DoubleSide,
  Mesh,
  type ColorRepresentation,
} from "three";
import type { PlanetTargetId } from "../api/types";
import type { Vec3 } from "./types";
import type { VisualPlanet } from "./planets";
import { planetBump, planetTexture } from "./surfaces";

type Props = {
  body: VisualPlanet;
  position: Vec3;
  selected: boolean;
  interactive: boolean;
  onSelect: (target: PlanetTargetId) => void;
};

function AtmosphereShell({
  radius,
  color,
  scale,
  opacity,
}: {
  radius: number;
  color: ColorRepresentation;
  scale: number;
  opacity: number;
}) {
  return (
    <mesh scale={scale}>
      <sphereGeometry args={[radius, 48, 32]} />
      <meshBasicMaterial
        color={color}
        side={BackSide}
        transparent
        opacity={opacity}
        depthWrite={false}
        blending={AdditiveBlending}
      />
    </mesh>
  );
}

export function PlanetMesh({
  body,
  position,
  selected,
  interactive,
  onSelect,
}: Props) {
  const sphere = useRef<Mesh>(null);
  const maps = useMemo(
    () => ({
      map: planetTexture(body),
      bumpMap: planetBump(body),
    }),
    [body],
  );

  useFrame((_, delta) => {
    if (sphere.current) {
      const speed =
        body.surface === "gas" ? 0.085 : body.name === "Earth" ? 0.07 : 0.05;
      sphere.current.rotation.y += Math.min(delta, 0.05) * speed;
    }
  });

  const clickable = interactive && !!body.target;
  const atmosphereColor =
    body.name === "Earth"
      ? "#6ec8ff"
      : body.name === "Mars"
        ? "#ff9a6a"
        : body.name === "Neptune" || body.name === "Uranus"
          ? "#7ad0ff"
          : body.color;

  return (
    <group position={position}>
      <mesh
        ref={sphere}
        castShadow
        receiveShadow
        rotation={[0, 0, body.name === "Uranus" ? 1.5 : 0.08]}
        onClick={(e) => {
          if (clickable && body.target) {
            e.stopPropagation();
            onSelect(body.target);
          }
        }}
        onPointerOver={(e) => {
          if (clickable) {
            e.stopPropagation();
            document.body.style.cursor = "pointer";
          }
        }}
        onPointerOut={() => {
          document.body.style.cursor = "auto";
        }}
      >
        <sphereGeometry args={[body.radius, 96, 64]} />
        <meshStandardMaterial
          map={maps.map}
          bumpMap={maps.bumpMap}
          bumpScale={body.surface === "gas" ? 0.012 : 0.045}
          roughness={body.surface === "gas" ? 0.55 : 0.78}
          metalness={body.surface === "gas" ? 0.08 : 0.04}
          emissive={selected ? body.color : "#000000"}
          emissiveIntensity={selected ? 0.12 : 0}
        />
      </mesh>

      <AtmosphereShell
        radius={body.radius}
        color={atmosphereColor}
        scale={1.035}
        opacity={
          body.surface === "earth" || body.name === "Neptune" ? 0.38 : 0.16
        }
      />
      <AtmosphereShell
        radius={body.radius}
        color={atmosphereColor}
        scale={1.09}
        opacity={0.07}
      />

      {body.rings && (
        <group rotation={[Math.PI * 0.38, 0, 0.1]}>
          <mesh receiveShadow>
            <ringGeometry args={[body.radius * 1.28, body.radius * 2.2, 128]} />
            <meshStandardMaterial
              color="#c4b08a"
              side={DoubleSide}
              transparent
              opacity={0.72}
              roughness={0.85}
              metalness={0.05}
            />
          </mesh>
          <mesh>
            <ringGeometry args={[body.radius * 1.62, body.radius * 1.7, 128]} />
            <meshBasicMaterial color="#0b1018" side={DoubleSide} />
          </mesh>
        </group>
      )}

      {selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[body.radius * 1.55, body.radius * 1.62, 96]} />
          <meshBasicMaterial
            color="#b8fff6"
            side={DoubleSide}
            transparent
            opacity={0.9}
          />
        </mesh>
      )}

      <Html
        position={[0, body.radius * 1.85, 0]}
        center
        zIndexRange={[8, 0]}
        style={{ pointerEvents: "none" }}
      >
        <span
          style={{
            display: "block",
            color: selected ? "#e8fffb" : "#a8b8cc",
            font: "600 11px/1 Avenir Next, Segoe UI, sans-serif",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            textShadow: "0 2px 12px rgba(0,0,0,0.85)",
            borderBottom: selected ? "1px solid #7de8da" : "none",
            paddingBottom: 3,
          }}
        >
          {body.name}
        </span>
      </Html>
    </group>
  );
}
