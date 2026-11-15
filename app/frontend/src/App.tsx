import { useEffect, useMemo, useState } from "react";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { EngineerDrawer } from "./components/EngineerDrawer";
import { GlassStatus } from "./components/GlassStatus";
import { GuidedLaunch } from "./components/GuidedLaunch";
import { PlanetBar } from "./components/PlanetBar";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { RouteCards } from "./components/RouteCards";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
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
    snapshot,
    faultHistory,
    gates,
    simFaultsEnabled,
    selectPlanById,
    prepareMission,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const [focusName, setFocusName] = useState<string | null>(null);
  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const live = linkMode === "live";

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
      if (key === "p" && live && selectedPlan && !commandBusy) {
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
  }, [
    clearSelection,
    commandBusy,
    gates,
    live,
    planetChoiceEnabled,
    prepareMission,
    selectPlanet,
    selectedPlan,
    sendCommand,
  ]);

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
          focusName={focusName}
          plan={scenePlan}
          snapshot={sceneSnapshot}
        />
      </div>

      <header className="glass brand-glass">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">Earth → Mars mission</p>
      </header>

      <GlassStatus
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        snapshot={snapshot}
        lastError={lastError}
      />

      <aside className="glass panel-left" aria-label="Route and launch">
        <h2 className="panel-title">Choose a route</h2>
        <RouteCards
          leastFuel={routePlans.least_fuel}
          earliestArrival={routePlans.earliest_arrival}
          selectedPlanId={selectedPlan?.plan_id ?? null}
          disabled={commandBusy}
          onSelect={(id) => void selectPlanById(id)}
        />
        <GuidedLaunch
          live={live}
          busy={commandBusy}
          hasPlan={Boolean(selectedPlan)}
          snapshot={snapshot}
          gates={gates}
          simFaultsEnabled={simFaultsEnabled}
          onPrepare={() => void prepareMission()}
          onArm={() => void sendCommand("arm")}
          onLaunch={() => void sendCommand("start")}
          onAbort={() => void sendCommand("abort")}
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
