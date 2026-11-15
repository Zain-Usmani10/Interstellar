/**
 * Coordinate mapping (MAIN_BACKEND_FPGA_TASKS §12):
 * scientific (x, y, z) → Three.js (x, z, -y)
 * Applied once to planets, ship, and paths.
 */
export const AU_KM = 149_597_870.7;
export const UNITS_PER_AU = 10;

export function sciToThree(
  x: number,
  y: number,
  z: number,
): [number, number, number] {
  return [x, z, -y];
}

/** Use for every canonical plan/snapshot vector, which is in kilometres. */
export function kmToScene(position: readonly number[]): [number, number, number] {
  const scale = UNITS_PER_AU / AU_KM;
  return sciToThree(position[0] * scale, position[1] * scale, position[2] * scale);
}
