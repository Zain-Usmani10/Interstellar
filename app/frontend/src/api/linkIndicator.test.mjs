import assert from "node:assert/strict";
import { test } from "node:test";
import { isLinkIndicator, linkLightLabel } from "./linkIndicator.ts";

test("isLinkIndicator accepts only backend enum values", () => {
  assert.equal(isLinkIndicator("active"), true);
  assert.equal(isLinkIndicator("inactive"), true);
  assert.equal(isLinkIndicator("reconnecting"), true);
  assert.equal(isLinkIndicator("connected"), false);
  assert.equal(isLinkIndicator(undefined), false);
});

test("linkLightLabel prefixes controller and exact state wording", () => {
  assert.equal(
    linkLightLabel("active", "fpga"),
    "FPGA · Link Active",
  );
  assert.equal(
    linkLightLabel("inactive", "simulator"),
    "Simulator · Link Inactive",
  );
  assert.equal(
    linkLightLabel("reconnecting", "fpga"),
    "FPGA · Reconnecting",
  );
  assert.equal(
    linkLightLabel("active", "unknown"),
    "Simulator · Link Active",
  );
});
