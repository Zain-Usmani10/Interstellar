import { useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbitControls as Controls } from "three-stdlib";
import { PerspectiveCamera, Vector3, type Camera } from "three";
import type { Vec3 } from "./types";
import { surfaceCameraPose } from "./surface";

function asPerspective(camera: Camera): PerspectiveCamera | null {
  return camera instanceof PerspectiveCamera ? camera : null;
}

type Props = {
  focus: Vec3 | null;
  focusRadius: number;
  transitionKey: string;
  extent: number;
  /** After launch: track the craft and ease the camera outward. */
  follow?: boolean;
  /** Planet click: zoom into Affan's low-arc surface framing. */
  surface?: boolean;
  sagitta?: number;
  /** Overview pull-back multiplier (A4: keep planets detailed, not specks). */
  overviewDistanceScale?: number;
  /** 0..1 zoom progress for surface dressing fade-in. */
  onApproach?: (value: number) => void;
};

const DEFAULT_FOV = 42;

/** Camera motion is presentation only. User drag cancels an in-progress fly-in. */
export function CameraRig({
  focus,
  focusRadius,
  transitionKey,
  extent,
  follow = false,
  surface = false,
  sagitta = 0.16,
  overviewDistanceScale = 1.05,
  onApproach,
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
  const fromFov = useRef(DEFAULT_FOV);
  const toFov = useRef(DEFAULT_FOV);
  const approachRef = useRef(onApproach);
  approachRef.current = onApproach;
  const lastApproach = useRef(-1);

  useFrame((_, delta) => {
    const orbit = controls.current;
    const perspective = asPerspective(camera);
    if (!orbit || !perspective) return;
    const aspect = Math.max(0.5, size.width / Math.max(1, size.height));
    const key = `${transitionKey}:${size.width}:${size.height}:${follow ? "follow" : surface ? "surface" : "visit"}`;
    if (previousKey.current !== key) {
      previousKey.current = key;
      progress.current = 0;
      zoomOut.current = follow ? 0 : 1;
      from.current.copy(perspective.position);
      fromTarget.current.copy(orbit.target);
      fromFov.current = perspective.fov;
      if (focus && surface && !follow) {
        previousFocus.current.fromArray(focus);
        const pose = surfaceCameraPose(focusRadius, aspect, sagitta);
        to.current.set(
          focus[0] + pose.position[0],
          focus[1] + pose.position[1],
          focus[2] + pose.position[2],
        );
        toTarget.current.set(
          focus[0] + pose.lookAt[0],
          focus[1] + pose.lookAt[1],
          focus[2] + pose.lookAt[2],
        );
        toFov.current = pose.fov;
        perspective.near = Math.min(perspective.near, focusRadius * 0.001);
        perspective.updateProjectionMatrix();
      } else if (focus) {
        previousFocus.current.fromArray(focus);
        toTarget.current.fromArray(focus);
        if (!follow) {
          toTarget.current.y += focusRadius * 0.55;
        }
        const d = Math.max(2.2, focusRadius * (follow ? 3.2 : 3.6));
        to.current
          .copy(toTarget.current)
          .add(new Vector3(d * 0.25, d * 0.35, d));
        toFov.current = DEFAULT_FOV;
      } else {
        toTarget.current.set(0, 0, 0);
        const distance =
          extent *
          overviewDistanceScale *
          Math.max(1, size.height / size.width);
        to.current.set(distance * 0.28, distance * 0.48, distance * 0.72);
        toFov.current = DEFAULT_FOV;
      }
    } else if (focus) {
      focusOffset.current.fromArray(focus).sub(previousFocus.current);
      previousFocus.current.fromArray(focus);
      from.current.add(focusOffset.current);
      to.current.add(focusOffset.current);
      fromTarget.current.add(focusOffset.current);
      toTarget.current.add(focusOffset.current);
      perspective.position.add(focusOffset.current);
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
          perspective.position.lerp(to.current, Math.min(1, delta * 2.2));
          orbit.target.lerp(toTarget.current, Math.min(1, delta * 2.2));
          orbit.update();
        }
      } else if (surface) {
        const pose = surfaceCameraPose(focusRadius, aspect, sagitta);
        to.current.set(
          focus[0] + pose.position[0],
          focus[1] + pose.position[1],
          focus[2] + pose.position[2],
        );
        toTarget.current.set(
          focus[0] + pose.lookAt[0],
          focus[1] + pose.lookAt[1],
          focus[2] + pose.lookAt[2],
        );
      }
    }
    if (progress.current < 1) {
      progress.current = Math.min(
        1,
        progress.current + Math.min(delta, 0.05) / 1.5,
      );
      const t =
        progress.current * progress.current * (3 - 2 * progress.current);
      perspective.position.lerpVectors(from.current, to.current, t);
      orbit.target.lerpVectors(fromTarget.current, toTarget.current, t);
      perspective.fov = fromFov.current + (toFov.current - fromFov.current) * t;
      perspective.updateProjectionMatrix();
      orbit.update();
    }
    const approach =
      surface && focus && !follow
        ? progress.current >= 1
          ? 1
          : progress.current
        : 0;
    if (
      Math.abs(approach - lastApproach.current) >= 0.03 ||
      approach === 0 ||
      approach === 1
    ) {
      if (approach !== lastApproach.current) {
        lastApproach.current = approach;
        approachRef.current?.(approach);
      }
    }
  });
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan
      enableDamping
      dampingFactor={0.12}
      minDistance={surface && !follow ? Math.max(0.05, focusRadius * 0.05) : 1.5}
      maxDistance={900}
      maxPolarAngle={Math.PI * 0.95}
      onStart={() => {
        progress.current = 1;
      }}
    />
  );
}
