import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { BackSide, DoubleSide, Mesh } from "three";
import type { PlanetTargetId } from "../api/types";
import type { Vec3 } from "./types";
import type { VisualPlanet } from "./planets";
import { planetTexture } from "./surfaces";

type Props = {
  body: VisualPlanet;
  position: Vec3;
  selected: boolean;
  interactive: boolean;
  onSelect: (target: PlanetTargetId) => void;
};
export function PlanetMesh({
  body,
  position,
  selected,
  interactive,
  onSelect,
}: Props) {
  const sphere = useRef<Mesh>(null);
  useFrame((_, delta) => {
    if (sphere.current)
      sphere.current.rotation.y += Math.min(delta, 0.05) * 0.055;
  });
  const clickable = interactive && !!body.target;
  return (
    <group position={position}>
      <mesh
        ref={sphere}
        rotation={[0, 0, body.name === "Uranus" ? 1.5 : 0.08]}
        onClick={(e) => {
          if (clickable && body.target) {
            e.stopPropagation();
            onSelect(body.target);
          }
        }}
      >
        <sphereGeometry args={[body.radius, 48, 32]} />
        <meshStandardMaterial
          map={planetTexture(body)}
          roughness={0.9}
          metalness={0.02}
        />
      </mesh>
      {(body.surface === "earth" || body.name === "Neptune") && (
        <mesh scale={1.045}>
          <sphereGeometry args={[body.radius, 32, 24]} />
          <meshBasicMaterial
            color={body.color}
            side={BackSide}
            transparent
            opacity={0.28}
            depthWrite={false}
          />
        </mesh>
      )}
      {body.rings && (
        <group rotation={[Math.PI * 0.38, 0, 0.1]}>
          <mesh>
            <ringGeometry args={[body.radius * 1.3, body.radius * 2.15, 96]} />
            <meshStandardMaterial
              color="#a89875"
              side={DoubleSide}
              transparent
              opacity={0.65}
            />
          </mesh>
          <mesh>
            <ringGeometry args={[body.radius * 1.65, body.radius * 1.69, 96]} />
            <meshBasicMaterial color="#151b27" side={DoubleSide} />
          </mesh>
        </group>
      )}
      {selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[body.radius * 1.5, body.radius * 1.53, 96]} />
          <meshBasicMaterial
            color="#b1e8e4"
            side={DoubleSide}
            transparent
            opacity={0.85}
          />
        </mesh>
      )}
      <Html
        position={[0, body.radius * 1.7, 0]}
        center
        zIndexRange={[8, 0]}
        style={{ pointerEvents: "none" }}
      >
        <span
          style={{
            display: "block",
            color: selected ? "#c1f6ef" : "#9dabbf",
            font: "10px ui-monospace, monospace",
            letterSpacing: ".14em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            textShadow: "0 2px 8px #000",
            borderBottom: selected ? "1px solid #74d3c7" : "none",
            paddingBottom: 4,
          }}
        >
          {body.name}
        </span>
      </Html>
    </group>
  );
}
