import { useEffect, useMemo, useState } from "react";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { EngineerDrawer } from "./components/EngineerDrawer";
import { GlassStatus } from "./components/GlassStatus";
import { GuidedLaunch } from "./components/GuidedLaunch";
import { PlanetBar } from "./components/PlanetBar";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { RouteCards } from "./components/RouteCards";
import { TripPicker } from "./components/TripPicker";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import { planetName } from "./state/planetBodies";
import { useCoreBridge } from "./state/useCoreBridge";

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
        />
      </div>

      <header className="glass brand-glass">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">{routeLabel}</p>
      </header>

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
          disabled={tripLocked}
          onOrigin={(id) => setTrip({ origin: id })}
          onDestination={(id) => {
            setTrip({ destination: id });
            setFocusName(planetName(id));
          }}
        />
        <h2 className="panel-title panel-title-sub">Choose a route</h2>
        {routesAvailable ? (
          <RouteCards
            leastFuel={routePlans.least_fuel}
            earliestArrival={routePlans.earliest_arrival}
            selectedPlanId={selectedPlan?.plan_id ?? null}
            disabled={commandBusy}
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
        selectionEnabled={planetChoiceEnabled}
        onVisit={setFocusName}
        onSelectEarthMars={selectPlanet}
      />
    </div>
  );
}
