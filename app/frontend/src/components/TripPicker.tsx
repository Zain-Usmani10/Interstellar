import {
  PLANET_BODIES,
  type PlanetBodyId,
} from "../state/planetBodies";

type Props = {
  originBodyId: PlanetBodyId;
  destinationBodyId: PlanetBodyId;
  disabled?: boolean;
  onOrigin: (id: PlanetBodyId) => void;
  onDestination: (id: PlanetBodyId) => void;
};

export function TripPicker({
  originBodyId,
  destinationBodyId,
  disabled,
  onOrigin,
  onDestination,
}: Props) {
  return (
    <div className="trip-picker" aria-label="Choose origin and destination">
      <label className="trip-field">
        <span>From</span>
        <select
          value={originBodyId}
          disabled={disabled}
          onChange={(e) => onOrigin(e.target.value as PlanetBodyId)}
        >
          {PLANET_BODIES.map((p) => (
            <option key={p.bodyId} value={p.bodyId}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <label className="trip-field">
        <span>To</span>
        <select
          value={destinationBodyId}
          disabled={disabled}
          onChange={(e) => onDestination(e.target.value as PlanetBodyId)}
        >
          {PLANET_BODIES.map((p) => (
            <option
              key={p.bodyId}
              value={p.bodyId}
              disabled={p.bodyId === originBodyId}
            >
              {p.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
