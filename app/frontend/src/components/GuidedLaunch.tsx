import type { MissionSnapshot } from "../api/missionTypes";
import { guidedStep } from "../state/friendlyMission";

type Gates = {
  canCreate: boolean;
  canUpload: boolean;
  canArm: boolean;
  canStart: boolean;
  canAbort: boolean;
  canClear: boolean;
};

type Props = {
  live: boolean;
  busy: boolean;
  hasPlan: boolean;
  snapshot: MissionSnapshot | null;
  gates: Gates;
  simFaultsEnabled: boolean;
  routeLabel: string;
  blackoutActive: boolean;
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
  onReset: () => void;
  onBlackoutStart: () => void;
  onBlackoutEnd: () => void;
  onResetFleet: () => void;
  onFaultSingle: () => void;
  onFaultDivergence: () => void;
};

export function GuidedLaunch({
  live,
  busy,
  hasPlan,
  snapshot,
  gates,
  simFaultsEnabled,
  routeLabel,
  blackoutActive,
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onReset,
  onBlackoutStart,
  onBlackoutEnd,
  onResetFleet,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  const step = guidedStep(snapshot);
  const locked = busy || blackoutActive;
  const canStartBlackout =
    live && !blackoutActive && snapshot?.state === "RUNNING";
  const canEndBlackout = live && blackoutActive;

  const primary =
    step === "reset"
      ? {
          label: "Start over",
          hint: "Clears the aborted/finished mission so you can launch again",
          enabled: !blackoutActive,
          run: onReset,
        }
      : step === "prepare"
        ? {
            label: "Prepare mission",
            hint: hasPlan
              ? `Loads your ${routeLabel} route onto the controller`
              : "Pick a docked shuttle and destination with a route first",
            enabled:
              live &&
              hasPlan &&
              !blackoutActive &&
              (gates.canCreate || gates.canUpload),
            run: onPrepare,
          }
        : step === "arm"
          ? {
              label: "Arm",
              hint: "Controller must be LOADED",
              enabled: live && gates.canArm && !blackoutActive,
              run: onArm,
            }
          : step === "launch"
            ? {
                label: "Launch",
                hint: "Starts only when the controller is ARMED",
                enabled: live && gates.canStart && !blackoutActive,
                run: onLaunch,
              }
            : {
                label: blackoutActive
                  ? "Blackout — estimate only"
                  : "Mission under way",
                hint: blackoutActive
                  ? "Contact lost; waiting for sync at arrival"
                  : "Follow the live snapshot",
                enabled: false,
                run: () => undefined,
              };

  return (
    <div className="guided-launch" aria-label="Mission controls">
      <div className="step-rail" aria-hidden="true">
        <span className={step === "prepare" ? "on" : "done"}>Prepare</span>
        <span
          className={
            step === "arm"
              ? "on"
              : step === "launch" || step === "done"
                ? "done"
                : ""
          }
        >
          Arm
        </span>
        <span className={step === "launch" ? "on" : step === "done" ? "done" : ""}>
          Launch
        </span>
      </div>
      <button
        type="button"
        className="primary-launch"
        disabled={busy || !primary.enabled}
        onClick={primary.run}
      >
        {busy ? "Working…" : primary.label}
      </button>
      <p className="guided-hint">{primary.hint}</p>
      <div className="guided-secondary">
        <button
          type="button"
          className="abort-btn"
          disabled={locked || !(live && gates.canAbort)}
          onClick={onAbort}
        >
          Abort
        </button>
        {blackoutActive ? (
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
        <button type="button" disabled={locked} onClick={onReset}>
          Start over
        </button>
        <button
          type="button"
          disabled={busy || !live || blackoutActive}
          title="Restore the starting fleet (operator)"
          onClick={onResetFleet}
        >
          Reset fleet
        </button>
        {simFaultsEnabled ? (
          <>
            <button
              type="button"
              disabled={locked || !live}
              onClick={onFaultSingle}
            >
              Sim fault
            </button>
            <button
              type="button"
              disabled={locked || !live}
              onClick={onFaultDivergence}
            >
              Divergence
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
