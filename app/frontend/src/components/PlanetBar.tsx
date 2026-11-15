import { VISUAL_PLANETS } from "../scene/planets";
import type { PlanetTargetId } from "../api/types";

type Props = {
  focusName: string | null;
  selectedId: PlanetTargetId | null;
  selectionEnabled: boolean;
  onVisit: (name: string) => void;
  onSelectEarthMars: (target: PlanetTargetId) => void;
};

const EXTRA = [{ name: "Black Hole", color: "#1a0a08" }];

export function PlanetBar({
  focusName,
  selectedId,
  selectionEnabled,
  onVisit,
  onSelectEarthMars,
}: Props) {
  return (
    <nav className="planet-bar" aria-label="Fly to a planet">
      {VISUAL_PLANETS.map((body) => {
        const active =
          focusName === body.name ||
          (body.target != null && selectedId === body.target);
        const routeEndpoint =
          body.target === "planet.399" || body.target === "planet.499";
        return (
          <button
            key={body.name}
            type="button"
            className={active ? "planet-chip active" : "planet-chip"}
            title={`Fly to ${body.name}`}
            onClick={() => {
              onVisit(body.name);
              if (routeEndpoint && body.target && selectionEnabled) {
                onSelectEarthMars(body.target);
              }
            }}
          >
            <span className="chip-dot" style={{ background: body.color }} />
            {body.name}
          </button>
        );
      })}
      {EXTRA.map((item) => (
        <button
          key={item.name}
          type="button"
          className={
            focusName === item.name ? "planet-chip active" : "planet-chip"
          }
          title="Fly to the black hole"
          onClick={() => onVisit(item.name)}
        >
          <span className="chip-dot" style={{ background: item.color }} />
          {item.name}
        </button>
      ))}
    </nav>
  );
}
