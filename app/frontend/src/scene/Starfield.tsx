import { useMemo } from "react";
import { AdditiveBlending, BufferAttribute, BufferGeometry, Color } from "three";

type Props = {
  /** Fewer points for the compact inset canvas. */
  compact?: boolean;
};

const PALETTE = [
  new Color("#e8f0ff"),
  new Color("#a8c8ff"),
  new Color("#7aa0ff"),
  new Color("#c4a8ff"),
  new Color("#9b6cff"),
  new Color("#ff9ad8"),
  new Color("#6ec8ff"),
  new Color("#ffffff"),
];

type Cloud = {
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
};

/** Deterministic LCG so the field is stable across renders (oxlint purity). */
function makeCloud(count: number, radius: number, seed: number): Cloud {
  let s = seed >>> 0;
  const rand = () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const u = rand();
    const v = rand();
    const theta = 2 * Math.PI * u;
    let phi = Math.acos(2 * v - 1);
    if (rand() < 0.22) {
      phi = Math.PI * 0.5 + (rand() - 0.5) * 0.35;
    }
    const r = radius * (0.35 + rand() * 0.65);
    const i3 = i * 3;
    positions[i3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i3 + 1] = r * Math.cos(phi) * (0.55 + rand() * 0.45);
    positions[i3 + 2] = r * Math.sin(phi) * Math.sin(theta);

    const c = PALETTE[(rand() * PALETTE.length) | 0].clone();
    c.multiplyScalar(0.45 + rand() * 0.55);
    colors[i3] = c.r;
    colors[i3 + 1] = c.g;
    colors[i3 + 2] = c.b;
    sizes[i] =
      0.5 + rand() * (rand() < 0.08 ? 4.5 : 2.4) * (radius < 1000 ? 0.75 : 1);
  }
  return { positions, colors, sizes };
}

const FULL = makeCloud(9000, 1500, 0x51a7f1e1);
const COMPACT = makeCloud(2200, 900, 0x0c0ffee);

/** Dense procedural starfield — indigo / electric blue / violet / magenta pinpoints. */
export function Starfield({ compact = false }: Props) {
  const cloud = compact ? COMPACT : FULL;
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(cloud.positions, 3));
    g.setAttribute("color", new BufferAttribute(cloud.colors, 3));
    g.setAttribute("size", new BufferAttribute(cloud.sizes, 1));
    return g;
  }, [cloud]);

  return (
    <points geometry={geometry} frustumCulled={false}>
      <pointsMaterial
        size={compact ? 0.85 : 1.15}
        sizeAttenuation
        vertexColors
        transparent
        opacity={0.92}
        depthWrite={false}
        blending={AdditiveBlending}
      />
    </points>
  );
}
