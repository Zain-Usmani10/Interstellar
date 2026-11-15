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
    resetMission,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const [focusName, setFocusName] = useState<string | null>("Mars");
  const [scenic, setScenic] = useState<{
    destination: string;
    progress: number;
  } | null>(null);

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const live = linkMode === "live";

  /** Mars = real controller mission; anything else = scenic destination. */
  const destinationName =
    !focusName || focusName === "Earth" ? "Mars" : focusName;
  const controllerMission = destinationName === "Mars";

  useEffect(() => {
    if (!scenic || scenic.progress >= 1) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      setScenic((s) => {
        if (!s) return s;
        const next = Math.min(1, s.progress + dt / 14);
        return { ...s, progress: next };
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [scenic?.destination, Boolean(scenic && scenic.progress < 1)]);

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
        void handleReset();
      } else if (
        key === "p" &&
        live &&
        controllerMission &&
        selectedPlan &&
        !commandBusy
      ) {
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

  async function handleReset() {
    setScenic(null);
    await resetMission();
  }

  async function handleAbort() {
    await sendCommand("abort");
    clearSelection("mouse");
  }

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
          scenic={scenic}
        />
      </div>

      <header className="glass brand-glass">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">
          {controllerMission
            ? "Earth → Mars mission"
            : `Earth → ${destinationName}`}
        </p>
      </header>

      <GlassStatus
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        snapshot={snapshot}
        lastError={lastError}
        destinationName={destinationName}
        scenicActive={Boolean(scenic)}
      />

      <aside className="glass panel-left" aria-label="Route and launch">
        <h2 className="panel-title">
          {controllerMission
            ? "Choose a route"
            : `Destination: ${destinationName}`}
        </h2>
        {controllerMission ? (
          <RouteCards
            leastFuel={routePlans.least_fuel}
            earliestArrival={routePlans.earliest_arrival}
            selectedPlanId={selectedPlan?.plan_id ?? null}
            disabled={commandBusy}
            onSelect={(id) => void selectPlanById(id)}
          />
        ) : (
          <p className="muted scenic-note">
            Controller missions are validated for Earth→Mars. Pick another
            world for an illustrative scenic flight (labeled on the scene —
            not MissionSnapshot).
          </p>
        )}
        <GuidedLaunch
          live={live}
          busy={commandBusy}
          hasPlan={Boolean(selectedPlan)}
          snapshot={snapshot}
          gates={gates}
          simFaultsEnabled={simFaultsEnabled}
          destinationName={destinationName}
          scenicActive={Boolean(scenic)}
          onPrepare={() => void prepareMission()}
          onArm={() => void sendCommand("arm")}
          onLaunch={() => void sendCommand("start")}
          onAbort={() => void handleAbort()}
          onReset={() => void handleReset()}
          onScenic={() => {
            if (controllerMission) return;
            setScenic({ destination: destinationName, progress: 0 });
          }}
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
