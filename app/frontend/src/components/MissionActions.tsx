import type { MissionCommand, SimFaultKind } from "../api/missionTypes";

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
  gates: Gates;
  simFaultsEnabled: boolean;
  hasSelectedPlan: boolean;
  onCreate: () => void;
  onCommand: (command: MissionCommand) => void;
  onFault: (kind: SimFaultKind) => void;
};

export function MissionActions({
  live,
  busy,
  gates,
  simFaultsEnabled,
  hasSelectedPlan,
  onCreate,
  onCommand,
  onFault,
}: Props) {
  const locked = !live || busy;

  return (
    <section className="mission-actions" aria-label="Mission commands">
      <h3>Mission commands</h3>
      <p className="muted">
        Keys: C create · U upload · R arm · G start · X abort · L clear
        {simFaultsEnabled ? " · F single fault · D divergence" : ""}
      </p>
      <div className="action-row" role="group" aria-label="Lifecycle">
        <button
          type="button"
          disabled={locked || !hasSelectedPlan || !gates.canCreate}
          onClick={onCreate}
        >
          Create
        </button>
        <button
          type="button"
          disabled={locked || !gates.canUpload}
          onClick={() => onCommand("upload")}
        >
          Upload
        </button>
        <button
          type="button"
          disabled={locked || !gates.canArm}
          onClick={() => onCommand("arm")}
        >
          Arm
        </button>
        <button
          type="button"
          disabled={locked || !gates.canStart}
          onClick={() => onCommand("start")}
        >
          Start
        </button>
        <button
          type="button"
          disabled={locked || !gates.canAbort}
          onClick={() => onCommand("abort")}
        >
          Abort
        </button>
        <button
          type="button"
          disabled={locked || !gates.canClear}
          onClick={() => onCommand("clear")}
        >
          Clear
        </button>
      </div>

      {simFaultsEnabled ? (
        <div className="action-row" role="group" aria-label="Simulator faults">
          <button
            type="button"
            disabled={locked}
            onClick={() => onFault("single")}
          >
            Sim fault: single
          </button>
          <button
            type="button"
            disabled={locked}
            onClick={() => onFault("divergence")}
          >
            Sim fault: divergence
          </button>
        </div>
      ) : (
        <p className="muted">
          Simulator fault buttons hidden — controller is not SIMULATED CONTROLLER.
        </p>
      )}
    </section>
  );
}
