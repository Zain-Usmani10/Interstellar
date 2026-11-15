import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { countdownProgress, estimatePosition, dockedShuttles, MOCK_FLEET } from "./dockState.ts";
import { flightView } from "./flightState.ts";
const fixture = name => JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}.json`, import.meta.url), "utf8"));
const plan = fixture("mission_plan_earth_mars");
plan.ticks = { departure_tick: 500, arrival_tick: 6500, end_tick: 6800 };
const coast = fixture("mission_snapshot_running_coast");

test("countdown follows confirmed ticks, stops on blackout, never starts from mismatched plan", () => {
  const snapshot = { ...coast, tick: 250, executed_mask: 0 };
  assert.equal(countdownProgress(snapshot, plan), 0.5);
  assert.equal(countdownProgress({ ...snapshot, link: { ...snapshot.link, blackout: true } }, plan), 0);
  assert.equal(countdownProgress({ ...snapshot, plan_id: "wrong" }, plan), 0);
  assert.equal(countdownProgress({ ...snapshot, executed_mask: 1 }, plan), 0);
});

test("estimated capture cannot land the confirmed shuttle", () => {
  const snapshot = { ...coast, link: { ...coast.link, blackout: true },
    estimate: { tick: 6500, epoch_jd_tdb: 2461500, spacecraft: { phase: "captured", r_km: [1, 2, 3] } } };
  assert.ok(estimatePosition(snapshot, plan));
  assert.equal(flightView(snapshot, plan).mode, "coast");
  assert.equal(estimatePosition({ ...snapshot, link: { ...snapshot.link, blackout: false } }, plan), null);
  assert.equal(estimatePosition({ ...snapshot, plan_id: "wrong" }, plan), null);
});

test("fleet markers require docked inventory and remove the departed mission shuttle", () => {
  assert.equal(dockedShuttles(MOCK_FLEET, "399").length, 2);
  assert.equal(dockedShuttles(MOCK_FLEET, "799").length, 0);
  assert.equal(dockedShuttles(MOCK_FLEET, "399", { ...coast, shuttle_id: "earth-standard" }).length, 1);
  assert.equal(dockedShuttles([], "399").length, 0);
});
