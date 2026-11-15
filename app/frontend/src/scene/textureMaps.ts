import { SRGBColorSpace, Texture, TextureLoader } from "three";

const loader = new TextureLoader();
const cache = new Map<string, Texture>();

const PLANET_MAP: Record<string, string> = {
  Mercury: "/textures/2k_mercury.jpg",
  Venus: "/textures/2k_venus_surface.jpg",
  Earth: "/textures/2k_earth_daymap.jpg",
  Mars: "/textures/2k_mars.jpg",
  Jupiter: "/textures/2k_jupiter.jpg",
  Saturn: "/textures/2k_saturn.jpg",
  Uranus: "/textures/2k_uranus.jpg",
  Neptune: "/textures/2k_neptune.jpg",
};

export function loadPlanetMap(name: string): Texture | null {
  const url = PLANET_MAP[name];
  if (!url) return null;
  const hit = cache.get(url);
  if (hit) return hit;
  try {
    const tex = loader.load(url);
    tex.colorSpace = SRGBColorSpace;
    tex.anisotropy = 8;
    cache.set(url, tex);
    return tex;
  } catch {
    return null;
  }
}

export function loadTexture(url: string): Texture {
  const hit = cache.get(url);
  if (hit) return hit;
  const tex = loader.load(url);
  tex.colorSpace = SRGBColorSpace;
  cache.set(url, tex);
  return tex;
}
