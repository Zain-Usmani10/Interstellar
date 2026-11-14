import { MOCK_SNAPSHOT } from "../mock/missionSnapshot";

export function MissionPanel() {
  const s = MOCK_SNAPSHOT;
  return (
    <section className="mission-panel" aria-label="Mission status">
      <h3>Mission status</h3>
      <p className="mode-chip">data_mode: {s.data_mode}</p>
      <dl className="mission-dl">
        <div>
          <dt>State</dt>
          <dd>{s.state}</dd>
        </div>
        <div>
          <dt>Tick</dt>
          <dd>{s.tick}</dd>
        </div>
        <div>
          <dt>Executed mask</dt>
          <dd>{s.executed_mask}</dd>
        </div>
        <div>
          <dt>Fuel remaining</dt>
          <dd>{s.fuel_remaining_g === null ? "n/a" : `${s.fuel_remaining_g} g`}</dd>
        </div>
        <div>
          <dt>Faults (masked / no-majority / rx)</dt>
          <dd>
            {s.fault_counts.masked} / {s.fault_counts.no_majority} /{" "}
            {s.fault_counts.rx_error}
          </dd>
        </div>
      </dl>
      <p className="muted">{s.note}</p>
      <p className="muted">
        Route upload/start UI comes after API wiring. This panel will not show
        RUNNING or COMPLETE without snapshot evidence.
      </p>
    </section>
  );
}
