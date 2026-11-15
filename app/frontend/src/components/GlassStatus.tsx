import type { MissionSnapshot } from "../api/missionTypes";
import { friendlyMissionLabel } from "../state/friendlyMission";
import type { LinkMode } from "../state/useCoreBridge";

type Props = {
  linkMode: LinkMode;
  controllerLabel: string;
  dataMode: string;
  snapshot: MissionSnapshot | null;
  lastError: string | null;
  destinationName?: string | null;
  scenicActive?: boolean;
};

export function GlassStatus({
  linkMode,
  controllerLabel,
  dataMode,
  snapshot,
  lastError,
  destinationName,
  scenicActive,
}: Props) {
  const transport = snapshot?.link?.transport_state ?? "unknown";
  const stale =
    transport === "stale" ||
    linkMode !== "live" ||
    (typeof snapshot?.link?.observed_age_ms === "number" &&
      snapshot.link.observed_age_ms > 1000);

  return (
    <div className="glass-status" role="status" aria-label="Mission status">
      <p className="glass-mission">
        {friendlyMissionLabel(snapshot, destinationName, scenicActive)}
      </p>
      <div className="honesty-row">
        <span className="honesty">{controllerLabel}</span>
        <span className="honesty">NASA {dataMode}</span>
        <span className={stale && !scenicActive ? "honesty warn" : "honesty"}>
          link {scenicActive ? "illustrative" : stale ? "stale" : "live"}
        </span>
      </div>
      {lastError ? <p className="glass-error">{lastError}</p> : null}
    </div>
  );
}
