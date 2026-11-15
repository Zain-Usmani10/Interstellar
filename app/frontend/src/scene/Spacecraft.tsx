import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Group, Quaternion, Vector3 } from "three";
import type { Vec3, SceneSnapshot } from "./types";
import type { FlightView } from "./flightState";

const UP = new Vector3(0, 1, 0);

/** Original low-poly orbital platform attached to the illustrative planet marker. */
export function Station({ radius }: { radius: number }) {
  return (
    <group position={[0, radius + 0.22, 0]} scale={0.18}>
      <mesh>
        <cylinderGeometry args={[1.1, 1.3, 0.25, 12]} />
        <meshStandardMaterial
          color="#a3b5c3"
          metalness={0.7}
          roughness={0.35}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.55, 0.065, 6, 32]} />
        <meshStandardMaterial color="#bfc9cf" />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side} position={[side * 2.1, -0.05, 0]}>
          <mesh>
            <boxGeometry args={[2.3, 0.045, 1.15]} />
            <meshStandardMaterial
              color="#183c68"
              metalness={0.5}
              roughness={0.3}
            />
          </mesh>
          {[-0.7, 0, 0.7].map((x) => (
            <mesh key={x} position={[x, 0.026, 0]}>
              <boxGeometry args={[0.025, 0.01, 1.15]} />
              <meshBasicMaterial color="#6da8b8" />
            </mesh>
          ))}
        </group>
      ))}
      <mesh position={[0, -0.3, 0]}>
        <cylinderGeometry args={[0.25, 0.5, 0.4, 8]} />
        <meshStandardMaterial color="#506472" />
      </mesh>
      <mesh position={[1.2, 0.14, 0]}>
        <sphereGeometry args={[0.07, 8, 8]} />
        <meshBasicMaterial color="#75f6d5" />
      </mesh>
    </group>
  );
}

export function RocketModel({ warning }: { warning: boolean }) {
  return (
    <group scale={0.14}>
      <mesh>
        <cylinderGeometry args={[0.23, 0.31, 1.8, 12]} />
        <meshStandardMaterial
          color="#dce4e4"
          metalness={0.5}
          roughness={0.35}
        />
      </mesh>
      <mesh position={[0, 1.18, 0]}>
        <coneGeometry args={[0.23, 0.58, 12]} />
        <meshStandardMaterial color="#dce4e4" />
      </mesh>
      <mesh position={[0, 0.48, 0.205]}>
        <boxGeometry args={[0.15, 0.22, 0.04]} />
        <meshBasicMaterial color="#78c7db" />
      </mesh>
      <mesh position={[0, -0.5, 0]}>
        <cylinderGeometry args={[0.32, 0.32, 0.12, 12]} />
        <meshStandardMaterial color={warning ? "#f19b58" : "#c78554"} />
      </mesh>
      {[0, Math.PI / 2, Math.PI, Math.PI * 1.5].map((angle) => (
        <group key={angle} rotation={[0, angle, 0]}>
          <mesh position={[0.32, -0.7, 0]} rotation={[0, 0, 0.2]}>
            <boxGeometry args={[0.3, 0.55, 0.06]} />
            <meshStandardMaterial color="#7c8d9c" />
          </mesh>
        </group>
      ))}
      <mesh position={[0, -1.02, 0]}>
        <cylinderGeometry args={[0.18, 0.27, 0.25, 12, 1, true]} />
        <meshStandardMaterial color="#354456" />
      </mesh>
    </group>
  );
}

type Props = {
  view: FlightView;
  snapshot?: SceneSnapshot | null;
  origin: Vec3;
  originRadius: number;
  destination?: Vec3;
  destinationRadius?: number;
  launchProgress?: number;
};
export function Spacecraft({ view, snapshot, origin, originRadius, destination, destinationRadius = 1, launchProgress = 0 }: Props) {
  const group = useRef<Group>(null),
    flame = useRef<Group>(null);
  const target = useRef(new Vector3()),
    from = useRef(new Vector3());
  const direction = useRef(new Vector3()),
    rotation = useRef(new Quaternion());
  const elapsed = useRef(1),
    departure = useRef<{ mission: string | null; departed: boolean } | null>(null),
    flash = useRef(0),
    initialized = useRef(false);
  const dock: Vec3 = [origin[0], origin[1] + originRadius + 0.42 + launchProgress * 0.55, origin[2]];
  const landing: Vec3 | null = destination && view.mode === "captured"
    ? [destination[0], destination[1] + destinationRadius + 0.42, destination[2]] : null;
  const [x, y, z] = landing ?? view.position ?? dock;
  const velocity = snapshot?.spacecraft.v_km_s,
    stale = view.stale;
  useEffect(() => {
    target.current.set(x, y, z);
    if (group.current) {
      from.current.copy(group.current.position);
      if (!initialized.current || stale) {
        group.current.position.copy(target.current);
        from.current.copy(target.current);
        initialized.current = true;
      }
    }
    elapsed.current = 0;
  }, [x, y, z, stale, snapshot?.mission_id, view.mode]);
  useEffect(() => {
    const key = snapshot?.mission_id ?? null;
    if (
      view.departed &&
      departure.current?.mission === key &&
      !departure.current.departed &&
      !stale &&
      snapshot?.state === "RUNNING"
    )
      flash.current = 0.7;
    departure.current = { mission: key, departed: view.departed };
  }, [view.departed, snapshot?.mission_id, snapshot?.state, stale]);
  useFrame((_, delta) => {
    if (!group.current) return;
    elapsed.current = Math.min(
      1,
      elapsed.current + Math.min(delta, 0.05) / (view.mode === "captured" ? 1.5 : 0.18),
    );
    const t = elapsed.current * elapsed.current * (3 - 2 * elapsed.current);
    group.current.position.lerpVectors(from.current, target.current, t);
    if (view.departed && view.mode !== "captured" && velocity) {
      direction.current.set(velocity[0], velocity[2], -velocity[1]);
      if (direction.current.lengthSq() > 0)
        group.current.quaternion.slerp(
          rotation.current.setFromUnitVectors(
            UP,
            direction.current.normalize(),
          ),
          0.15,
        );
    } else group.current.quaternion.identity();
    flash.current = Math.max(0, flash.current - Math.min(delta, 0.05));
    if (flame.current)
      flame.current.visible =
        !stale && ((flash.current > 0 && view.mode === "coast") || launchProgress > 0);
  });
  if (view.mode === "unavailable") return null;
  return (
    <group ref={group}>
      <group>
        <RocketModel warning={view.mode === "uncaptured"} />
      </group>
      <group
        ref={flame}
        visible={false}
        position={[0, -0.23, 0]}
        rotation={[Math.PI, 0, 0]}
        scale={0.14}
      >
        <mesh>
          <coneGeometry args={[0.22, 1.05, 12]} />
          <meshBasicMaterial color="#78d4ef" transparent opacity={0.65} />
        </mesh>
        <mesh>
          <coneGeometry args={[0.1, 0.8, 12]} />
          <meshBasicMaterial color="#fff0c9" />
        </mesh>
      </group>
      {view.mode === "captured" && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.25, 0.012, 6, 48]} />
          <meshBasicMaterial color="#88e5be" />
        </mesh>
      )}
    </group>
  );
}
