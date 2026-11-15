import { useEffect, useMemo } from "react";
import type { ComponentProps } from "react";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { FaultHistory } from "./components/FaultHistory";
import { MissionActions } from "./components/MissionActions";
import { MissionPanel } from "./components/MissionPanel";
import { MockBanner } from "./components/MockBanner";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { PlanetPicker } from "./components/PlanetPicker";
import { RouteCompare } from "./components/RouteCompare";
import { StatusStrip } from "./components/StatusStrip";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import { useCoreBridge } from "./state/useCoreBridge";

/**
 * Affan's OrbitScene declares optional plan/snapshot once #21 lands.
 * Until then we forward them at runtime without editing src/scene/.
 */
type OrbitSceneProps = ComponentProps<typeof OrbitScene> & {
  plan?: unknown;
  snapshot?: unknown;
};

export default function App() {
  const {
    linkMode,
    controllerLabel,
    dataMode,
    inputSourceLabel,
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
    createMissionFromSelected,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const live = linkMode === "live";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clearSelection("keyboard");
        return;
      }
      if (planetChoiceEnabled) {
        if (event.key === "1") selectPlanet("planet.399", "keyboard");
        if (event.key === "2") selectPlanet("planet.499", "keyboard");
      }

      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "c" && live && selectedPlan && gates.canCreate && !commandBusy) {
        event.preventDefault();
        void createMissionFromSelected();
      } else if (key === "u" && live && gates.canUpload && !commandBusy) {
        event.preventDefault();
        void sendCommand("upload");
      } else if (key === "r" && live && gates.canArm && !commandBusy) {
        event.preventDefault();
        void sendCommand("arm");
      } else if (key === "g" && live && gates.canStart && !commandBusy) {
        event.preventDefault();
        void sendCommand("start");
      } else if (key === "x" && live && gates.canAbort && !commandBusy) {
        event.preventDefault();
        void sendCommand("abort");
      } else if (key === "l" && live && gates.canClear && !commandBusy) {
        event.preventDefault();
        void sendCommand("clear");
      } else if (key === "f" && simFaultsEnabled && !commandBusy) {
        event.preventDefault();
        void injectFault("single");
      } else if (key === "d" && simFaultsEnabled && !commandBusy) {
        event.preventDefault();
        void injectFault("divergence");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    clearSelection,
    commandBusy,
    createMissionFromSelected,
    gates,
    injectFault,
    live,
    planetChoiceEnabled,
    selectPlanet,
    selectedPlan,
    sendCommand,
    simFaultsEnabled,
  ]);

  const sceneProps = {
    selectedId,
    selectionEnabled: planetChoiceEnabled,
    onSelect: selectPlanet,
    plan: scenePlan,
    snapshot: sceneSnapshot,
  } as OrbitSceneProps;

  return (
    <div className="app-shell">
      <MockBanner linkMode={linkMode} />
      <StatusStrip
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        inputSourceLabel={inputSourceLabel}
        snapshot={snapshot}
        lastError={lastError}
      />
      <header className="top-bar">
        <div>
          <p className="brand">Interstellar</p>
          <h1>Mission control</h1>
          <p className="lede">
            Compare routes, create a mission, upload → arm → start. The rocket
            moves only when MissionSnapshot says so.
          </p>
        </div>
        <PlanetPicker
          selectedId={selectedId}
          enabled={planetChoiceEnabled}
          onSelect={selectPlanet}
        />
      </header>

      <main className="stage">
        <div className="canvas-column">
          <div className="canvas-wrap">
            <OrbitScene {...sceneProps} />
          </div>
          <div className="bci-dock" aria-label="Optional brain widget">
            <BciSlot />
          </div>
        </div>
        <div className="side-stack">
          <RouteCompare
            leastFuel={routePlans.least_fuel}
            earliestArrival={routePlans.earliest_arrival}
            selectedPlanId={selectedPlan?.plan_id ?? null}
            disabled={commandBusy}
            onSelect={(id) => void selectPlanById(id)}
          />
          <MissionActions
            live={live}
            busy={commandBusy}
            gates={gates}
            simFaultsEnabled={simFaultsEnabled}
            hasSelectedPlan={Boolean(selectedPlan)}
            onCreate={() => void createMissionFromSelected()}
            onCommand={(cmd) => void sendCommand(cmd)}
            onFault={(kind) => void injectFault(kind)}
          />
          {card ? (
            <PlanetInfoCard
              planet={card}
              status={cardStatus === "idle" ? "ready" : cardStatus}
              onClose={() => clearSelection("mouse")}
            />
          ) : (
            <aside className="info-card idle" aria-live="polite">
              <p className="eyebrow">Planet explorer</p>
              <h2>Earth or Mars</h2>
              <p>
                Optional: open a sourced info card. Mission launch does not
                require a planet selection.
              </p>
              <p className="muted">Keys: 1 Earth · 2 Mars · Esc back</p>
            </aside>
          )}
          <MissionPanel plan={selectedPlan} snapshot={snapshot} />
          <FaultHistory entries={faultHistory} />
        </div>
      </main>
    </div>
  );
}
