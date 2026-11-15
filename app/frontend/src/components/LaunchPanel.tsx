import type { MissionPlan } from "../api/missionTypes";
import {
  PLANET_BODIES,
  type PlanetBodyId,
  planetName,
} from "../state/planetBodies";
import {
  SHUTTLE_LABEL,
  type FleetShuttle,
  type ShuttleClass,
} from "../state/fleetMock";
import { RouteCards } from "./RouteCards";

type Props = {
  originBodyId: PlanetBodyId;
  destinationBodyId: PlanetBodyId;
  dockedShuttles: FleetShuttle[];
  shuttleId: string | null;
  shuttleClass: ShuttleClass;
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  unavailableMessage: string | null;
  disabled?: boolean;
  onShuttle: (shuttle: FleetShuttle) => void;
  onDestination: (id: PlanetBodyId) => void;
  onSelectPlan: (planId: string) => void;
};

export function LaunchPanel({
  originBodyId,
  destinationBodyId,
  dockedShuttles,
  shuttleId,
  shuttleClass,
  leastFuel,
  earliestArrival,
  selectedPlanId,
  unavailableMessage,
  disabled,
  onShuttle,
  onDestination,
  onSelectPlan,
}: Props) {
  const originLabel = planetName(originBodyId);

  return (
    <section className="launch-panel" aria-label="Launch panel">
      <header className="launch-panel-head">
        <p className="launch-kicker">Dock · {originLabel}</p>
        <h2 className="launch-title">Launch</h2>
      </header>

      {!dockedShuttles.length ? (
        <p className="launch-empty">No shuttle docked here</p>
      ) : (
        <>
          <div className="launch-field">
            <span className="launch-label">Shuttle</span>
            <div className="shuttle-row" role="group" aria-label="Shuttle class">
              {dockedShuttles.map((shuttle) => (
                <button
                  key={shuttle.id}
                  type="button"
                  className={
                    shuttleId === shuttle.id
                      ? "shuttle-chip active"
                      : "shuttle-chip"
                  }
                  disabled={disabled}
                  onClick={() => onShuttle(shuttle)}
                >
                  {SHUTTLE_LABEL[shuttle.class]}
                </button>
              ))}
            </div>
          </div>

          <label className="launch-field">
            <span className="launch-label">Destination</span>
            <select
              value={destinationBodyId}
              disabled={disabled}
              onChange={(e) =>
                onDestination(e.target.value as PlanetBodyId)
              }
            >
              {PLANET_BODIES.filter((p) => p.bodyId !== originBodyId).map(
                (p) => (
                  <option key={p.bodyId} value={p.bodyId}>
                    {p.name}
                  </option>
                ),
              )}
            </select>
          </label>

          <p className="launch-route-line">
            {originLabel} → {planetName(destinationBodyId)}
            <span className="launch-class-tag">
              {SHUTTLE_LABEL[shuttleClass]}
            </span>
          </p>

          {unavailableMessage ? (
            <p className="launch-empty">{unavailableMessage}</p>
          ) : (
            <RouteCards
              leastFuel={leastFuel}
              earliestArrival={earliestArrival}
              selectedPlanId={selectedPlanId}
              disabled={disabled}
              onSelect={onSelectPlan}
            />
          )}
        </>
      )}
    </section>
  );
}
