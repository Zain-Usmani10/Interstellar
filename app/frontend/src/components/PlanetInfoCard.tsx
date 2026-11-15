import type { PlanetCardModel } from "../api/mapPlanetInfo";

type Props = {
  planet: PlanetCardModel;
  status?: "loading" | "ready" | "error";
  onClose: () => void;
};

export function PlanetInfoCard({ planet, status = "ready", onClose }: Props) {
  const pos = planet.orbital.r_km;
  const vel = planet.orbital.v_km_s;

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

      <p className="mode-chip">data: {planet.data_mode_label}</p>
      {status === "loading" ? (
        <p className="muted">Loading planet info…</p>
      ) : null}
      {status === "error" ? (
        <p className="muted">Planet info fetch failed — showing fallback card.</p>
      ) : null}

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
                <strong>{fact.display_value}</strong>
              </div>
              {fact.note ? <p className="muted">{fact.note}</p> : null}
              <p className="source">{fact.source_label}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Orbital state</h3>
        <p className="availability">availability: {planet.orbital.availability}</p>
        <p className="muted">{planet.orbital.frame_label}</p>
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
        <p className="source">{planet.orbital.provenance_note}</p>
      </section>

      <section className="conditions-block">
        <h3>{planet.conditions.label}</h3>
        <p className="availability">
          availability: {planet.conditions.availability}
          {planet.conditions.delivery
            ? ` · delivery: ${planet.conditions.delivery}`
            : ""}
        </p>
        <p>{planet.conditions.note}</p>
        <div className="obs-times" aria-label="Observation and retrieval times">
          <p className="muted">
            Observed (UTC):{" "}
            {planet.conditions.observed_from_utc ||
            planet.conditions.observed_to_utc
              ? `${planet.conditions.observed_from_utc ?? "—"} → ${planet.conditions.observed_to_utc ?? "—"}`
              : "n/a"}
          </p>
          <p className="muted">
            Retrieved (UTC): {planet.conditions.retrieved_utc ?? "n/a"}
          </p>
          <p className="muted obs-sep">
            These times are Earth-hazard observation/retrieval stamps — not the
            scene/mission epoch above.
          </p>
        </div>
        {planet.conditions.items.length > 0 ? (
          <ul className="fact-list">
            {planet.conditions.items.map((item) => (
              <li key={item.id}>
                <div className="fact-row">
                  <span>{item.title}</span>
                  <strong>{item.category}</strong>
                </div>
                {item.date_utc ? (
                  <p className="muted">event date: {item.date_utc}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <p className="scale-note">
        Marker sizes and orbit guides are illustrative, not to scale (1 au = 10
        display units).
      </p>
    </aside>
  );
}
