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
  destinationName: string | null;
  scenicActive: boolean;
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
  onReset: () => void;
  onScenic: () => void;
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
  destinationName,
  scenicActive,
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onReset,
  onScenic,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  const step = guidedStep(snapshot, {
    scenicDestination: destinationName,
    scenicActive,
  });
  const locked = busy;

  const primary =
    step === "reset"
      ? {
          label: "Start over",
          hint: "Clears the aborted/finished mission so you can launch again",
          enabled: true,
          run: onReset,
        }
      : step === "scenic"
        ? {
            label: `Fly to ${destinationName}`,
            hint: "Illustrative scenic flight — not a controller mission",
            enabled: true,
            run: onScenic,
          }
        : step === "prepare"
          ? {
              label: "Prepare mission",
              hint: "Loads your Earth→Mars route onto the controller",
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
                  label: scenicActive
                    ? "Scenic flight running"
                    : "Mission under way",
                  hint: scenicActive
                    ? "Illustrative path — labeled on the scene"
                    : "Follow the live snapshot",
                  enabled: false,
                  run: () => undefined,
                };

  return (
    <div className="guided-launch" aria-label="Mission controls">
      <div className="step-rail" aria-hidden="true">
        <span className={step === "prepare" || step === "scenic" ? "on" : "done"}>
          Prepare
        </span>
        <span
          className={
            step === "arm" ? "on" : step === "launch" || step === "done" ? "done" : ""
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
          disabled={
            locked ||
            (scenicActive ? false : !(live && gates.canAbort))
          }
          onClick={() => {
            if (scenicActive) onReset();
            else onAbort();
          }}
        >
          {scenicActive ? "Stop tour" : "Abort"}
        </button>
        <button type="button" disabled={locked} onClick={onReset}>
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
