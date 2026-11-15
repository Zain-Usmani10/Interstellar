import {
  formatFactSource,
  formatFactValue,
  type PlanetInfo,
} from "../mock/planetInfo";

type Props = {
  planet: PlanetInfo;
  onClose: () => void;
};

export function PlanetInfoCard({ planet, onClose }: Props) {
  const orbital = planet.orbital_state;
  const pos = orbital.r_km;
  const vel = orbital.v_km_s;

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
        <p className="muted">JD TDB {planet.scene_epoch_jd_tdb}</p>
      </section>

      <section>
        <h3>Facts</h3>
        <ul className="fact-list">
          {planet.facts.map((fact) => (
            <li key={fact.key}>
              <div className="fact-row">
                <span>{fact.label}</span>
                <strong>{formatFactValue(fact.value, fact.unit)}</strong>
              </div>
              {fact.note ? <p className="muted">{fact.note}</p> : null}
              <p className="source">{formatFactSource(fact.source)}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Orbital state</h3>
        <p className="availability">availability: {orbital.availability}</p>
        <p className="muted">{orbital.frame_label}</p>
        {pos && vel ? (
          <>
            <p>
              r = [{pos[0].toExponential(3)}, {pos[1].toExponential(3)},{" "}
              {pos[2].toExponential(3)}] km
            </p>
            <p>
              v = [{vel[0].toFixed(2)}, {vel[1].toFixed(2)},{" "}
              {vel[2].toFixed(2)}] km/s
            </p>
          </>
        ) : (
          <p className="muted">Position/velocity unavailable for this epoch.</p>
        )}
        <p className="source">{orbital.provenance_note}</p>
      </section>

      <section>
        <h3>{planet.conditions.label}</h3>
        <p className="availability">
          availability: {planet.conditions.availability}
          {planet.conditions.delivery
            ? ` · delivery: ${planet.conditions.delivery}`
            : ""}
        </p>
        <p>{planet.conditions.note}</p>
        <p className="muted">
          Observation time is separate from mission/scene epoch.
        </p>
      </section>

      <p className="scale-note">
        Marker sizes and orbit guides are illustrative, not to scale (1 au = 10
        display units).
      </p>
    </aside>
  );
}
