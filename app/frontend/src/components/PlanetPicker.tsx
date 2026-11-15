import { PLANETS } from "../mock/planetInfo";
import type { PlanetTargetId } from "../api/types";

type Props = {
  selectedId: PlanetTargetId | null;
  enabled?: boolean;
  onSelect: (targetId: PlanetTargetId) => void;
};

export function PlanetPicker({
  selectedId,
  enabled = true,
  onSelect,
}: Props) {
  return (
    <div className="planet-picker" role="group" aria-label="Select planet">
      {PLANETS.map((planet) => {
        const active = selectedId === planet.target_id;
        return (
          <button
            key={planet.target_id}
            type="button"
            className={active ? "planet-btn active" : "planet-btn"}
            aria-pressed={active}
            disabled={!enabled}
            title={
              enabled
                ? undefined
                : "Close the info card (Esc) before choosing another planet"
            }
            onClick={() => onSelect(planet.target_id)}
          >
            <span
              className="swatch"
              style={{ background: planet.display_color }}
              aria-hidden
            />
            {planet.name}
            <span className="target-id">{planet.target_id}</span>
          </button>
        );
      })}
    </div>
  );
}
