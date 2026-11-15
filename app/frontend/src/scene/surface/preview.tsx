import { useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Stars } from "@react-three/drei";
import { PerspectiveCamera, Vector3 } from "three";
import { PlanetSurfaceView } from "./PlanetSurfaceView";
import { surfaceCameraPose } from "./framing";
import type { SceneBodyId } from "../types";

const planets: [SceneBodyId, string][] = [["199", "Mercury"], ["299", "Venus"], ["399", "Earth"],
  ["499", "Mars"], ["599", "Jupiter"], ["699", "Saturn"], ["799", "Uranus"], ["899", "Neptune"]];
const ships = [{ id: "a", name: "Standard shuttle", class: "standard" as const },
  { id: "b", name: "Long-range shuttle", class: "long_range" as const }];

function Scene({ body, close, progress }: { body: SceneBodyId; close: boolean; progress: number }) {
  const { size } = useThree();
  const pose = useMemo(() => surfaceCameraPose(1, size.width / size.height), [size]);
  const look = useRef(new Vector3());
  const desired = useRef(new Vector3());
  const [approach, setApproach] = useState(0);
  const frames = useRef<number[]>([]);
  useFrame(({ camera }, delta) => {
    const alpha = 1 - Math.exp(-Math.min(delta, 0.05) * 4);
    desired.current.set(...(close ? pose.position : [0, 0, 4] as [number, number, number]));
    camera.position.lerp(desired.current, alpha);
    desired.current.set(...(close ? pose.lookAt : [0, 0, 0] as [number, number, number]));
    look.current.lerp(desired.current, alpha);
    camera.lookAt(look.current);
    (camera as PerspectiveCamera).fov = pose.fov;
    camera.updateProjectionMatrix();
    const next = approach + ((close ? 1 : 0) - approach) * alpha;
    if (Math.abs(next - approach) > 0.0001) setApproach(next);
    frames.current.push(delta);
    if (frames.current.length > 180) frames.current.shift();
    const output = document.getElementById('fps');
    if (output) output.textContent = `${Math.round(frames.current.length / frames.current.reduce((a, b) => a + b, 0))} fps /  ${document.visibilityState}`;
  });
  return <>
    <color attach="background" args={["#050819"]} />
    <ambientLight intensity={1.0} />
    <directionalLight position={[-2, 4, 4]} intensity={2.2} />
    <directionalLight position={[3, 1, -1]} intensity={0.7} color="#8caaff" />
    <Stars radius={40} depth={30} count={6000} factor={4} saturation={0.3} fade speed={0.1} />
    <PlanetSurfaceView bodyId={body} radius={1} shuttles={ships} renderSurface approach={approach}
      launchingShuttleId={progress > 0 ? 'a' : null} launchProgress={progress} />
  </>;
}

export default function Preview() {
  const [body, setBody] = useState<SceneBodyId>('399');
  const [close, setClose] = useState(true);
  const [progress, setProgress] = useState(0);
  return <main style={{ width: '100vw', height: '100vh', background: '#050819', color: '#d9e5ed', fontFamily: 'system-ui' }}>
    <Canvas dpr={1} camera={{ position: [0, 0, 4], near: 0.001, far: 100, fov: 35 }}>
      <Scene body={body} close={close} progress={progress} />
    </Canvas>
    <nav style={{ position: 'absolute', left: 24, top: 20, display: 'flex', gap: 8, flexWrap: 'wrap', maxWidth: '90%' }}>
      {planets.map(([id, name]) => <button key={id} onClick={() => { setBody(id); setClose(true); }}
        style={{ border: '1px solid #334259', borderRadius: 6, background: body === id ? '#315275' : '#111d31', color: 'white', padding: '8px 12px' }}>{name}</button>)}
      <button onClick={() => setClose(!close)}>Zoom {close ? 'out' : 'in'}</button>
    </nav>
    <div style={{ position: 'absolute', left: 24, top: 78, fontSize: 12, color: '#b8c7d9' }}>
      Illustrative surface / gas-giant cloud deck · mock fleet · <span id="fps" />
    </div>
    <label style={{ position: 'absolute', right: 24, bottom: 20, fontSize: 12 }}>Mock lift-off
      <input aria-label="Mock lift-off" type="range" min={0} max={1} step={0.01} value={progress} onChange={e => setProgress(Number(e.target.value))} />
    </label>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Preview />);
