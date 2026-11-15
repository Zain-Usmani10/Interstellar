import { useMemo } from "react";
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  type Texture,
} from "three";

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
};

let cachedMap: Texture | null = null;

/** Soft round sprite so PointsMaterial does not draw squares. */
function softDiscTexture(): Texture {
  if (cachedMap) return cachedMap;
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    cachedMap = new CanvasTexture(canvas);
    return cachedMap;
  }
  const g = ctx.createRadialGradient(
    size / 2,
    size / 2,
    0,
    size / 2,
    size / 2,
    size / 2,
  );
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.35, "rgba(255,255,255,0.75)");
  g.addColorStop(0.7, "rgba(255,255,255,0.2)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  cachedMap = new CanvasTexture(canvas);
  cachedMap.needsUpdate = true;
  return cachedMap;
}

/** Deterministic LCG so the field is stable across renders (oxlint purity). */
function makeCloud(count: number, radius: number, seed: number): Cloud {
  let s = seed >>> 0;
  const rand = () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  for (let i = 0; i < count; i++) {
    const u = rand();
    const v = rand();
    const theta = 2 * Math.PI * u;
    let phi = Math.acos(2 * v - 1);
    if (rand() < 0.28) {
      phi = Math.PI * 0.5 + (rand() - 0.5) * 0.4;
    }
    const r = radius * (0.28 + rand() * 0.72);
    const i3 = i * 3;
    positions[i3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i3 + 1] = r * Math.cos(phi) * (0.5 + rand() * 0.5);
    positions[i3 + 2] = r * Math.sin(phi) * Math.sin(theta);

    const c = PALETTE[(rand() * PALETTE.length) | 0].clone();
    c.multiplyScalar(0.4 + rand() * 0.6);
    colors[i3] = c.r;
    colors[i3 + 1] = c.g;
    colors[i3 + 2] = c.b;
  }
  return { positions, colors };
}

const FULL = makeCloud(16000, 1600, 0x51a7f1e1);
const COMPACT = makeCloud(3500, 950, 0x0c0ffee);

/** Dense procedural starfield — round soft pinpoints, indigo / blue / violet / magenta. */
export function Starfield({ compact = false }: Props) {
  const cloud = compact ? COMPACT : FULL;
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(cloud.positions, 3));
    g.setAttribute("color", new BufferAttribute(cloud.colors, 3));
    return g;
  }, [cloud]);
  const map = useMemo(() => softDiscTexture(), []);

  return (
    <points geometry={geometry} frustumCulled={false}>
      <pointsMaterial
        map={map}
        size={compact ? 1.6 : 2.2}
        sizeAttenuation
        vertexColors
        transparent
        opacity={0.95}
        depthWrite={false}
        blending={AdditiveBlending}
        alphaTest={0.01}
      />
    </points>
  );
}
