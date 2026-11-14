import type { PlanetInfo } from "../mock/planetInfo";

type Props = {
  planet: PlanetInfo;
  onClose: () => void;
};

export function PlanetInfoCard({ planet, onClose }: Props) {
  const pos = planet.orbital_state.position_km;
  const vel = planet.orbital_state.velocity_km_s;

  return (
    <aside className="info-card" aria-label={`${planet.name} information`}>
      <header className="info-card-header">
        <div>
          <p className="eyebrow">Planet explorer · {planet.target_id}</p>
          <h2>{planet.name}</h2>
        </div>
        <button type="button" className="close-btn" onClick={onClose}>
          Close
        </button>
      </header>

      <p className="mode-chip">data_mode: {planet.data_mode}</p>

      <section>
        <h3>Scene epoch</h3>
        <p>{planet.scene_epoch_utc_label}</p>
        <p className="muted">JD TDB {planet.scene_epoch_jd_tdb} (mock)</p>
      </section>

      <section>
        <h3>Facts</h3>
        <ul className="fact-list">
          {planet.facts.map((fact) => (
            <li key={fact.key}>
              <div className="fact-row">
                <span>{fact.label}</span>
                <strong>
                  {fact.value}
                  {fact.unit ? ` ${fact.unit}` : ""}
                </strong>
              </div>
              <p className="source">{fact.source}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Orbital state (mock)</h3>
        <p className="muted">
          {planet.orbital_state.frame} · {planet.orbital_state.center} ·{" "}
          {planet.orbital_state.units}
        </p>
        <p>
          r = [{pos[0].toExponential(3)}, {pos[1].toExponential(3)},{" "}
          {pos[2].toExponential(3)}] km
        </p>
        <p>
          v = [{vel[0].toFixed(2)}, {vel[1].toFixed(2)}, {vel[2].toFixed(2)}]
          km/s
        </p>
        <p className="source">{planet.orbital_state.provenance}</p>
      </section>

      <section>
        <h3>
          {planet.body_id === "399"
            ? "Earth natural hazard events"
            : "Mars conditions"}
        </h3>
        <p className="availability">
          availability: {planet.conditions.availability} · delivery:{" "}
          {planet.conditions.delivery}
        </p>
        <p>{planet.conditions.note}</p>
        <p className="muted">
          Observation time is separate from mission/scene epoch — neither is
          live in this mock.
        </p>
      </section>

      <p className="scale-note">
        Marker sizes and orbit guides are illustrative, not to scale (1 au = 10
        display units).
      </p>
    </aside>
  );
}
