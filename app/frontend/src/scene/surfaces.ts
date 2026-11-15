import { CanvasTexture, SRGBColorSpace } from "three";
import type { VisualPlanet } from "./planets";

// Original procedural illustration. No external textures, fonts or reference assets.
const surfaces = new Map<string, CanvasTexture>();
export function planetTexture(body: VisualPlanet): CanvasTexture {
  const existing = surfaces.get(body.name);
  if (existing) return existing;
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = body.color;
  ctx.fillRect(0, 0, 512, 256);
  for (let y = 0; y < 256; y += 2)
    for (let x = 0; x < 512; x += 2) {
      const lon = (x / 512) * Math.PI * 2,
        lat = (y / 256) * Math.PI;
      const field =
        Math.sin(lon * 3 + Math.sin(lat * 5)) * Math.cos(lat * 4) +
        0.45 * Math.sin(lon * 7 - lat * 9) +
        0.2 * Math.cos(lon * 13 + lat * 11);
      if (body.surface === "earth") {
        if (field > 0.43 && Math.sin(lat) > 0.2) {
          ctx.fillStyle = field > 0.95 ? "#d3cba2" : body.accent;
          ctx.fillRect(x, y, 2, 2);
        }
        if (Math.sin(lat) < 0.14) {
          ctx.fillStyle = "#dbebea";
          ctx.fillRect(x, y, 2, 2);
        }
        if (Math.sin(lon * 8 + lat * 15 + field * 2) > 0.89) {
          ctx.fillStyle = "rgba(235,248,250,.28)";
          ctx.fillRect(x, y, 2, 2);
        }
      } else {
        const band =
          body.surface === "gas"
            ? Math.sin(lat * 33 + Math.sin(lon * 4) * 0.4)
            : field;
        ctx.globalAlpha = 0.12 + Math.abs(band) * 0.22;
        ctx.fillStyle = band > 0 ? body.accent : "#fff5d8";
        ctx.fillRect(x, y, 2, 2);
      }
    }
  ctx.globalAlpha = 1;
  if (body.surface === "rock")
    for (let i = 0; i < 38; i++) {
      ctx.beginPath();
      ctx.arc(
        (i * 137.5) % 512,
        24 + ((i * 71.3) % 208),
        2 + (i % 5) * 1.8,
        0,
        Math.PI * 2,
      );
      ctx.fillStyle = "rgba(35,21,20,.16)";
      ctx.fill();
      ctx.strokeStyle = "rgba(255,221,185,.18)";
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  surfaces.set(body.name, texture);
  return texture;
}

let glow: CanvasTexture | undefined;
export function sunGlow(): CanvasTexture {
  if (glow) return glow;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d")!,
    gradient = ctx.createRadialGradient(64, 64, 8, 64, 64, 64);
  gradient.addColorStop(0, "rgba(255,223,157,.65)");
  gradient.addColorStop(0.25, "rgba(255,159,70,.24)");
  gradient.addColorStop(1, "rgba(255,138,50,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  glow = new CanvasTexture(canvas);
  glow.colorSpace = SRGBColorSpace;
  return glow;
}
