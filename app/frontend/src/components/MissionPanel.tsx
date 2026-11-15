import type { MissionPlan, MissionSnapshot } from "../api/missionTypes";

type Props = {
  plan: MissionPlan | null;
  snapshot: MissionSnapshot | null;
};

export function MissionPanel({ plan, snapshot }: Props) {
  const state = snapshot?.state ?? "IDLE";
  const tick = snapshot?.tick ?? 0;
  const mask = snapshot?.executed_mask ?? 0;
  const fuel = snapshot?.fuel_remaining_g;
  const faults = snapshot?.faults;
  const phase = snapshot?.spacecraft.phase;
  const outcome = snapshot?.outcome;

  return (
    <section className="mission-panel" aria-label="Mission status">
      <h3>Mission status</h3>
      <p className="mode-chip">
        {snapshot
          ? `${snapshot.controller_label} · seq ${snapshot.server_seq}`
          : "no MissionSnapshot yet"}
      </p>

      {plan ? (
        <p className="muted">
          Plan {plan.plan_id.slice(0, 8)}… · path {plan.nominal_path.length} pts ·{" "}
          {(plan.objectives_won ?? []).join(", ") || "objective n/a"}
        </p>
      ) : (
        <p className="muted">Select a route above before creating a mission.</p>
      )}

      <dl className="mission-dl">
        <div>
          <dt>State</dt>
          <dd>{state}</dd>
        </div>
        <div>
          <dt>Tick</dt>
          <dd>{tick}</dd>
        </div>
        <div>
          <dt>Executed mask</dt>
          <dd>{mask}</dd>
        </div>
        <div>
          <dt>Spacecraft phase</dt>
          <dd>{phase ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Outcome</dt>
          <dd>{outcome ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Fuel remaining</dt>
          <dd>{fuel === undefined || fuel === null ? "n/a" : `${fuel} g`}</dd>
        </div>
        <div>
          <dt>Faults (masked / no-majority / rx)</dt>
          <dd>
            {faults
              ? `${faults.masked_fault_count} / ${faults.no_majority_count} / ${faults.rx_error_count}`
              : "n/a"}
          </dd>
        </div>
      </dl>
      <p className="muted">
        RUNNING/COMPLETE only appear when MissionSnapshot says so. Scene follows
        the snapshot — never browser-invented progression.
      </p>
    </section>
  );
}
