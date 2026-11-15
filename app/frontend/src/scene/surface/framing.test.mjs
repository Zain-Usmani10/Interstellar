import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';
import { surfaceCameraPose, surfaceAnchor } from './framing.ts';

test('perspective horizon spans width with requested sagitta at desktop aspects', () => {
  for (const aspect of [900 / 700, 16 / 9, 21 / 9]) {
    for (const radius of [0.4, 1, 3]) {
      const pose = surfaceCameraPose(radius, aspect, 0.16);
      const camera = new PerspectiveCamera(pose.fov, aspect, 0.001, 1000);
      camera.position.set(...pose.position);
      camera.lookAt(...pose.lookAt);
      camera.updateMatrixWorld();
      const d = pose.position[2];
      const z = radius * radius / d;
      const ring = Math.sqrt(radius * radius - z * z);
      const top = new Vector3(0, ring, z).project(camera);
      let edge;
      for (let i = 0; i <= 20000; i++) {
        const angle = i / 20000 * Math.PI / 2;
        const point = new Vector3(ring * Math.sin(angle), ring * Math.cos(angle), z).project(camera);
        if (point.x >= 1) { edge = point; break; }
      }
      assert.ok(edge);
      assert.ok(Math.abs(top.y + 0.25) < 1e-8);
      assert.ok(Math.abs((top.y - edge.y) / 2 - 0.16) < 0.001);
      for (const x of [-0.52, -0.04, 0.37, 0.78]) {
        const anchor = new Vector3(...surfaceAnchor(radius, aspect, 0.16, x));
        assert.ok(Math.abs(anchor.length() - radius) < 1e-8, 'pad must sit on sphere');
        const screen = anchor.clone().project(camera);
        assert.ok(Math.abs(screen.x - x) < 1e-8);
      }
    }
  }
});

test('invalid surface geometry is refused', () => {
  for (const args of [[0, 1], [1, 0], [NaN, 1], [1, 1, 0.9]]) {
    assert.throws(() => surfaceCameraPose(...args));
  }
});
