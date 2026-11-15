import type { MissionSnapshot } from "../api/missionTypes";
import { friendlyMissionLabel } from "../state/friendlyMission";
import type { LinkMode } from "../state/useCoreBridge";

type Props = {
  linkMode: LinkMode;
  controllerSource: "fpga" | "simulator" | "unknown";
  snapshot: MissionSnapshot | null;
  lastError: string | null;
  destinationName?: string | null;
};

function linkChip(
  linkMode: LinkMode,
  controllerSource: "fpga" | "simulator" | "unknown",
  snapshot: MissionSnapshot | null,
): { label: string; warn: boolean } {
  if (controllerSource !== "fpga" || linkMode !== "live") {
    return { label: "Simulator", warn: false };
  }
  const transport = snapshot?.link?.transport_state ?? "unknown";
  const age = snapshot?.link?.observed_age_ms;
  const stale =
    transport === "stale" ||
    transport === "disconnected" ||
    transport === "error" ||
    (typeof age === "number" && age > 1000);
  if (stale) return { label: "FPGA Link Lost", warn: true };
  return { label: "FPGA Link Live", warn: false };
}

export function GlassStatus({
  linkMode,
  controllerSource,
  snapshot,
  lastError,
  destinationName,
}: Props) {
  const chip = linkChip(linkMode, controllerSource, snapshot);

  return (
    <div className="glass-status" role="status" aria-label="Mission status">
      <p className="glass-mission">
        {friendlyMissionLabel(snapshot, destinationName)}
      </p>
      <div className="honesty-row">
        <span className={chip.warn ? "honesty warn" : "honesty"}>
          {chip.label}
        </span>
      </div>
      {lastError ? <p className="glass-error">{lastError}</p> : null}
    </div>
  );
}
