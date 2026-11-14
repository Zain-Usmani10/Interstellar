import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { Line, OrbitControls, Stars } from "@react-three/drei";
import { PLANETS, type PlanetTargetId } from "../mock/planetInfo";
import { sciToThree } from "./axes";
import { PlanetMesh } from "./PlanetMesh";

type Props = {
  selectedId: PlanetTargetId | null;
  onSelect: (targetId: PlanetTargetId) => void;
};

function Sun() {
  return (
    <mesh>
      <sphereGeometry args={[0.55, 32, 32]} />
      <meshBasicMaterial color="#f0c36a" />
      <pointLight intensity={2.2} distance={80} decay={1.2} color="#fff1c9" />
    </mesh>
  );
}

function OrbitGuide({ radius }: { radius: number }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[radius - 0.02, radius + 0.02, 128]} />
      <meshBasicMaterial color="#6a7a8c" transparent opacity={0.35} />
    </mesh>
  );
}

/** Decorative mock preview arc — not a validated Lambert sample path. */
function MockTransferPreview() {
  const points = useMemo(() => {
    const earth = PLANETS[0].display_position_au_scaled;
    const mars = PLANETS[1].display_position_au_scaled;
    const out: [number, number, number][] = [];
    const steps = 48;
    for (let i = 0; i <= steps; i += 1) {
      const t = i / steps;
      const x = earth[0] + (mars[0] - earth[0]) * t;
      const y = earth[1] + (mars[1] - earth[1]) * t + Math.sin(Math.PI * t) * 2.5;
      const z = earth[2] + (mars[2] - earth[2]) * t;
      out.push(sciToThree(x, y, z));
    }
    return out;
  }, []);

  return <Line points={points} color="#9bb6d4" lineWidth={1.5} transparent opacity={0.55} />;
}

export function OrbitScene({ selectedId, onSelect }: Props) {
  return (
    <Canvas
      camera={{ position: [18, 12, 18], fov: 42, near: 0.1, far: 500 }}
      dpr={[1, 1.75]}
      style={{ width: "100%", height: "100%" }}
    >
      <color attach="background" args={["#070b12"]} />
      <ambientLight intensity={0.28} />
      <Stars
        radius={120}
        depth={50}
        count={2500}
        factor={3}
        saturation={0}
        fade
        speed={0.4}
      />
      <Sun />
      <OrbitGuide radius={10} />
      <OrbitGuide radius={15.2} />
      <MockTransferPreview />
      {PLANETS.map((planet) => (
        <PlanetMesh
          key={planet.target_id}
          planet={planet}
          selected={selectedId === planet.target_id}
          onSelect={onSelect}
        />
      ))}
      <OrbitControls
        enablePan
        minDistance={6}
        maxDistance={60}
        target={[8, 0, 0]}
      />
    </Canvas>
  );
}
