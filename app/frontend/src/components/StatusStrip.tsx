import type { MissionSnapshot } from "../api/missionTypes";
import type { LinkMode } from "../state/useCoreBridge";

type Props = {
  linkMode: LinkMode;
  controllerLabel: string;
  dataMode: string;
  inputSourceLabel: string;
  snapshot: MissionSnapshot | null;
  lastError: string | null;
};

export function StatusStrip({
  linkMode,
  controllerLabel,
  dataMode,
  inputSourceLabel,
  snapshot,
  lastError,
}: Props) {
  const transport = snapshot?.link?.transport_state ?? "unknown";
  const age = snapshot?.link?.observed_age_ms;
  const stale =
    transport === "stale" ||
    (typeof age === "number" && age > 1000) ||
    linkMode !== "live";
  const delayDemo = snapshot?.link?.delay_demo_s;
  const delayPhysical = snapshot?.link?.delay_physical_s;
  const state = snapshot?.state ?? "IDLE";

  return (
    <div className="status-strip" role="status" aria-label="Mission indicators">
      <span className={linkMode === "live" ? "pill" : "pill mock"}>
        link: {stale ? "stale" : linkMode}
      </span>
      <span className="pill">controller: {controllerLabel}</span>
      <span className="pill">NASA/data: {dataMode}</span>
      <span className="pill">input: {inputSourceLabel}</span>
      <span className="pill">
        freshness: {transport}
        {age === null || age === undefined ? "" : ` · ${age} ms`}
      </span>
      <span className="pill">mission: {state}</span>
      <span className="pill">
        delay: demo {delayDemo ?? "n/a"}s / physical {delayPhysical ?? "n/a"}s
      </span>
      {lastError ? <span className="pill mock">err: {lastError}</span> : null}
    </div>
  );
}
