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
  /** After launch: track the craft and ease the camera outward. */
  follow?: boolean;
  /** Overview pull-back multiplier (A4: keep planets detailed, not specks). */
  overviewDistanceScale?: number;
};

/** Camera motion is presentation only. User drag cancels an in-progress fly-in. */
export function CameraRig({
  focus,
  focusRadius,
  transitionKey,
  extent,
  follow = false,
  overviewDistanceScale = 1.05,
}: Props) {
  const controls = useRef<Controls>(null);
  const { camera, size } = useThree();
  const previousKey = useRef("");
  const progress = useRef(1);
  const from = useRef(new Vector3());
  const to = useRef(new Vector3());
  const fromTarget = useRef(new Vector3());
  const toTarget = useRef(new Vector3());
  const previousFocus = useRef(new Vector3());
  const focusOffset = useRef(new Vector3());
  const zoomOut = useRef(0);

  useFrame((_, delta) => {
    const orbit = controls.current;
    if (!orbit) return;
    const key = `${transitionKey}:${size.width}:${size.height}:${follow ? "follow" : "visit"}`;
    if (previousKey.current !== key) {
      previousKey.current = key;
      progress.current = 0;
      zoomOut.current = follow ? 0 : 1;
      from.current.copy(camera.position);
      fromTarget.current.copy(orbit.target);
      if (focus) {
        previousFocus.current.fromArray(focus);
        toTarget.current.fromArray(focus);
        if (!follow) {
          toTarget.current.y += focusRadius * 0.55;
        }
        const d = Math.max(2.2, focusRadius * (follow ? 3.2 : 3.6));
        to.current
          .copy(toTarget.current)
          .add(new Vector3(d * 0.25, d * 0.35, d));
      } else {
        toTarget.current.set(0, 0, 0);
        const distance =
          extent *
          overviewDistanceScale *
          Math.max(1, size.height / size.width);
        to.current.set(distance * 0.28, distance * 0.48, distance * 0.72);
      }
    } else if (focus) {
      focusOffset.current.fromArray(focus).sub(previousFocus.current);
      previousFocus.current.fromArray(focus);
      from.current.add(focusOffset.current);
      to.current.add(focusOffset.current);
      fromTarget.current.add(focusOffset.current);
      toTarget.current.add(focusOffset.current);
      camera.position.add(focusOffset.current);
      orbit.target.add(focusOffset.current);

      if (follow) {
        // Part B: pull back only a little — watch take-off, no system zoom-out.
        zoomOut.current = Math.min(1, zoomOut.current + delta / 6);
        const near = Math.max(2.2, focusRadius * 2.8);
        const far = near * 1.45;
        const d = near + (far - near) * zoomOut.current;
        toTarget.current.fromArray(focus);
        to.current
          .copy(toTarget.current)
          .add(new Vector3(d * 0.22, d * 0.32, d));
        if (progress.current >= 1) {
          camera.position.lerp(to.current, Math.min(1, delta * 2.2));
          orbit.target.lerp(toTarget.current, Math.min(1, delta * 2.2));
          orbit.update();
        }
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
      dampingFactor={0.12}
      minDistance={1.5}
      maxDistance={900}
      maxPolarAngle={Math.PI * 0.95}
      onStart={() => {
        progress.current = 1;
      }}
    />
  );
}
