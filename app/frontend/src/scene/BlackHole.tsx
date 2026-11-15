import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { AdditiveBlending, DoubleSide, Group, Mesh } from "three";

/** Original black-hole presentation beyond Neptune — not copied from reference code. */
export function BlackHole({
  position,
  selected,
  onSelect,
  showLabel = true,
}: {
  position: [number, number, number];
  selected?: boolean;
  onSelect?: () => void;
  showLabel?: boolean;
}) {
  const disk = useRef<Mesh>(null);
  const group = useRef<Group>(null);

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05);
    if (disk.current) disk.current.rotation.z += d * 0.35;
    if (group.current) group.current.rotation.y += d * 0.08;
  });

  return (
    <group
      ref={group}
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.();
      }}
      onPointerOver={() => {
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "auto";
      }}
    >
      <mesh>
        <sphereGeometry args={[0.85, 48, 32]} />
        <meshBasicMaterial color="#000000" />
      </mesh>
      <mesh rotation={[Math.PI / 2.2, 0.2, 0]}>
        <torusGeometry args={[1.15, 0.045, 12, 64]} />
        <meshBasicMaterial
          color="#ffd9a0"
          transparent
          opacity={0.85}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={disk} rotation={[Math.PI / 2.35, 0, 0]}>
        <ringGeometry args={[1.35, 3.4, 96]} />
        <meshBasicMaterial
          color="#ff8a3a"
          side={DoubleSide}
          transparent
          opacity={0.55}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2.35, 0, 0.4]}>
        <ringGeometry args={[1.6, 2.6, 64]} />
        <meshBasicMaterial
          color="#ffd080"
          side={DoubleSide}
          transparent
          opacity={0.25}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {[1, -1].map((dir) => (
        <mesh key={dir} position={[0, dir * 2.4, 0]}>
          <cylinderGeometry args={[0.08, 0.28, 3.2, 12]} />
          <meshBasicMaterial
            color="#9ec9ff"
            transparent
            opacity={0.35}
            blending={AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
      <mesh>
        <sphereGeometry args={[2.2, 24, 16]} />
        <meshBasicMaterial
          color="#301008"
          transparent
          opacity={0.18}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {showLabel ? (
        <Html
          position={[0, 4.2, 0]}
          center
          sprite
          distanceFactor={28}
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
            }}
          >
            Black Hole
          </span>
        </Html>
      ) : null}
    </group>
  );
}
