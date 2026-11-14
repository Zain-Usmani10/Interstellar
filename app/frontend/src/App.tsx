import { useEffect, useState } from "react";
import { MockBanner } from "./components/MockBanner";
import { MissionPanel } from "./components/MissionPanel";
import { PlanetInfoCard } from "./components/PlanetInfoCard";
import { PlanetPicker } from "./components/PlanetPicker";
import { StatusStrip } from "./components/StatusStrip";
import { BciSlot } from "./integrations/bciSlot";
import {
  getPlanetByTargetId,
  type PlanetTargetId,
} from "./mock/planetInfo";
import { OrbitScene } from "./scene/OrbitScene";

export default function App() {
  const [selectedId, setSelectedId] = useState<PlanetTargetId | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "1") setSelectedId("planet.399");
      if (event.key === "2") setSelectedId("planet.499");
      if (event.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selected =
    selectedId === null ? null : getPlanetByTargetId(selectedId);

  return (
    <div className="app-shell">
      <MockBanner />
      <StatusStrip />
      <header className="top-bar">
        <div>
          <p className="brand">Interstellar</p>
          <h1>Planet explorer</h1>
          <p className="lede">
            Click Earth or Mars in the scene (or use the buttons / keys 1–2).
            Selection highlights the body and opens its information card.
          </p>
        </div>
        <PlanetPicker selectedId={selectedId} onSelect={setSelectedId} />
      </header>

      <main className="stage">
        <div className="canvas-wrap">
          <OrbitScene selectedId={selectedId} onSelect={setSelectedId} />
        </div>
        <div className="side-stack">
          {selected ? (
            <PlanetInfoCard
              planet={selected}
              onClose={() => setSelectedId(null)}
            />
          ) : (
            <aside className="info-card idle" aria-live="polite">
              <p className="eyebrow">No planet selected</p>
              <h2>Choose Earth or Mars</h2>
              <p>
                Ordinary mouse/keyboard only in this milestone. Brain/EEG widget
                mounts later via the reserved BCI slot — core UI works without
                it.
              </p>
              <p className="muted">Keys: 1 Earth · 2 Mars · Esc close</p>
            </aside>
          )}
          <MissionPanel />
        </div>
      </main>

      <BciSlot />
    </div>
  );
}
