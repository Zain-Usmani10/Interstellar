import { useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbitControls as Controls } from "three-stdlib";
import { Vector3 } from "three";
import type { Vec3 } from "./types";

type Props = {
  focus: Vec3 | null;
  focusRadius: number;
  transitionKey: string;
  extent: number;
};

/** Camera motion is presentation only. User drag cancels an in-progress fly-in. */
export function CameraRig({
  focus,
  focusRadius,
  transitionKey,
  extent,
}: Props) {
  const controls = useRef<Controls>(null);
  const { camera, size } = useThree();
  const previousKey = useRef("");
  const progress = useRef(1),
    from = useRef(new Vector3()),
    to = useRef(new Vector3());
  const fromTarget = useRef(new Vector3()),
    toTarget = useRef(new Vector3());
  useFrame((_, delta) => {
    const orbit = controls.current;
    if (!orbit) return;
    const key = `${transitionKey}:${size.width}:${size.height}`;
    if (previousKey.current !== key) {
      previousKey.current = key;
      progress.current = 0;
      from.current.copy(camera.position);
      fromTarget.current.copy(orbit.target);
      if (focus) {
        toTarget.current.fromArray(focus);
        const d = Math.max(3.5, focusRadius * 6);
        to.current
          .copy(toTarget.current)
          .add(new Vector3(d * 0.7, d * 0.45, d));
      } else {
        toTarget.current.set(0, 0, 0);
        const distance = extent * 2.1 * Math.max(1, size.height / size.width);
        to.current.set(distance * 0.32, distance * 0.6, distance * 0.85);
      }
    }
    if (progress.current < 1) {
      progress.current = Math.min(
        1,
        progress.current + Math.min(delta, 0.05) / 1.5,
      );
      const t =
        progress.current * progress.current * (3 - 2 * progress.current);
      camera.position.lerpVectors(from.current, to.current, t);
      orbit.target.lerpVectors(fromTarget.current, toTarget.current, t);
      orbit.update();
    }
  });
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan
      enableDamping
      dampingFactor={0.09}
      minDistance={1.5}
      maxDistance={1400}
      maxPolarAngle={Math.PI * 0.95}
      onStart={() => {
        progress.current = 1;
      }}
    />
  );
}
