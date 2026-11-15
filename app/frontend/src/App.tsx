import { useEffect, useMemo, useState } from "react";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { BlackoutBanner } from "./components/BlackoutBanner";
import { EngineerDrawer } from "./components/EngineerDrawer";
import { GlassStatus } from "./components/GlassStatus";
import { GuidedLaunch } from "./components/GuidedLaunch";
import { PlanetBar } from "./components/PlanetBar";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { ReconciliationCard } from "./components/ReconciliationCard";
import { RouteCards } from "./components/RouteCards";
import { TripPicker } from "./components/TripPicker";
import { TripReadout } from "./components/TripReadout";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import { routePoints } from "./scene/flightState";
import { planetName } from "./state/planetBodies";
import { useCoreBridge } from "./state/useCoreBridge";

/** Layout-only preview until contracts 1.2.0 (`?ccsPreview=1`). */
function useCcsPreview(): boolean {
  return useMemo(
    () =>
      import.meta.env.DEV &&
      new URLSearchParams(location.search).has("ccsPreview"),
    [],
  );
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
    routesAvailable,
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

  const [focusName, setFocusName] = useState<string | null>("Mars");
  const ccsPreview = useCcsPreview();

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const live = linkMode === "live";
  const originLabel = planetName(originBodyId);
  const destinationLabel = planetName(destinationBodyId);
  const routeLabel = `${originLabel} → ${destinationLabel}`;
  const tripLocked = commandBusy || Boolean(
    snapshot &&
      snapshot.state !== "IDLE" &&
      snapshot.state !== "UNKNOWN" &&
      snapshot.state !== "ABORTED" &&
      snapshot.state !== "COMPLETE",
  );

  // Live wiring waits for contracts 1.2.0; preview uses static layout samples.
  const blackout = Boolean(snapshot?.link?.blackout) || ccsPreview;
  const daysToArrival = blackout
    ? (snapshot?.estimate?.days_to_arrival ?? (ccsPreview ? 187 : null))
    : (snapshot?.trip?.days_to_arrival ?? (ccsPreview ? 300 : null));
  const tripDays = snapshot?.trip?.trip_days ?? (ccsPreview ? 300 : null);
  const estimatedReadout = Boolean(blackout && (snapshot?.estimate || ccsPreview));

  const estimateOverlay = useMemo(() => {
    if (!blackout) return null;
    const path = routePoints(scenePlan);
    if (path.length < 2) return null;
    // Layout sample only: mid-path marker. Live mode will use estimate.r_km.
    const idx = Math.min(path.length - 1, Math.floor(path.length * 0.45));
    return {
      position: path[idx],
      path,
      label: ccsPreview ? "estimate (layout preview)" : "estimate",
    };
  }, [blackout, ccsPreview, scenePlan]);

  const reconciliation = snapshot?.reconciliation
    ? {
        blackoutStartTick: snapshot.reconciliation.blackout_start_tick,
        blackoutEndTick: snapshot.reconciliation.blackout_end_tick,
        eventsDuringBlackout: snapshot.reconciliation.events_during_blackout,
        estimateMatched: snapshot.reconciliation.estimate_matched,
        differences: snapshot.reconciliation.differences,
      }
    : ccsPreview
      ? {
          blackoutStartTick: 120,
          blackoutEndTick: 6005,
          eventsDuringBlackout: ["departure (confirmed after sync)"],
          estimateMatched: false,
          differences: [
            "Estimate expected capture; shuttle reported SAFE (layout sample)",
          ],
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
        }
        if (event.key === "2") {
          setFocusName("Mars");
          selectPlanet("planet.499", "keyboard");
        }
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "o") {
        event.preventDefault();
        void resetMission();
      } else if (key === "p" && live && selectedPlan && !commandBusy) {
        event.preventDefault();
        void prepareMission();
      } else if (key === "r" && live && gates.canArm && !commandBusy) {
        event.preventDefault();
        void sendCommand("arm");
      } else if (key === "g" && live && gates.canStart && !commandBusy) {
        event.preventDefault();
        void sendCommand("start");
      } else if (key === "x" && live && gates.canAbort && !commandBusy) {
        event.preventDefault();
        void sendCommand("abort");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="app-shell">
      <div className="scene-layer">
        <OrbitScene
          selectedId={selectedId}
          selectionEnabled={planetChoiceEnabled}
          onSelect={(id) => {
            const name = id === "planet.399" ? "Earth" : "Mars";
            setFocusName(name);
            selectPlanet(id);
          }}
          onFocusName={setFocusName}
          focusName={focusName}
          plan={scenePlan}
          snapshot={sceneSnapshot}
          estimateOverlay={estimateOverlay}
        />
      </div>

      <header className="glass brand-glass">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">{routeLabel}</p>
      </header>

      <BlackoutBanner visible={blackout} preview={ccsPreview} />

      <GlassStatus
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        snapshot={snapshot}
        lastError={lastError}
        destinationName={destinationLabel}
      />

      <aside className="glass panel-left" aria-label="Route and launch">
        <h2 className="panel-title">Choose a trip</h2>
        <TripPicker
          originBodyId={originBodyId}
          destinationBodyId={destinationBodyId}
          disabled={tripLocked || blackout}
          onOrigin={(id) => setTrip({ origin: id })}
          onDestination={(id) => {
            setTrip({ destination: id });
            setFocusName(planetName(id));
          }}
        />
        <TripReadout
          daysToArrival={daysToArrival}
          tripDays={tripDays}
          tMinusLabel={ccsPreview ? "T−00:04" : null}
          estimated={estimatedReadout}
          preview={ccsPreview}
        />
        <h2 className="panel-title panel-title-sub">Choose a route</h2>
        {routesAvailable ? (
          <RouteCards
            leastFuel={routePlans.least_fuel}
            earliestArrival={routePlans.earliest_arrival}
            selectedPlanId={selectedPlan?.plan_id ?? null}
            disabled={commandBusy || blackout}
            onSelect={(id) => void selectPlanById(id)}
          />
        ) : (
          <p className="muted scenic-note">
            Route being calculated / not available yet for {routeLabel}.
            Earth→Mars plans are available today; other pairs arrive with
            planner work (#38).
          </p>
        )}
        <GuidedLaunch
          live={live}
          busy={commandBusy}
          hasPlan={Boolean(selectedPlan)}
          snapshot={snapshot}
          gates={gates}
          simFaultsEnabled={simFaultsEnabled}
          routeLabel={routeLabel}
          blackoutActive={blackout}
          canStartBlackout={false}
          canEndBlackout={false}
          onPrepare={() => void prepareMission()}
          onArm={() => void sendCommand("arm")}
          onLaunch={() => void sendCommand("start")}
          onAbort={() => {
            void sendCommand("abort");
            clearSelection("mouse");
          }}
          onReset={() => void resetMission()}
          onFaultSingle={() => void injectFault("single")}
          onFaultDivergence={() => void injectFault("divergence")}
        />
        <EngineerDrawer
          plan={selectedPlan}
          snapshot={snapshot}
          faultHistory={faultHistory}
        />
      </aside>

      <ReconciliationCard data={reconciliation} preview={ccsPreview} />

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
        onVisit={setFocusName}
        onSelectEarthMars={selectPlanet}
      />
    </div>
  );
}
