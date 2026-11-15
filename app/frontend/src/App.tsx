import { useEffect } from "react";
import { MockBanner } from "./components/MockBanner";
import { MissionPanel } from "./components/MissionPanel";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { PlanetPicker } from "./components/PlanetPicker";
import { StatusStrip } from "./components/StatusStrip";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import { useCoreBridge } from "./state/useCoreBridge";

export default function App() {
  const {
    linkMode,
    controllerLabel,
    dataMode,
    selectedId,
    card,
    cardStatus,
    lastError,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "1") selectPlanet("planet.399", "keyboard");
      if (event.key === "2") selectPlanet("planet.499", "keyboard");
      if (event.key === "Escape") clearSelection("keyboard");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearSelection, selectPlanet]);

  return (
    <div className="app-shell">
      <MockBanner linkMode={linkMode} />
      <StatusStrip
        linkMode={linkMode}
        controllerLabel={controllerLabel}
        dataMode={dataMode}
        lastError={lastError}
      />
      <header className="top-bar">
        <div>
          <p className="brand">Interstellar</p>
          <h1>Planet explorer</h1>
          <p className="lede">
            Click Earth or Mars (or keys 1–2). Mouse/keyboard and EEG share the
            same core selection path when the backend is live.
          </p>
        </div>
        <PlanetPicker selectedId={selectedId} onSelect={selectPlanet} />
      </header>

      <main className="stage">
        <div className="canvas-wrap">
          <OrbitScene selectedId={selectedId} onSelect={selectPlanet} />
        </div>
        <div className="side-stack">
          {card ? (
            <PlanetInfoCard
              planet={card}
              status={cardStatus === "idle" ? "ready" : cardStatus}
              onClose={() => clearSelection("mouse")}
            />
          ) : (
            <aside className="info-card idle" aria-live="polite">
              <p className="eyebrow">No planet selected</p>
              <h2>Choose Earth or Mars</h2>
              <p>
                Ordinary input and optional brain intents both wait for the core{" "}
                <code>selection</code> event before the card loads.
              </p>
              <p className="muted">Keys: 1 Earth · 2 Mars · Esc back</p>
            </aside>
          )}
          <MissionPanel />
        </div>
      </main>

      <BciSlot />
    </div>
  );
}
