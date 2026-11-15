import { CanvasTexture, LinearSRGBColorSpace, SRGBColorSpace } from "three";
import type { VisualPlanet } from "./planets";

type Maps = { color: CanvasTexture; bump: CanvasTexture };
const cache = new Map<string, Maps>();

function fieldAt(lon: number, lat: number) {
  return (
    Math.sin(lon * 3 + Math.sin(lat * 5)) * Math.cos(lat * 4) +
    0.45 * Math.sin(lon * 7 - lat * 9) +
    0.2 * Math.cos(lon * 13 + lat * 11)
  );
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

function buildMaps(body: VisualPlanet): Maps {
  const width = 768;
  const height = 384;
  const colorCanvas = document.createElement("canvas");
  colorCanvas.width = width;
  colorCanvas.height = height;
  const bumpCanvas = document.createElement("canvas");
  bumpCanvas.width = width;
  bumpCanvas.height = height;
  const c = colorCanvas.getContext("2d")!;
  const b = bumpCanvas.getContext("2d")!;
  const colorData = c.createImageData(width, height);
  const bumpData = b.createImageData(width, height);
  const [br, bg, bb] = hexToRgb(body.color);
  const [ar, ag, ab] = hexToRgb(body.accent);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const lon = (x / width) * Math.PI * 2;
      const lat = (y / height) * Math.PI;
      const field = fieldAt(lon, lat);
      const band =
        body.surface === "gas"
          ? Math.sin(lat * 36 + Math.sin(lon * 5) * 0.55)
          : field;
      let r = br,
        g = bg,
        bl = bb;
      let heightSample = 0.5 + band * 0.18;

      if (body.surface === "earth") {
        const land = field > 0.38 && Math.sin(lat) > 0.18;
        if (land) {
          if (field > 0.92) {
            r = 201;
            g = 194;
            bl = 154;
          } else {
            r = ar;
            g = ag;
            bl = ab;
          }
          heightSample = 0.62 + field * 0.2;
        } else {
          const deep = 0.55 + field * 0.12;
          r = 20 + deep * 40;
          g = 70 + deep * 50;
          bl = 110 + deep * 60;
          heightSample = 0.35 + field * 0.08;
        }
        if (Math.sin(lat) < 0.16) {
          r = 232;
          g = 244;
          bl = 242;
          heightSample = 0.72;
        }
        if (Math.sin(lon * 9 + lat * 17 + field * 2) > 0.9) {
          r = r * 0.65 + 245 * 0.35;
          g = g * 0.65 + 250 * 0.35;
          bl = bl * 0.65 + 255 * 0.35;
        }
      } else if (body.surface === "gas") {
        const mix = 0.35 + Math.abs(band) * 0.4;
        if (band > 0) {
          r = br * (1 - mix) + ar * mix;
          g = bg * (1 - mix) + ag * mix;
          bl = bb * (1 - mix) + ab * mix;
        } else {
          r = br * (1 - mix) + 255 * mix;
          g = bg * (1 - mix) + 241 * mix;
          bl = bb * (1 - mix) + 208 * mix;
        }
        heightSample = 0.45 + (0.5 + band * 0.5) * 0.12;
      } else {
        const mix = 0.14 + Math.abs(field) * 0.28;
        if (field > 0) {
          r = br * (1 - mix) + ar * mix;
          g = bg * (1 - mix) + ag * mix;
          bl = bb * (1 - mix) + ab * mix;
        } else {
          r = br * (1 - mix) + 240 * mix;
          g = bg * (1 - mix) + 226 * mix;
          bl = bb * (1 - mix) + 200 * mix;
        }
        heightSample = 0.48 + field * 0.28;
      }

      colorData.data[i] = r;
      colorData.data[i + 1] = g;
      colorData.data[i + 2] = bl;
      colorData.data[i + 3] = 255;
      const grey = Math.max(0, Math.min(255, Math.floor(heightSample * 255)));
      bumpData.data[i] = grey;
      bumpData.data[i + 1] = grey;
      bumpData.data[i + 2] = grey;
      bumpData.data[i + 3] = 255;
    }
  }

  c.putImageData(colorData, 0, 0);
  b.putImageData(bumpData, 0, 0);

  if (body.surface === "rock") {
    for (let i = 0; i < 55; i++) {
      const cx = (i * 137.5) % width;
      const cy = 18 + ((i * 71.3) % (height - 36));
      const rad = 2 + (i % 6) * 1.6;
      c.beginPath();
      c.arc(cx, cy, rad, 0, Math.PI * 2);
      c.fillStyle = "rgba(30,18,16,0.22)";
      c.fill();
      b.beginPath();
      b.arc(cx, cy, rad * 0.9, 0, Math.PI * 2);
      b.fillStyle = "rgba(40,40,40,0.55)";
      b.fill();
    }
  }

  const color = new CanvasTexture(colorCanvas);
  color.colorSpace = SRGBColorSpace;
  color.anisotropy = 4;
  const bump = new CanvasTexture(bumpCanvas);
  bump.colorSpace = LinearSRGBColorSpace;
  return { color, bump };
}

function mapsFor(body: VisualPlanet): Maps {
  let maps = cache.get(body.name);
  if (!maps) {
    maps = buildMaps(body);
    cache.set(body.name, maps);
  }
  return maps;
}

export function planetTexture(body: VisualPlanet): CanvasTexture {
  return mapsFor(body).color;
}

export function planetBump(body: VisualPlanet): CanvasTexture {
  return mapsFor(body).bump;
}

let glow: CanvasTexture | undefined;
export function sunGlow(): CanvasTexture {
  if (glow) return glow;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(128, 128, 6, 128, 128, 128);
  gradient.addColorStop(0, "rgba(255,240,200,0.95)");
  gradient.addColorStop(0.18, "rgba(255,200,110,0.45)");
  gradient.addColorStop(0.45, "rgba(255,140,50,0.16)");
  gradient.addColorStop(1, "rgba(255,100,30,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 256);
  glow = new CanvasTexture(canvas);
  glow.colorSpace = SRGBColorSpace;
  return glow;
}
