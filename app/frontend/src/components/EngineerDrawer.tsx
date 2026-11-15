import { useState } from "react";
import type { FaultHistoryEntry, MissionPlan, MissionSnapshot } from "../api/missionTypes";

type Props = {
  plan: MissionPlan | null;
  snapshot: MissionSnapshot | null;
  faultHistory: FaultHistoryEntry[];
};

export function EngineerDrawer({ plan, snapshot, faultHistory }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`engineer-drawer ${open ? "open" : ""}`}>
      <button
        type="button"
        className="drawer-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide" : "Details for engineers"}
      </button>
      {open ? (
        <div className="drawer-body">
          <dl>
            <div>
              <dt>State</dt>
              <dd>{snapshot?.state ?? "—"}</dd>
            </div>
            <div>
              <dt>Tick</dt>
              <dd>{snapshot?.tick ?? "—"}</dd>
            </div>
            <div>
              <dt>Mask</dt>
              <dd>{snapshot?.executed_mask ?? "—"}</dd>
            </div>
            <div>
              <dt>Phase</dt>
              <dd>{snapshot?.spacecraft.phase ?? "—"}</dd>
            </div>
            <div>
              <dt>Fuel g</dt>
              <dd>{snapshot?.fuel_remaining_g ?? "—"}</dd>
            </div>
            <div>
              <dt>Δv km/s</dt>
              <dd>{plan?.dv?.dv_total_km_s ?? "—"}</dd>
            </div>
            <div>
              <dt>Plan id</dt>
              <dd className="mono">{plan?.plan_id?.slice(0, 8) ?? "—"}</dd>
            </div>
            <div>
              <dt>seq</dt>
              <dd>{snapshot?.server_seq ?? "—"}</dd>
            </div>
          </dl>
          {faultHistory.length > 0 ? (
            <ul className="drawer-faults">
              {faultHistory.slice(0, 8).map((e) => (
                <li key={e.id}>
                  {e.kind} · seq {e.at_seq} · {e.detail}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No fault events yet.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
