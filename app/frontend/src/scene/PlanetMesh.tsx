import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";
import type { PlanetInfo } from "../mock/planetInfo";
import { sciToThree } from "./axes";

type Props = {
  planet: PlanetInfo;
  selected: boolean;
  onSelect: (targetId: PlanetInfo["target_id"]) => void;
};

export function PlanetMesh({ planet, selected, onSelect }: Props) {
  const meshRef = useRef<Mesh>(null);
  const [sx, sy, sz] = sciToThree(...planet.display_position_au_scaled);

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.25;
    }
  });

  return (
    <group position={[sx, sy, sz]}>
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(planet.target_id);
        }}
        onPointerOver={() => {
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <sphereGeometry args={[planet.display_radius, 48, 48]} />
        <meshStandardMaterial
          color={planet.display_color}
          emissive={selected ? planet.display_color : "#000000"}
          emissiveIntensity={selected ? 0.45 : 0}
          roughness={0.55}
          metalness={0.15}
        />
      </mesh>
      {selected ? (
        <mesh>
          <ringGeometry
            args={[
              planet.display_radius * 1.35,
              planet.display_radius * 1.55,
              64,
            ]}
          />
          <meshBasicMaterial
            color="#f2e8d5"
            transparent
            opacity={0.85}
            side={2}
          />
        </mesh>
      ) : null}
    </group>
  );
}
