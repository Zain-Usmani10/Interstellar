import { MOCK_SNAPSHOT } from "../mock/missionSnapshot";
import type { LinkMode } from "../state/useCoreBridge";

type Props = {
  linkMode: LinkMode;
  controllerLabel: string;
  dataMode: string;
  lastError: string | null;
};

export function StatusStrip({
  linkMode,
  controllerLabel,
  dataMode,
  lastError,
}: Props) {
  const s = MOCK_SNAPSHOT;
  return (
    <div className="status-strip" role="status" aria-label="Mission indicators">
      <span className={linkMode === "live" ? "pill" : "pill mock"}>
        link: {linkMode}
      </span>
      <span className="pill">controller: {controllerLabel}</span>
      <span className="pill">NASA/data: {dataMode}</span>
      <span className="pill">input: mouse (+ optional BCI)</span>
      <span className="pill">mission: {s.state}</span>
      {lastError ? <span className="pill mock">err: {lastError}</span> : null}
    </div>
  );
}
