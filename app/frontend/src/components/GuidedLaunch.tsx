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
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
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
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  const step = guidedStep(snapshot);
  const locked = !live || busy;

  const primary =
    step === "prepare"
      ? {
          label: "Prepare mission",
          hint: "Loads your route onto the controller",
          enabled: hasPlan && (gates.canCreate || gates.canUpload),
          run: onPrepare,
        }
      : step === "arm"
        ? {
            label: "Arm",
            hint: "Controller must be LOADED",
            enabled: gates.canArm,
            run: onArm,
          }
        : step === "launch"
          ? {
              label: "Launch",
              hint: "Starts only when the controller is ARMED",
              enabled: gates.canStart,
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
        <span className={step === "arm" ? "on" : step === "launch" || step === "done" ? "done" : ""}>
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
          disabled={locked || !gates.canAbort}
          onClick={onAbort}
        >
          Abort
        </button>
        {simFaultsEnabled ? (
          <>
            <button type="button" disabled={locked} onClick={onFaultSingle}>
              Sim fault
            </button>
            <button type="button" disabled={locked} onClick={onFaultDivergence}>
              Divergence
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
