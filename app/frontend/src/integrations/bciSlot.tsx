import { useEffect, useState, type ComponentType } from "react";

/**
 * Affan owns `app/frontend/src/bci/`. This slot only mounts his widget when
 * present and VITE_BRAIN_ENABLED=true. Core selection WS events still own
 * highlight/card — BrainWidget must not drive those itself.
 */
const bciModules = import.meta.glob("../bci/BrainWidget.tsx");

type DecisionResult = {
  event_id: string;
  accepted: boolean;
  reason: string;
  new_context_revision: number;
};

type BrainWidgetProps = {
  enabled?: boolean;
  bridgeUrl?: string;
  onDecision?: (result: DecisionResult) => void;
  onActiveChange?: (active: boolean) => void;
};

type BrainWidgetComponent = ComponentType<BrainWidgetProps>;

export function BciSlot() {
  const enabled = import.meta.env.VITE_BRAIN_ENABLED === "true";
  const [Widget, setWidget] = useState<BrainWidgetComponent | null>(null);

  useEffect(() => {
    const loader = bciModules["../bci/BrainWidget.tsx"];
    if (!loader) {
      return;
    }
    let cancelled = false;
    loader().then((mod) => {
      if (cancelled) return;
      const component = (mod as { BrainWidget?: BrainWidgetComponent }).BrainWidget;
      if (component) setWidget(() => component);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!enabled || !Widget) {
    return (
      <div className="bci-slot" data-bci-slot="reserved" hidden aria-hidden>
        {/* Affan: place BrainWidget.tsx under src/bci/; enable with VITE_BRAIN_ENABLED=true */}
      </div>
    );
  }

  return (
    <div className="bci-slot" data-bci-slot="mounted">
      <Widget
        enabled={enabled}
        bridgeUrl="ws://127.0.0.1:8766"
        onDecision={(result) => {
          // Acknowledgment only — highlight/card come from core selection events.
          console.info("[bci] core decision acknowledgment", result);
        }}
      />
    </div>
  );
}
