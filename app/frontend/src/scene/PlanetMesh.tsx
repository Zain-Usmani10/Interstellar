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
import { loadPlanetMap, loadTexture } from "./textureMaps";

type Props = {
  body: VisualPlanet;
  position: Vec3;
  selected: boolean;
  interactive: boolean;
  onSelect: (target: PlanetTargetId) => void;
  onFocus?: () => void;
  showLabel?: boolean;
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
  onFocus,
  showLabel = true,
}: Props) {
  const sphere = useRef<Mesh>(null);
  const clouds = useRef<Mesh>(null);
  const maps = useMemo(() => {
    const photo = loadPlanetMap(body.name);
    return {
      map: photo ?? planetTexture(body),
      bumpMap: photo ? null : planetBump(body),
      clouds:
        body.name === "Earth" ? loadTexture("/textures/2k_earth_clouds.jpg") : null,
      rings:
        body.rings ? loadTexture("/textures/2k_saturn_ring_alpha.png") : null,
    };
  }, [body]);

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05);
    if (sphere.current) {
      const speed =
        body.surface === "gas" ? 0.085 : body.name === "Earth" ? 0.07 : 0.05;
      sphere.current.rotation.y += d * speed;
    }
    if (clouds.current) clouds.current.rotation.y += d * 0.09;
  });

  const clickable = interactive && (!!body.target || !!onFocus);
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
        rotation={[0, 0, body.name === "Uranus" ? 1.5 : 0.08]}
        onClick={(e) => {
          if (clickable) {
            e.stopPropagation();
            if (body.target) onSelect(body.target);
            onFocus?.();
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
          bumpMap={maps.bumpMap ?? undefined}
          bumpScale={maps.bumpMap ? (body.surface === "gas" ? 0.012 : 0.045) : 0}
          roughness={body.surface === "gas" ? 0.5 : 0.72}
          metalness={body.surface === "gas" ? 0.06 : 0.03}
          emissive={selected ? body.color : "#000000"}
          emissiveIntensity={selected ? 0.1 : 0}
        />
      </mesh>

      {maps.clouds ? (
        <mesh ref={clouds} scale={1.018}>
          <sphereGeometry args={[body.radius, 64, 48]} />
          <meshStandardMaterial
            map={maps.clouds}
            transparent
            opacity={0.45}
            depthWrite={false}
            roughness={1}
            metalness={0}
          />
        </mesh>
      ) : null}

      <AtmosphereShell
        radius={body.radius}
        color={atmosphereColor}
        scale={1.04}
        opacity={
          body.surface === "earth" || body.name === "Neptune" ? 0.4 : 0.16
        }
      />
      <AtmosphereShell
        radius={body.radius}
        color={atmosphereColor}
        scale={1.1}
        opacity={0.07}
      />

      {body.rings && (
        <group rotation={[Math.PI * 0.38, 0, 0.1]}>
          <mesh>
            <ringGeometry args={[body.radius * 1.28, body.radius * 2.25, 128]} />
            <meshStandardMaterial
              map={maps.rings ?? undefined}
              color={maps.rings ? "#ffffff" : "#c4b08a"}
              side={DoubleSide}
              transparent
              opacity={0.85}
              roughness={0.85}
              metalness={0.05}
              alphaMap={maps.rings ?? undefined}
            />
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

      {showLabel ? (
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
      ) : null}
    </group>
  );
}
