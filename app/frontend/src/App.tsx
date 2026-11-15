import { useEffect, useMemo, useState } from "react";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { BlackoutBanner } from "./components/BlackoutBanner";
import { DateCorner } from "./components/DateCorner";
import { EngineerDrawer } from "./components/EngineerDrawer";
import { GlassStatus } from "./components/GlassStatus";
import { GuidedLaunch } from "./components/GuidedLaunch";
import { LaunchPanel } from "./components/LaunchPanel";
import { PlanetBar } from "./components/PlanetBar";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { ReconciliationCard } from "./components/ReconciliationCard";
import { TripReadout } from "./components/TripReadout";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import {
  MOCK_FLEET,
  dockedAt,
  type FleetShuttle,
} from "./state/fleetMock";
import {
  PLANET_BODIES,
  type PlanetBodyId,
  planetName,
} from "./state/planetBodies";
import { unavailableMessage } from "./state/selectPresentationRoutes";
import { useCoreBridge } from "./state/useCoreBridge";

function bodyIdFromName(name: string | null): PlanetBodyId | null {
  if (!name) return null;
  return PLANET_BODIES.find((p) => p.name === name)?.bodyId ?? null;
}

/** Format T-minus from confirmed tick vs plan departure_tick (100 Hz). */
function formatTMinus(
  tick: number | null | undefined,
  departureTick: number | null | undefined,
): string | null {
  if (
    tick == null ||
    departureTick == null ||
    !Number.isFinite(tick) ||
    !Number.isFinite(departureTick) ||
    tick >= departureTick
  ) {
    return null;
  }
  const seconds = (departureTick - tick) / 100;
  const whole = Math.floor(seconds);
  const centi = Math.floor((seconds - whole) * 100);
  return `T−${String(whole).padStart(2, "0")}.${String(centi).padStart(2, "0")}`;
}

export default function App() {
  const {
    linkMode,
    controllerLabel,
    dataMode,
    selectedId,
    planetChoiceEnabled,
    card,
    cardStatus,
    lastError,
    commandBusy,
    routePlans,
    selectedPlan,
    originBodyId,
    destinationBodyId,
    shuttleClass,
    routeUnavailable,
    snapshot,
    faultHistory,
    gates,
    simFaultsEnabled,
    selectPlanById,
    setTrip,
    prepareMission,
    resetMission,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const [focusName, setFocusName] = useState<string | null>("Earth");
  const [shuttleId, setShuttleId] = useState<string | null>(
    "shuttle-std-earth-1",
  );
  const [fleet] = useState(MOCK_FLEET);

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const live = linkMode === "live";
  const originLabel = planetName(originBodyId);
  const destinationLabel = planetName(destinationBodyId);
  const routeLabel = `${originLabel} → ${destinationLabel}`;

  const dockedShuttles = dockedAt(fleet, originBodyId);
  const blackout = Boolean(snapshot?.link?.blackout);
  const tripLocked =
    commandBusy ||
    blackout ||
    Boolean(
      snapshot &&
        snapshot.state !== "IDLE" &&
        snapshot.state !== "UNKNOWN" &&
        snapshot.state !== "ABORTED" &&
        snapshot.state !== "COMPLETE",
    );

  const daysToArrival = blackout
    ? (snapshot?.estimate?.days_to_arrival ?? null)
    : (snapshot?.trip?.days_to_arrival ?? null);
  const tripDays = snapshot?.trip?.trip_days ?? null;
  const tMinus = formatTMinus(
    snapshot?.tick,
    selectedPlan?.ticks?.departure_tick,
  );

  const dateUtc = blackout
    ? (snapshot?.estimate?.date_utc ?? null)
    : (snapshot?.date_utc ?? selectedPlan?.departure?.utc ?? null);
  const dateEstimated = Boolean(blackout && snapshot?.estimate?.date_utc);

  const routeMsg = unavailableMessage(
    routeUnavailable,
    dockedShuttles.length > 0,
  );

  const reconciliation = snapshot?.reconciliation
    ? {
        blackoutStartTick: snapshot.reconciliation.blackout_start_tick,
        blackoutEndTick: snapshot.reconciliation.blackout_end_tick,
        eventsDuringBlackout: snapshot.reconciliation.events_during_blackout.map(
          (e) => (typeof e === "string" ? e : e.event),
        ),
        estimateMatched: snapshot.reconciliation.estimate_matched,
        differences: snapshot.reconciliation.differences,
      }
    : null;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clearSelection("keyboard");
        setFocusName(null);
        return;
      }
      if (planetChoiceEnabled) {
        if (event.key === "1") {
          setFocusName("Earth");
          selectPlanet("planet.399", "keyboard");
          setTrip({ origin: "399" });
        }
        if (event.key === "2") {
          setFocusName("Mars");
          selectPlanet("planet.499", "keyboard");
          setTrip({ origin: "499" });
        }
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "o") {
        event.preventDefault();
        void resetMission();
      } else if (key === "p" && live && selectedPlan && !commandBusy && !blackout) {
        event.preventDefault();
        void prepareMission();
      } else if (key === "r" && live && gates.canArm && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("arm");
      } else if (key === "g" && live && gates.canStart && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("start");
      } else if (key === "x" && live && gates.canAbort && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("abort");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function visitPlanet(name: string) {
    setFocusName(name);
    const bodyId = bodyIdFromName(name);
    if (!bodyId) return;
    const docked = dockedAt(fleet, bodyId);
    const first = docked[0] ?? null;
    setShuttleId(first?.id ?? null);
    setTrip({
      origin: bodyId,
      shuttleClass: first?.class ?? "standard",
    });
  }

  function pickShuttle(shuttle: FleetShuttle) {
    setShuttleId(shuttle.id);
    setTrip({ shuttleClass: shuttle.class });
  }

  return (
    <div className="app-shell sci-fi">
      <div className="scene-layer">
        <OrbitScene
          selectedId={selectedId}
          selectionEnabled={planetChoiceEnabled && !blackout}
          onSelect={(id) => {
            const name = id === "planet.399" ? "Earth" : "Mars";
            setFocusName(name);
            selectPlanet(id);
            setTrip({ origin: id === "planet.399" ? "399" : "499" });
          }}
          onFocusName={(name) => visitPlanet(name)}
          focusName={focusName}
          plan={scenePlan}
          snapshot={sceneSnapshot}
        />
      </div>

      <header className="glass brand-glass">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">{routeLabel}</p>
      </header>

      <DateCorner dateUtc={dateUtc} estimated={dateEstimated} />

      <BlackoutBanner visible={blackout} />

      <GlassStatus
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        snapshot={snapshot}
        lastError={lastError}
        destinationName={destinationLabel}
      />

      <aside className="glass panel-left launch-aside" aria-label="Launch">
        <LaunchPanel
          originBodyId={originBodyId}
          destinationBodyId={destinationBodyId}
          dockedShuttles={dockedShuttles}
          shuttleId={shuttleId}
          shuttleClass={shuttleClass}
          leastFuel={routePlans.least_fuel}
          earliestArrival={routePlans.earliest_arrival}
          selectedPlanId={selectedPlan?.plan_id ?? null}
          unavailableMessage={routeMsg}
          disabled={tripLocked}
          onShuttle={pickShuttle}
          onDestination={(id) => {
            setTrip({ destination: id });
            setFocusName(planetName(id));
          }}
          onSelectPlan={(id) => void selectPlanById(id)}
        />
        <TripReadout
          daysToArrival={daysToArrival}
          tripDays={tripDays}
          tMinusLabel={tMinus}
          estimated={blackout}
        />
        <GuidedLaunch
          live={live}
          busy={commandBusy}
          hasPlan={Boolean(selectedPlan)}
          snapshot={snapshot}
          gates={gates}
          simFaultsEnabled={simFaultsEnabled}
          routeLabel={routeLabel}
          blackoutActive={blackout}
          onPrepare={() => void prepareMission()}
          onArm={() => void sendCommand("arm")}
          onLaunch={() => void sendCommand("start")}
          onAbort={() => {
            void sendCommand("abort");
            clearSelection("mouse");
          }}
          onReset={() => void resetMission()}
          onBlackoutStart={() => void sendCommand("blackout_start")}
          onBlackoutEnd={() => void sendCommand("blackout_end")}
          onFaultSingle={() => void injectFault("single")}
          onFaultDivergence={() => void injectFault("divergence")}
        />
        <EngineerDrawer
          plan={selectedPlan}
          snapshot={snapshot}
          faultHistory={faultHistory}
        />
      </aside>

      <ReconciliationCard data={reconciliation} />

      {card ? (
        <aside className="glass panel-right" aria-label="Planet information">
          <PlanetInfoCard
            planet={card}
            status={cardStatus === "idle" ? "ready" : cardStatus}
            onClose={() => clearSelection("mouse")}
          />
        </aside>
      ) : null}

      <div className="bci-float" aria-label="Optional brain widget">
        <BciSlot />
      </div>

      <PlanetBar
        focusName={focusName}
        selectedId={selectedId}
        selectionEnabled={planetChoiceEnabled && !blackout}
        onVisit={visitPlanet}
        onSelectEarthMars={selectPlanet}
      />
    </div>
  );
}
