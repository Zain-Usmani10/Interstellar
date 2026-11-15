/**
 * Coordinate mapping (MAIN_BACKEND_FPGA_TASKS §12):
 * scientific (x, y, z) → Three.js (x, z, -y)
 * Applied once to planets, ship, and paths.
 */
export function sciToThree(
  x: number,
  y: number,
  z: number,
): [number, number, number] {
  return [x, z, -y];
}
