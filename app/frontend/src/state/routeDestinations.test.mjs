import assert from "node:assert/strict";
import { test } from "node:test";
import {
  destinationsWithRoute,
  originsWithRoute,
} from "./routeDestinations.ts";

test("destinationsWithRoute lists only stored destinations from an origin", () => {
  const summaries = [
    { plan_id: "a", origin_body_id: "399", destination_body_id: "499" },
    { plan_id: "b", origin_body_id: "399", destination_body_id: "299" },
    { plan_id: "c", origin_body_id: "499", destination_body_id: "399" },
  ];
  const set = destinationsWithRoute(summaries, "399");
  assert.equal(set.has("499"), true);
  assert.equal(set.has("299"), true);
  assert.equal(set.has("599"), false);
});

test("originsWithRoute lists inbound origins", () => {
  const summaries = [
    { plan_id: "a", origin_body_id: "399", destination_body_id: "499" },
    { plan_id: "b", origin_body_id: "299", destination_body_id: "499" },
  ];
  const set = originsWithRoute(summaries, "499");
  assert.equal(set.has("399"), true);
  assert.equal(set.has("299"), true);
  assert.equal(set.has("199"), false);
});
