import { Html } from "@react-three/drei";
import { RocketModel, Station } from "./Spacecraft";
import type { SceneShuttle } from "./types";

/** Empty centre pad is reserved for the telemetry-controlled mission shuttle. */
export function DockStation({ radius, shuttles }: { radius: number; shuttles: SceneShuttle[] }) {
  return <>
    <Station radius={radius} />
    <group position={[0, radius + 0.22, 0]}>
      <mesh position={[0, -0.04, 0]}>
        <boxGeometry args={[Math.max(1.4, Math.ceil(shuttles.length / 2) * 1.3 + 0.6), 0.08, 0.65]} />
        <meshStandardMaterial color="#14283c" metalness={0.8} roughness={0.3} />
      </mesh>
      <Pad x={0} />
      {shuttles.map((ship, index) => {
        const x = Math.ceil((index + 1) / 2) * 0.65 * (index % 2 ? -1 : 1);
        return <group key={ship.id} position={[x, 0, 0]}>
          <Pad x={0} />
          <group position={[0, 0.2, 0]}><RocketModel warning={false} /></group>
          <Html center position={[0, -0.15, 0.4]} style={{ pointerEvents: "none" }}>
            <span style={{ color: "#b9e8ed", font: "9px monospace", whiteSpace: "nowrap" }}>
              {ship.class === "standard" ? "STANDARD" : "LONG-RANGE"}
            </span>
          </Html>
        </group>;
      })}
    </group>
  </>;
}

function Pad({ x }: { x: number }) {
  return <mesh position={[x, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
    <ringGeometry args={[0.2, 0.24, 32]} />
    <meshBasicMaterial color="#83ebde" />
  </mesh>;
}
