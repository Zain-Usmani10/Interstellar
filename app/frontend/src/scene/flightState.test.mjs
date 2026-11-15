import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { kmToScene, AU_KM } from "./axes.ts";
import {
  flightView,
  routePoints,
  betweenReceived,
  splitRouteAtCraft,
} from "./flightState.ts";

const fixture = (name) =>
  JSON.parse(
    readFileSync(
      new URL(`../../../contracts/fixtures/${name}.json`, import.meta.url),
      "utf8",
    ),
  );
const coast = fixture("mission_snapshot_running_coast");
const plan = fixture("mission_plan_earth_mars");

test("kilometres use one AU scale and one axis mapping", () => {
  kmToScene([AU_KM, 2 * AU_KM, 3 * AU_KM]).forEach((value, i) =>
    assert.ok(Math.abs(value - [10, 30, -20][i]) < 1e-12),
  );
});
test("RUNNING without departure cannot launch", () => {
  assert.equal(flightView({ ...coast, executed_mask: 0 }, plan).mode, "docked");
});

test("unknown spacecraft phase never presents a known flight position", () => {
  assert.equal(flightView({ ...coast, spacecraft: { ...coast.spacecraft, phase: "unknown" } }, plan).mode, "unavailable");
});
test("actual snapshot controls the position; route does not animate the rocket", () => {
  assert.deepEqual(
    flightView(coast, plan).position,
    kmToScene(coast.spacecraft.r_km),
  );
  assert.deepEqual(
    routePoints(plan),
    plan.nominal_path.map((p) => kmToScene(p.r_km)),
  );
  assert.deepEqual(routePoints(null), []);
});
test("capture requires capture phase, event and successful controller outcome", () => {
  const complete = fixture("mission_snapshot_complete");
  assert.equal(flightView(complete, plan).mode, "captured");
  assert.notEqual(
    flightView({ ...complete, executed_mask: 1 }, plan).mode,
    "captured",
  );
  assert.notEqual(
    flightView(
      { ...complete, spacecraft: { ...complete.spacecraft, phase: "coast" } },
      plan,
    ).mode,
    "captured",
  );
});
test("SAFE and ABORTED retain reported coast positions; no fake arrival", () => {
  for (const state of ["SAFE", "ABORTED"]) {
    const view = flightView({ ...coast, state }, plan);
    assert.equal(view.mode, "uncaptured");
    assert.deepEqual(view.position, kmToScene(coast.spacecraft.r_km));
  }
});
test("stale telemetry stays labelled; plan mismatch suppresses the vehicle", () => {
  assert.equal(
    flightView(
      { ...coast, link: { ...coast.link, transport_state: "stale" } },
      plan,
    ).stale,
    true,
  );
  assert.equal(
    flightView({ ...coast, plan_id: "another-plan" }, plan).mode,
    "unavailable",
  );
});
test("easing cannot overshoot either received point", () => {
  const a = [1, 2, 3],
    b = [4, 5, 6];
  assert.deepEqual(betweenReceived(a, b, -1), a);
  assert.deepEqual(betweenReceived(a, b, 2), b);
});

test("splitRouteAtCraft: no craft → all remaining, empty flown", () => {
  const pts = [
    [0, 0, 0],
    [10, 0, 0],
    [20, 0, 0],
  ];
  const { flown, remaining } = splitRouteAtCraft(pts, null);
  assert.deepEqual(flown, []);
  assert.deepEqual(remaining, pts);
});

test("splitRouteAtCraft: craft on a sample → solid up to it, dotted after", () => {
  const pts = [
    [0, 0, 0],
    [10, 0, 0],
    [20, 0, 0],
  ];
  const { flown, remaining } = splitRouteAtCraft(pts, [10, 0, 0]);
  assert.ok(flown.length >= 2);
  assert.deepEqual(flown[flown.length - 1], [10, 0, 0]);
  assert.deepEqual(remaining[0], [10, 0, 0]);
  assert.deepEqual(remaining[remaining.length - 1], [20, 0, 0]);
});

test("splitRouteAtCraft: craft mid-segment inserts the split point", () => {
  const pts = [
    [0, 0, 0],
    [10, 0, 0],
  ];
  const { flown, remaining } = splitRouteAtCraft(pts, [4, 0, 0]);
  assert.equal(flown.length, 2);
  assert.ok(Math.abs(flown[1][0] - 4) < 1e-9);
  assert.equal(remaining.length, 2);
  assert.ok(Math.abs(remaining[0][0] - 4) < 1e-9);
  assert.deepEqual(remaining[1], [10, 0, 0]);
});
