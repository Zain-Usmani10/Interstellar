import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { BackSide, DoubleSide, Group, Mesh, Quaternion, Vector3 } from "three";
import type { SceneBodyId } from "../types";
import { loadPlanetMap } from "../textureMaps";
import { surfaceAnchor } from "./framing";

export type SurfaceShuttle = { id: string; name: string; class: "standard" | "long_range" };
export type PlanetSurfaceProps = {
  bodyId: SceneBodyId;
  radius: number;
  shuttles: SurfaceShuttle[];
  aspect?: number;
  sagitta?: number;
  approach?: number;
  launchingShuttleId?: string | null;
  landedShuttleId?: string | null;
  launchProgress?: number;
  landingProgress?: number;
  showLabels?: boolean;
  /** False when mounted alongside the existing textured PlanetMesh. */
  renderSurface?: boolean;
};

const BODIES: Record<SceneBodyId, [string, string]> = {
  "199": ["Mercury", "#bdb4a5"], "299": ["Venus", "#ecc38b"], "399": ["Earth", "#78dcff"],
  "499": ["Mars", "#ff966a"], "599": ["Jupiter", "#e4b48e"], "699": ["Saturn", "#efdaa2"],
  "799": ["Uranus", "#9aeeee"], "899": ["Neptune", "#689cff"],
};
const clamp = (value: number) => Math.max(0, Math.min(1, value));

function Station({ accent }: { accent: string }) {
  const dish = useRef<Group>(null);
  const beacon = useRef<Mesh>(null);
  useFrame(({ clock }) => {
    if (dish.current) dish.current.rotation.y = Math.sin(clock.elapsedTime * 0.3) * 0.7;
    if (beacon.current) beacon.current.visible = Math.sin(clock.elapsedTime * 3) > -0.4;
  });
  return <group>
    <mesh position={[0, 0.4, 0]}><boxGeometry args={[2.4, 0.8, 1.2]} /><meshStandardMaterial color="#34465b" /></mesh>
    <mesh position={[-0.55, 1.2, 0]}><boxGeometry args={[0.8, 1.6, 0.8]} /><meshStandardMaterial color="#ced5d7" /></mesh>
    <mesh position={[-0.55, 2.1, 0]}><cylinderGeometry args={[0.8, 0.6, 0.48, 6]} /><meshStandardMaterial color="#31455c" /></mesh>
    <mesh position={[-0.55, 2.12, 0.44]}><boxGeometry args={[1.15, 0.22, 0.05]} /><meshBasicMaterial color={accent} /></mesh>
    {[0, 1, 2, 3, 4].map(i => <mesh key={i} position={[-0.8 + i * 0.4, 0.45, 0.61]}>
      <boxGeometry args={[0.17, 0.18, 0.025]} /><meshBasicMaterial color={accent} />
    </mesh>)}
    <group ref={dish} position={[0.65, 1.2, 0]}>
      <mesh position={[0, -0.3, 0]}><cylinderGeometry args={[0.1, 0.18, 0.6, 8]} /><meshStandardMaterial color="#a6bcc9" /></mesh>
      <group rotation={[0.65, 0, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}><sphereGeometry args={[0.65, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2]} /><meshStandardMaterial color="#d2e1e7" side={DoubleSide} /></mesh>
        <mesh position={[0, 0, 0.5]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.025, 0.025, 0.7, 6]} /><meshStandardMaterial color="#abbfce" /></mesh>
      </group>
    </group>
    <mesh ref={beacon} position={[-0.55, 2.48, 0]}><sphereGeometry args={[0.09, 8, 6]} /><meshBasicMaterial color="#ff8a66" /></mesh>
  </group>;
}

function Shuttle({ accent, height, visible, idle }: { accent: string; height: number; visible: boolean; idle: boolean }) {
  const exhaust = useRef<Mesh>(null);
  useFrame(({ clock }) => {
    if (exhaust.current) exhaust.current.scale.y = 0.7 + Math.sin(clock.elapsedTime * 5) * 0.2;
  });
  return <group position={[0, 0.18 + height, 0]} visible={visible}>
    <mesh position={[0, 0.68, 0]}><cylinderGeometry args={[0.22, 0.27, 1.1, 12]} /><meshStandardMaterial color="#e3e9ed" metalness={0.35} roughness={0.4} /></mesh>
    <mesh position={[0, 1.42, 0]}><coneGeometry args={[0.22, 0.4, 12]} /><meshStandardMaterial color={accent} /></mesh>
    <mesh position={[0, 0.95, 0.215]}><boxGeometry args={[0.14, 0.21, 0.035]} /><meshBasicMaterial color="#86dcff" /></mesh>
    {[-1, 1].map(side => <mesh key={side} position={[side * 0.28, 0.35, 0]} rotation={[0, 0, side * -0.2]}>
      <boxGeometry args={[0.2, 0.55, 0.1]} /><meshStandardMaterial color={accent} /></mesh>)}
    <mesh ref={exhaust} position={[0, 0.06, 0]} visible={idle}>
      <coneGeometry args={[0.13, 0.2, 12]} /><meshBasicMaterial color="#6edaff" transparent opacity={0.25} depthWrite={false} />
    </mesh>
  </group>;
}

/** Attach at the planet centre with identity rotation. Geometry follows the sphere. */
export function PlanetSurfaceView({ bodyId, radius, shuttles, aspect: suppliedAspect, sagitta = 0.16,
  approach = 1, launchingShuttleId, landedShuttleId, launchProgress = 0, landingProgress = 1,
  showLabels = false, renderSurface = false }: PlanetSurfaceProps) {
  const size = useThree(state => state.size);
  const aspect = suppliedAspect ?? size.width / size.height;
  const [name, accent] = BODIES[bodyId];
  const map = useMemo(() => renderSurface ? loadPlanetMap(name) : null, [name, renderSurface]);
  const layout = useMemo(() => {
    const coordinates = [-0.52, ...Array.from({ length: shuttles.length + 1 }, (_, i) =>
      -0.04 + i * 0.82 / Math.max(shuttles.length, 1))];
    return coordinates.map(x => {
      const point = surfaceAnchor(radius, aspect, sagitta, x);
      const normal = new Vector3(...point).normalize();
      return { point, rotation: new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), normal) };
    });
  }, [radius, aspect, sagitta, shuttles.length]);
  const dressing = clamp((approach - 0.65) / 0.35);
  const scale = radius * 0.055 * Math.min(1, 1.78 / aspect);
  return <group>
    {renderSurface && <mesh><sphereGeometry args={[radius, 96, 64]} /><meshStandardMaterial map={map} color={map ? "white" : accent} roughness={0.85} /></mesh>}
    <mesh scale={1.006}><sphereGeometry args={[radius, 64, 48]} /><meshBasicMaterial color={accent} side={BackSide} transparent opacity={0.14 * dressing} depthWrite={false} /></mesh>
    {layout.map(({ point, rotation }, i) => <group key={i} position={point} quaternion={rotation}>
      <group scale={scale * dressing} visible={dressing > 0}>
        {i === 0 ? <Station accent={accent} /> : <>
          <mesh position={[0, 0.06, 0]}><cylinderGeometry args={[0.7, 0.73, 0.12, 8]} /><meshStandardMaterial color="#4a5868" roughness={0.9} /></mesh>
          {[-1, 1].map(x => <mesh key={x} position={[x * 0.45, 0.13, 0.25]}><boxGeometry args={[0.08, 0.025, 0.3]} /><meshBasicMaterial color={accent} /></mesh>)}
          {shuttles[i-1] && <>
            <Shuttle accent={shuttles[i-1].class === "long_range" ? "#d5a675" : accent}
              height={shuttles[i-1].id === launchingShuttleId ? clamp(launchProgress) * 8
                : shuttles[i-1].id === landedShuttleId ? (1-clamp(landingProgress)) * 8 : 0}
              visible={shuttles[i-1].id !== launchingShuttleId || launchProgress < 1}
              idle={shuttles[i-1].id !== launchingShuttleId} />
            {showLabels && <Html center position={[0, 2, 0]} style={{ color: "white", whiteSpace: "nowrap", pointerEvents: "none" }}>{shuttles[i-1].name}</Html>}
          </>}
        </>}
      </group>
    </group>)}
  </group>;
}
