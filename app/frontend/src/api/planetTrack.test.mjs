import assert from "node:assert/strict";
import { test } from "node:test";
import { interpolateTrack } from "./planetTrackMath.ts";
import { jdTdbToUtcIso, utcIsoToJdTdb } from "./jd.ts";

test("interpolateTrack lerps between epochs and refuses to extrapolate", () => {
  const epochs = [100, 110, 120];
  const planets = [
    {
      body_id: "399",
      r_km: [
        [0, 0, 0],
        [10, 0, 0],
        [20, 0, 0],
      ],
    },
  ];
  const mid = interpolateTrack(epochs, planets, 105);
  assert.deepEqual(mid?.[0].r_km, [5, 0, 0]);
  assert.equal(interpolateTrack(epochs, planets, 99), null);
  assert.equal(interpolateTrack(epochs, planets, 121), null);
});

test("jd helpers round-trip within a second", () => {
  const iso = "2028-11-21T00:00:00Z";
  const jd = utcIsoToJdTdb(iso);
  assert.ok(jd != null);
  const back = jdTdbToUtcIso(jd);
  assert.equal(Math.abs(Date.parse(back) - Date.parse(iso)) < 2000, true);
});
