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
  /** §18.7 — enabled only in RUNNING after contracts 1.2.0 */
  blackoutActive?: boolean;
  canStartBlackout?: boolean;
  canEndBlackout?: boolean;
  onBlackoutStart?: () => void;
  onBlackoutEnd?: () => void;
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
  onReset: () => void;
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
  blackoutActive = false,
  canStartBlackout = false,
  canEndBlackout = false,
  onBlackoutStart,
  onBlackoutEnd,
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onReset,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  const step = guidedStep(snapshot);
  const locked = busy;

  const primary =
    step === "reset"
      ? {
          label: "Start over",
          hint: "Clears the aborted/finished mission so you can launch again",
          enabled: true,
          run: onReset,
        }
      : step === "prepare"
        ? {
            label: "Prepare mission",
            hint: hasPlan
              ? `Loads your ${routeLabel} route onto the controller`
              : "Pick a pair with an available MissionPlan first",
            enabled: live && hasPlan && (gates.canCreate || gates.canUpload),
            run: onPrepare,
          }
        : step === "arm"
          ? {
              label: "Arm",
              hint: "Controller must be LOADED",
              enabled: live && gates.canArm,
              run: onArm,
            }
          : step === "launch"
            ? {
                label: "Launch",
                hint: "Starts only when the controller is ARMED",
                enabled: live && gates.canStart,
                run: onLaunch,
              }
            : {
                label: "Mission under way",
                hint: "Follow the live snapshot",
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
        disabled={locked || !primary.enabled}
        onClick={primary.run}
      >
        {busy ? "Working…" : primary.label}
      </button>
      <p className="guided-hint">{primary.hint}</p>
      <div className="guided-secondary">
        <button
          type="button"
          className="abort-btn"
          disabled={locked || blackoutActive || !(live && gates.canAbort)}
          onClick={onAbort}
        >
          Abort
        </button>
        {blackoutActive ? (
          <button
            type="button"
            className="blackout-btn end"
            disabled={locked || !canEndBlackout}
            title={
              canEndBlackout
                ? "End blackout early"
                : "Awaits contracts 1.2.0 blackout_end"
            }
            onClick={onBlackoutEnd}
          >
            End blackout
          </button>
        ) : (
          <button
            type="button"
            className="blackout-btn"
            disabled={locked || !canStartBlackout}
            title={
              canStartBlackout
                ? "Start blackout (RUNNING only)"
                : "Awaits contracts 1.2.0 · RUNNING only"
            }
            onClick={onBlackoutStart}
          >
            Start blackout
          </button>
        )}
        <button type="button" disabled={locked || blackoutActive} onClick={onReset}>
          Start over
        </button>
        {simFaultsEnabled ? (
          <>
            <button type="button" disabled={locked || !live} onClick={onFaultSingle}>
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
