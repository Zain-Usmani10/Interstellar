/** Development-only manual fixture viewer. Not imported by the application. */
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { OrbitScene } from "./OrbitScene";
import type { ScenePlan, SceneSnapshot } from "./types";
import type { PlanetTargetId } from "../api/types";
import planRaw from "../../../contracts/fixtures/mission_plan_earth_mars.json?raw";
import coastRaw from "../../../contracts/fixtures/mission_snapshot_running_coast.json?raw";
import capturedRaw from "../../../contracts/fixtures/mission_snapshot_complete.json?raw";

const plan = JSON.parse(planRaw) as ScenePlan;
const coast = JSON.parse(coastRaw) as SceneSnapshot;
const captured = JSON.parse(capturedRaw) as SceneSnapshot;
plan.ticks = { departure_tick: 500, arrival_tick: 6500, end_tick: 6800 };
const cases: Record<string, SceneSnapshot | null> = {
  Preview: null,
  Docked: { ...coast, executed_mask: 0, spacecraft: { ...coast.spacecraft, phase: "at_origin" } },
  Countdown: { ...coast, tick: 250, executed_mask: 0 },
  Blackout: { ...coast, link: { ...coast.link, blackout: true }, estimate: { tick: 6400, epoch_jd_tdb: 2461600, spacecraft: { phase: "coast", r_km: captured.spacecraft.r_km } } },
  Coast: coast,
  Captured: captured,
  SAFE: { ...coast, state: "SAFE", spacecraft: { ...coast.spacecraft, phase: "uncaptured_coast" } },
  ABORTED: { ...coast, state: "ABORTED", outcome: "aborted" },
  Stale: { ...coast, link: { ...coast.link, transport_state: "disconnected" } },
};
export function Preview() {
  const [name, setName] = useState("Preview");
  const [focus, setFocus] = useState<string | null>(null);
  const [selected, setSelected] = useState<PlanetTargetId | null>(null);
  return <>
    <div style={{ position: "relative", zIndex: 30, background: "#e7eef4", color: "#152536", padding: 12, font: "13px monospace" }}>
      FIXTURE VIEWER — no backend, hardware or live mission. {Object.keys(cases).map(key => <button key={key} onClick={() => setName(key)}>{key}</button>)}
      <button onClick={() => setSelected("planet.399")}>Earth</button>
      <button onClick={() => setSelected("planet.499")}>Mars</button>
      <button onClick={() => setSelected(null)}>Overview</button>
    </div>
    <div style={{ position: "relative", height: "calc(100vh - 70px)" }}><OrbitScene selectedId={selected} onSelect={setSelected} plan={plan} snapshot={cases[name]} fetchPositions={false} mockFleet focusName={focus} onFocusName={setFocus} /></div>
  </>;
}
createRoot(document.getElementById("root")!).render(<Preview />);
