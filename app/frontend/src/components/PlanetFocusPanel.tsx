import type {
  MissionPlan,
  MissionSnapshot,
  PlanSummary,
} from "../api/missionTypes";
import type { PlanetCardModel } from "../api/mapPlanetInfo";
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
import {
  destinationsWithRoute,
  originsWithRoute,
} from "../state/routeDestinations";
import { RouteCards } from "./RouteCards";
import { GuidedLaunch } from "./GuidedLaunch";
import { TripReadout } from "./TripReadout";

export type FocusTab = "about" | "from-to" | "to-from";

type Gates = {
  canCreate: boolean;
  canUpload: boolean;
  canArm: boolean;
  canStart: boolean;
  canAbort: boolean;
  canClear: boolean;
};

type Props = {
  planetNameLabel: string;
  tab: FocusTab;
  onTab: (tab: FocusTab) => void;
  card: PlanetCardModel | null;
  cardStatus: "idle" | "loading" | "ready" | "error";
  originBodyId: PlanetBodyId;
  destinationBodyId: PlanetBodyId;
  dockedShuttles: FleetShuttle[];
  shuttleId: string | null;
  shuttleClass: ShuttleClass;
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  planSummaries: PlanSummary[];
  unavailableMessage: string | null;
  tripLocked: boolean;
  onShuttle: (shuttle: FleetShuttle) => void;
  onDestination: (id: PlanetBodyId) => void;
  onOrigin: (id: PlanetBodyId) => void;
  onSelectPlan: (planId: string) => void;
  daysToArrival: number | null;
  tripDays: number | null;
  tMinusLabel: string | null;
  blackout: boolean;
  live: boolean;
  commandBusy: boolean;
  hasPlan: boolean;
  snapshot: MissionSnapshot | null;
  gates: Gates;
  simFaultsEnabled: boolean;
  routeLabel: string;
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
  onReset: () => void;
  onBlackoutStart: () => void;
  onBlackoutEnd: () => void;
  onResetFleet: () => void;
  onFaultSingle: () => void;
  onFaultDivergence: () => void;
};

export function PlanetFocusPanel({
  planetNameLabel,
  tab,
  onTab,
  card,
  cardStatus,
  originBodyId,
  destinationBodyId,
  dockedShuttles,
  shuttleId,
  shuttleClass,
  leastFuel,
  earliestArrival,
  selectedPlanId,
  planSummaries,
  unavailableMessage,
  tripLocked,
  onShuttle,
  onDestination,
  onOrigin,
  onSelectPlan,
  daysToArrival,
  tripDays,
  tMinusLabel,
  blackout,
  live,
  commandBusy,
  hasPlan,
  snapshot,
  gates,
  simFaultsEnabled,
  routeLabel,
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onReset,
  onBlackoutStart,
  onBlackoutEnd,
  onResetFleet,
  onFaultSingle,
  onFaultDivergence,
}: Props) {
  return (
    <aside className="glass planet-focus-panel" aria-label={`${planetNameLabel} panel`}>
      <nav className="focus-tabs" aria-label="Planet panel tabs">
        {(
          [
            ["about", "About"],
            ["from-to", "From → To"],
            ["to-from", "To → From"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "focus-tab active" : "focus-tab"}
            onClick={() => onTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="focus-panel-body">
        {tab === "about" ? (
          <AboutBody
            card={card}
            cardStatus={cardStatus}
            planetNameLabel={planetNameLabel}
          />
        ) : null}

        {tab === "from-to" ? (
          <TripBody
            mode="outbound"
            focusBodyId={originBodyId}
            otherBodyId={destinationBodyId}
            dockedShuttles={dockedShuttles}
            shuttleId={shuttleId}
            shuttleClass={shuttleClass}
            leastFuel={leastFuel}
            earliestArrival={earliestArrival}
            selectedPlanId={selectedPlanId}
            planSummaries={planSummaries}
            unavailableMessage={unavailableMessage}
            tripLocked={tripLocked}
            onShuttle={onShuttle}
            onOther={(id) => onDestination(id)}
            onSelectPlan={onSelectPlan}
            daysToArrival={daysToArrival}
            tripDays={tripDays}
            tMinusLabel={tMinusLabel}
            blackout={blackout}
            live={live}
            commandBusy={commandBusy}
            hasPlan={hasPlan}
            snapshot={snapshot}
            gates={gates}
            simFaultsEnabled={simFaultsEnabled}
            routeLabel={routeLabel}
            onPrepare={onPrepare}
            onArm={onArm}
            onLaunch={onLaunch}
            onAbort={onAbort}
            onReset={onReset}
            onBlackoutStart={onBlackoutStart}
            onBlackoutEnd={onBlackoutEnd}
            onResetFleet={onResetFleet}
            onFaultSingle={onFaultSingle}
            onFaultDivergence={onFaultDivergence}
          />
        ) : null}

        {tab === "to-from" ? (
          <TripBody
            mode="inbound"
            focusBodyId={destinationBodyId}
            otherBodyId={originBodyId}
            dockedShuttles={dockedShuttles}
            shuttleId={shuttleId}
            shuttleClass={shuttleClass}
            leastFuel={leastFuel}
            earliestArrival={earliestArrival}
            selectedPlanId={selectedPlanId}
            planSummaries={planSummaries}
            unavailableMessage={unavailableMessage}
            tripLocked={tripLocked}
            onShuttle={onShuttle}
            onOther={(id) => onOrigin(id)}
            onSelectPlan={onSelectPlan}
            daysToArrival={daysToArrival}
            tripDays={tripDays}
            tMinusLabel={tMinusLabel}
            blackout={blackout}
            live={live}
            commandBusy={commandBusy}
            hasPlan={hasPlan}
            snapshot={snapshot}
            gates={gates}
            simFaultsEnabled={simFaultsEnabled}
            routeLabel={routeLabel}
            onPrepare={onPrepare}
            onArm={onArm}
            onLaunch={onLaunch}
            onAbort={onAbort}
            onReset={onReset}
            onBlackoutStart={onBlackoutStart}
            onBlackoutEnd={onBlackoutEnd}
            onResetFleet={onResetFleet}
            onFaultSingle={onFaultSingle}
            onFaultDivergence={onFaultDivergence}
          />
        ) : null}
      </div>
    </aside>
  );
}

function AboutBody({
  card,
  cardStatus,
  planetNameLabel,
}: {
  card: PlanetCardModel | null;
  cardStatus: "idle" | "loading" | "ready" | "error";
  planetNameLabel: string;
}) {
  if (!card) {
    return (
      <p className="muted">
        {cardStatus === "loading"
          ? `Loading ${planetNameLabel}…`
          : `No planet card for ${planetNameLabel}.`}
      </p>
    );
  }

  return (
    <div className="focus-about">
      <h2 className="focus-planet-title">{card.name}</h2>
      <p className="mode-chip">data: {card.data_mode_label}</p>
      {cardStatus === "error" ? (
        <p className="muted">Fetch failed — showing fallback card.</p>
      ) : null}
      <section>
        <h3>Scene epoch</h3>
        <p>{card.scene_epoch_utc_label}</p>
      </section>
      <section>
        <h3>Facts</h3>
        <ul className="fact-list">
          {card.facts.map((fact) => (
            <li key={fact.key}>
              <div className="fact-row">
                <span>{fact.label}</span>
                <strong>{fact.display_value}</strong>
              </div>
              {fact.note ? <p className="muted">{fact.note}</p> : null}
            </li>
          ))}
        </ul>
      </section>
      <section className="conditions-block">
        <h3>{card.conditions.label}</h3>
        <p className="availability">
          availability: {card.conditions.availability}
        </p>
        {card.conditions.note ? <p>{card.conditions.note}</p> : null}
      </section>
    </div>
  );
}

function TripBody({
  mode,
  focusBodyId,
  otherBodyId,
  dockedShuttles,
  shuttleId,
  shuttleClass,
  leastFuel,
  earliestArrival,
  selectedPlanId,
  planSummaries,
  unavailableMessage,
  tripLocked,
  onShuttle,
  onOther,
  onSelectPlan,
  daysToArrival,
  tripDays,
  tMinusLabel,
  blackout,
  live,
  commandBusy,
  hasPlan,
  snapshot,
  gates,
  simFaultsEnabled,
  routeLabel,
  onPrepare,
  onArm,
  onLaunch,
  onAbort,
  onReset,
  onBlackoutStart,
  onBlackoutEnd,
  onResetFleet,
  onFaultSingle,
  onFaultDivergence,
}: {
  mode: "outbound" | "inbound";
  focusBodyId: PlanetBodyId;
  otherBodyId: PlanetBodyId;
  dockedShuttles: FleetShuttle[];
  shuttleId: string | null;
  shuttleClass: ShuttleClass;
  leastFuel: MissionPlan | null;
  earliestArrival: MissionPlan | null;
  selectedPlanId: string | null;
  planSummaries: PlanSummary[];
  unavailableMessage: string | null;
  tripLocked: boolean;
  onShuttle: (shuttle: FleetShuttle) => void;
  onOther: (id: PlanetBodyId) => void;
  onSelectPlan: (planId: string) => void;
  daysToArrival: number | null;
  tripDays: number | null;
  tMinusLabel: string | null;
  blackout: boolean;
  live: boolean;
  commandBusy: boolean;
  hasPlan: boolean;
  snapshot: MissionSnapshot | null;
  gates: Gates;
  simFaultsEnabled: boolean;
  routeLabel: string;
  onPrepare: () => void;
  onArm: () => void;
  onLaunch: () => void;
  onAbort: () => void;
  onReset: () => void;
  onBlackoutStart: () => void;
  onBlackoutEnd: () => void;
  onResetFleet: () => void;
  onFaultSingle: () => void;
  onFaultDivergence: () => void;
}) {
  const focusLabel = planetName(focusBodyId);
  const otherLabel = planetName(otherBodyId);
  const others = PLANET_BODIES.filter((p) => p.bodyId !== focusBodyId);
  const outbound = mode === "outbound";
  const routed = outbound
    ? destinationsWithRoute(planSummaries, focusBodyId)
    : originsWithRoute(planSummaries, focusBodyId);
  const showFlightReadout = Boolean(
    snapshot &&
      (snapshot.state === "RUNNING" ||
        snapshot.state === "ARMED" ||
        snapshot.state === "LOADED" ||
        snapshot.state === "SAFE" ||
        blackout),
  );

  return (
    <div className="focus-trip">
      <p className="launch-kicker">
        {outbound
          ? `Leaving ${focusLabel}`
          : `Arriving at ${focusLabel}`}
      </p>

      {!dockedShuttles.length && outbound ? (
        <p className="launch-empty">No shuttle docked here</p>
      ) : (
        <>
          {outbound ? (
            <div className="launch-field">
              <span className="launch-label">Shuttle</span>
              <div className="shuttle-row" role="group" aria-label="Shuttle">
                {dockedShuttles.map((shuttle) => (
                  <button
                    key={shuttle.id}
                    type="button"
                    className={
                      shuttleId === shuttle.id
                        ? "shuttle-chip active"
                        : "shuttle-chip"
                    }
                    disabled={tripLocked}
                    onClick={() => onShuttle(shuttle)}
                  >
                    {shuttle.name}
                    <span className="shuttle-chip-class">
                      {SHUTTLE_LABEL[shuttle.class]}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="muted launch-class-tag">
              Arrivals for shuttle class · {SHUTTLE_LABEL[shuttleClass]}
            </p>
          )}

          <label className="launch-field">
            <span className="launch-label">
              {outbound ? "Destination" : "From"}
            </span>
            <select
              value={otherBodyId}
              disabled={tripLocked}
              onChange={(e) => onOther(e.target.value as PlanetBodyId)}
            >
              {others.map((p) => {
                const hasRoute = routed.has(p.bodyId);
                return (
                  <option key={p.bodyId} value={p.bodyId}>
                    {p.name}
                    {hasRoute ? " · route available" : " · no route"}
                  </option>
                );
              })}
            </select>
          </label>

          <p className="launch-route-line">
            {outbound
              ? `${focusLabel} → ${otherLabel}`
              : `${otherLabel} → ${focusLabel}`}
          </p>

          {unavailableMessage ? (
            <p className="launch-empty">{unavailableMessage}</p>
          ) : (
            <RouteCards
              leastFuel={leastFuel}
              earliestArrival={earliestArrival}
              selectedPlanId={selectedPlanId}
              disabled={tripLocked || !outbound}
              readOnly={!outbound}
              onSelect={onSelectPlan}
            />
          )}

          {showFlightReadout ? (
            <TripReadout
              daysToArrival={daysToArrival}
              tripDays={tripDays}
              tMinusLabel={tMinusLabel}
              estimated={blackout}
            />
          ) : null}

          {outbound ? (
            <GuidedLaunch
              live={live}
              busy={commandBusy}
              hasPlan={hasPlan}
              snapshot={snapshot}
              gates={gates}
              simFaultsEnabled={simFaultsEnabled}
              routeLabel={routeLabel}
              blackoutActive={blackout}
              compact
              onPrepare={onPrepare}
              onArm={onArm}
              onLaunch={onLaunch}
              onAbort={onAbort}
              onReset={onReset}
              onBlackoutStart={onBlackoutStart}
              onBlackoutEnd={onBlackoutEnd}
              onResetFleet={onResetFleet}
              onFaultSingle={onFaultSingle}
              onFaultDivergence={onFaultDivergence}
            />
          ) : (
            <p className="guided-hint">
              Read-only inbound numbers — use From → To on the origin planet to
              launch.
            </p>
          )}
        </>
      )}
    </div>
  );
}
