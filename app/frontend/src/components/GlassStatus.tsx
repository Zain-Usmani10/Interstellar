import type { MissionSnapshot } from "../api/missionTypes";
import { friendlyMissionLabel } from "../state/friendlyMission";

type Props = {
  snapshot: MissionSnapshot | null;
  lastError: string | null;
  destinationName?: string | null;
};

export function GlassStatus({
  snapshot,
  lastError,
  destinationName,
}: Props) {
  return (
    <div className="glass-status" role="status" aria-label="Mission status">
      <p className="glass-mission">
        {friendlyMissionLabel(snapshot, destinationName)}
      </p>
      {lastError ? <p className="glass-error">{lastError}</p> : null}
    </div>
  );
}
