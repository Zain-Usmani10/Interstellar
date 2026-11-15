import type {
  FaultHistoryEntry,
  MissionPlan,
  MissionSnapshot,
} from "../api/missionTypes";
import { EngineerDrawer } from "./EngineerDrawer";
import { GlassStatus } from "./GlassStatus";
import type { LinkMode } from "../state/useCoreBridge";

type Props = {
  open: boolean;
  onToggle: () => void;
  linkMode: LinkMode;
  controllerSource: "fpga" | "simulator" | "unknown";
  snapshot: MissionSnapshot | null;
  lastError: string | null;
  destinationName: string;
  plan: MissionPlan | null;
  faultHistory: FaultHistoryEntry[];
  dataMode: string;
};

export function DetailsTray({
  open,
  onToggle,
  linkMode,
  controllerSource,
  snapshot,
  lastError,
  destinationName,
  plan,
  faultHistory,
  dataMode,
}: Props) {
  return (
    <div className="details-tray">
      <button
        type="button"
        className={open ? "details-toggle open" : "details-toggle"}
        aria-expanded={open}
        onClick={onToggle}
      >
        Details
      </button>
      {open ? (
        <div className="glass details-panel" role="region" aria-label="Engineer details">
          <GlassStatus
            linkMode={linkMode}
            controllerSource={controllerSource}
            snapshot={snapshot}
            lastError={lastError}
            destinationName={destinationName}
          />
          <EngineerDrawer
            plan={plan}
            snapshot={snapshot}
            faultHistory={faultHistory}
            dataMode={dataMode}
          />
        </div>
      ) : null}
    </div>
  );
}
