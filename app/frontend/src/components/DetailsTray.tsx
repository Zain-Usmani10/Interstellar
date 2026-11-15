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
  live: boolean;
  busy: boolean;
  blackout: boolean;
  simFaultsEnabled: boolean;
  onBlackoutStart: () => void;
  onBlackoutEnd: () => void;
  onResetFleet: () => void;
  onFaultSingle: () => void;
  onFaultDivergence: () => void;
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
  live,
  busy,
  blackout,
  simFaultsEnabled,
  onBlackoutStart,
  onBlackoutEnd,
  onResetFleet,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  const canStartBlackout =
    live && !blackout && snapshot?.state === "RUNNING";
  const canEndBlackout = live && blackout;

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
        <div
          className="glass details-panel"
          role="region"
          aria-label="Engineer details"
        >
          <GlassStatus
            linkMode={linkMode}
            controllerSource={controllerSource}
            snapshot={snapshot}
            lastError={lastError}
            destinationName={destinationName}
          />
          <div className="details-ops" aria-label="Operator controls">
            {blackout ? (
              <button
                type="button"
                className="blackout-btn end"
                disabled={busy || !canEndBlackout}
                onClick={onBlackoutEnd}
              >
                End blackout
              </button>
            ) : (
              <button
                type="button"
                className="blackout-btn"
                disabled={busy || !canStartBlackout}
                title="RUNNING only"
                onClick={onBlackoutStart}
              >
                Start blackout
              </button>
            )}
            <button
              type="button"
              disabled={busy || !live || blackout}
              onClick={onResetFleet}
            >
              Reset fleet
            </button>
            {simFaultsEnabled ? (
              <>
                <button
                  type="button"
                  disabled={busy || blackout || !live}
                  onClick={onFaultSingle}
                >
                  Sim fault
                </button>
                <button
                  type="button"
                  disabled={busy || blackout || !live}
                  onClick={onFaultDivergence}
                >
                  Divergence
                </button>
              </>
            ) : null}
          </div>
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
