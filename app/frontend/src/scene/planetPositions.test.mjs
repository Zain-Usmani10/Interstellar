import { test } from "node:test";
import assert from "node:assert/strict";
import { positionQuery, validatePositions, PositionRequest } from "./planetPositions.ts";

const reply = (jd = 2461359.5) => ({
  epoch_jd_tdb: jd, date_utc: "2026-11-15T00:00:00Z", data_mode: "nasa_cached",
  frame: { center: "500@10", ref_system: "ICRF", ref_plane: "ECLIPTIC", units: "KM-S", time_scale: "TDB" },
  planets: ["199", "299", "399", "499", "599", "699", "799", "899"].map(body_id => ({body_id, r_km: [1, 2, 3]})),
});
const plan = { departure: { jd_tdb: 2461359.5 } };

test("scene query uses the selected departure, confirmed date or labelled blackout date, never wall time", () => {
  assert.equal(positionQuery(undefined, plan), "jd_tdb=2461359.5");
  const snapshot = { date_utc: "2026-11-15T00:00:00Z", link: { blackout: false }, estimate: { date_utc: "2027-01-01T00:00:00Z" } };
  assert.equal(new URLSearchParams(positionQuery(undefined, plan, snapshot)).get("date_utc"), snapshot.date_utc);
  snapshot.link.blackout = true;
  assert.equal(new URLSearchParams(positionQuery(undefined, plan, snapshot)).get("date_utc"), snapshot.estimate.date_utc);
  assert.equal(positionQuery(null, plan, snapshot), null);
  assert.equal(positionQuery(undefined, plan, { link: {} }), null);
});

test("requires eight distinct finite vectors and the canonical frame", () => {
  assert.equal(validatePositions(reply()).planets.length, 8);
  for (const edit of [r => r.planets.pop(), r => r.planets[0].r_km[0] = NaN,
    r => r.planets[0].body_id = "299", r => r.frame.units = "AU-D", r => r.frame.center = "500@399",
    r => r.data_mode = "synthetic", r => r.date_utc = "invalid"]) {
    const r = reply(); edit(r); assert.throws(() => validatePositions(r));
  }
});

test("late requests and late failures cannot overwrite the current date", async () => {
  const requests = new PositionRequest();
  let resolveOld, rejectOld, oldSignal;
  const old = requests.load("jd_tdb=2461359.5", (_, init) => {
    oldSignal = init.signal;
    return new Promise(resolve => { resolveOld = resolve; });
  });
  const current = await requests.load("jd_tdb=2461360.5", async () => reply(2461360.5));
  assert.equal(oldSignal.aborted, true);
  resolveOld(reply());
  assert.equal(await old, null);
  assert.equal(current.data.epoch_jd_tdb, 2461360.5);
  const failed = requests.load("jd_tdb=2461359.5", () => new Promise((_, reject) => { rejectOld = reject; }));
  requests.cancel(); rejectOld(new Error("late network error"));
  assert.equal(await failed, null);
});

test("out-of-track, malformed and wrong-date responses fail without invented positions", async () => {
  const requests = new PositionRequest();
  assert.match((await requests.load("jd_tdb=1", async () => { throw new Error("DATE_OUTSIDE_TRACK"); })).error, /OUTSIDE/);
  assert.match((await requests.load("jd_tdb=1", async () => reply())).error, /different scene date/);
  assert.ok((await requests.load("jd_tdb=1", async () => ({}))).error);
});
