import type { MissionPlan, MissionSnapshot, PlanSummary } from "../api/missionTypes";

type Props = {
  plan: MissionPlan | null;
  planSummaries: PlanSummary[];
  snapshot: MissionSnapshot | null;
  onSelectPlan?: (planId: string) => void;
};

export function MissionPanel({
  plan,
  planSummaries,
  snapshot,
  onSelectPlan,
}: Props) {
  const state = snapshot?.state ?? "IDLE";
  const tick = snapshot?.tick ?? 0;
  const mask = snapshot?.executed_mask ?? 0;
  const fuel = snapshot?.fuel_remaining_g;
  const faults = snapshot?.faults;
  const phase = snapshot?.spacecraft.phase;

  return (
    <section className="mission-panel" aria-label="Mission status">
      <h3>Mission status</h3>
      <p className="mode-chip">
        {snapshot
          ? `${snapshot.controller_label} · seq ${snapshot.server_seq}`
          : "no MissionSnapshot yet"}
      </p>

      {planSummaries.length > 0 ? (
        <label className="plan-picker">
          <span>Preview plan</span>
          <select
            value={plan?.plan_id ?? ""}
            onChange={(e) => onSelectPlan?.(e.target.value)}
          >
            {planSummaries.map((p) => (
              <option key={p.plan_id} value={p.plan_id}>
                {(p.objectives_won ?? []).join(",") || "plan"} · {p.data_mode ?? "?"}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="muted">No plans from GET /api/v1/plans (offline or empty).</p>
      )}

      {plan ? (
        <p className="muted">
          Plan {plan.plan_id.slice(0, 8)}… · path {plan.nominal_path.length} pts ·{" "}
          {(plan.objectives_won ?? []).join(", ") || "objective n/a"}
        </p>
      ) : null}

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
        Scene animations must follow MissionSnapshot only. This panel never invents
        RUNNING/COMPLETE without snapshot evidence. Upload/start controls are not in
        this change.
      </p>
    </section>
  );
}
