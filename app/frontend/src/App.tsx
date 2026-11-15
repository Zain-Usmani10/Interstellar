import { useEffect, useMemo, useState } from "react";
import { getPlanetPositions } from "./api/coreClient";
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
import type { SceneBodyId, ScenePlanetPosition } from "./scene/types";
import {
  dockedAt,
  toSceneFleet,
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

const BODY_IDS: SceneBodyId[] = [
  "199",
  "299",
  "399",
  "499",
  "599",
  "699",
  "799",
  "899",
];

export default function App() {
  const {
    linkMode,
    controllerSource,
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
    selectedShuttleId,
    fleet,
    routeUnavailable,
    snapshot,
    faultHistory,
    gates,
    simFaultsEnabled,
    selectPlanById,
    setTrip,
    setSelectedShuttleId,
    prepareMission,
    resetMission,
    resetFleet,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const [focusName, setFocusName] = useState<string | null>("Earth");
  const [planetPositions, setPlanetPositions] = useState<
    ScenePlanetPosition[]
  >([]);

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const sceneFleet = useMemo(() => toSceneFleet(fleet), [fleet]);
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
    if (linkMode !== "live" || !dateUtc) {
      setPlanetPositions([]);
      return;
    }
    let cancelled = false;
    void getPlanetPositions({ date_utc: dateUtc })
      .then((res) => {
        if (cancelled) return;
        setPlanetPositions(
          (res.planets ?? [])
            .filter((p) => (BODY_IDS as string[]).includes(p.body_id))
            .map((p) => ({
              body_id: p.body_id as SceneBodyId,
              r_km: p.r_km,
            })),
        );
      })
      .catch(() => {
        if (!cancelled) setPlanetPositions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [dateUtc, linkMode]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clearSelection("keyboard");
        setFocusName(null);
        return;
      }
      if (planetChoiceEnabled) {
        if (event.key === "1") {
          visitPlanet("Earth");
          selectPlanet("planet.399", "keyboard");
        }
        if (event.key === "2") {
          visitPlanet("Mars");
          selectPlanet("planet.499", "keyboard");
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
    setSelectedShuttleId(first?.id ?? null);
    setTrip({
      origin: bodyId,
      shuttleClass: first?.class ?? "standard",
      shuttleId: first?.id ?? null,
    });
  }

  function pickShuttle(shuttle: FleetShuttle) {
    setSelectedShuttleId(shuttle.id);
    setTrip({ shuttleClass: shuttle.class, shuttleId: shuttle.id });
  }

  return (
    <div className="app-shell sci-fi">
      <div className="scene-layer">
        <OrbitScene
          selectedId={selectedId}
          selectionEnabled={planetChoiceEnabled && !blackout}
          onSelect={(id) => {
            const name = id === "planet.399" ? "Earth" : "Mars";
            visitPlanet(name);
            selectPlanet(id);
          }}
          onFocusName={(name) => visitPlanet(name)}
          focusName={focusName}
          plan={scenePlan}
          snapshot={sceneSnapshot}
          fleet={sceneFleet}
          mockFleet={false}
          planetPositions={planetPositions}
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
        controllerSource={controllerSource}
        snapshot={snapshot}
        lastError={lastError}
        destinationName={destinationLabel}
      />

      <aside className="glass panel-left launch-aside" aria-label="Launch">
        <LaunchPanel
          originBodyId={originBodyId}
          destinationBodyId={destinationBodyId}
          dockedShuttles={dockedShuttles}
          shuttleId={selectedShuttleId}
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
          onResetFleet={() => void resetFleet()}
          onFaultSingle={() => void injectFault("single")}
          onFaultDivergence={() => void injectFault("divergence")}
        />
        <EngineerDrawer
          plan={selectedPlan}
          snapshot={snapshot}
          faultHistory={faultHistory}
          dataMode={dataMode}
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
