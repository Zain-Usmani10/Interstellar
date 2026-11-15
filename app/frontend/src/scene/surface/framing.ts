export type SurfaceVector = [number, number, number];
export type SurfacePose = { position: SurfaceVector; lookAt: SurfaceVector; fov: number };
const FOV = 35;
const PEAK = -0.25;

function ray(aspect: number, tilt: number, x: number, y: number): SurfaceVector {
  const t = Math.tan(FOV * Math.PI / 360);
  return [x * aspect * t, Math.sin(tilt) + y * t * Math.cos(tilt),
    -Math.cos(tilt) + y * t * Math.sin(tilt)];
}

function discriminant(distance: number, aspect: number, tilt: number, x: number, y: number) {
  const v = ray(aspect, tilt, x, y);
  return (distance * v[2]) ** 2 - v.reduce((s, n) => s + n * n, 0) * (distance * distance - 1);
}

/** Local planet coordinates. Add the planet centre to both vectors in the camera rig.
 * Sagitta is a fraction of viewport HEIGHT, measured peak to left/right edge.
 * Solve the perspective sphere silhouette, rather than flattening the planet.
 */
export function surfaceCameraPose(radius: number, aspect: number, sagitta = 0.16): SurfacePose {
  if (!Number.isFinite(radius) || radius <= 0 || !Number.isFinite(aspect) || aspect <= 0
      || !Number.isFinite(sagitta) || sagitta < 0.08 || sagitta > 0.3) {
    throw new Error("Surface framing needs positive radius/aspect and sagitta 0.08..0.3");
  }
  const t = Math.tan(FOV * Math.PI / 360);
  let low = 1.000001, high = 100;
  for (let i = 0; i < 60; i++) {
    const d = (low + high) / 2;
    const tilt = Math.asin(1 / d) - Math.atan(PEAK * t);
    if (discriminant(d, aspect, tilt, 1, PEAK - 2 * sagitta) > 0) low = d;
    else high = d;
  }
  const distance = (low + high) / 2;
  const tilt = Math.asin(1 / distance) - Math.atan(PEAK * t);
  return { position: [0, 0, distance * radius],
    lookAt: [0, radius * Math.sin(tilt), radius * (distance - Math.cos(tilt))], fov: FOV };
}

/** A point on the near surface just below its silhouette at horizontal NDC x. */
export function surfaceAnchor(radius: number, aspect: number, sagitta: number, x: number): SurfaceVector {
  const pose = surfaceCameraPose(radius, aspect, sagitta);
  const d = pose.position[2] / radius;
  const tilt = Math.atan2(pose.lookAt[1], pose.position[2] - pose.lookAt[2]);
  let low = -0.98, high = PEAK + 0.05;
  for (let i = 0; i < 50; i++) {
    const y = (low + high) / 2;
    if (discriminant(d, aspect, tilt, x, y) > 0) low = y; else high = y;
  }
  const v = ray(aspect, tilt, x, (low + high) / 2 - 0.035);
  const a = v.reduce((s, n) => s + n * n, 0);
  const b = d * v[2];
  const distance = (-b - Math.sqrt(b * b - a * (d * d - 1))) / a;
  return [radius * v[0] * distance, radius * v[1] * distance, radius * (d + v[2] * distance)];
}
