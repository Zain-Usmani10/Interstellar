import { MOCK_SNAPSHOT } from "../mock/missionSnapshot";

export function StatusStrip() {
  const s = MOCK_SNAPSHOT;
  return (
    <div className="status-strip" role="status" aria-label="Mission indicators">
      <span className="pill mock">mode: {s.data_mode}</span>
      <span className="pill">controller: {s.controller_source}</span>
      <span className="pill">NASA: {s.nasa_ephemeris}</span>
      <span className="pill">input: {s.input_source}</span>
      <span className="pill">link: {s.freshness}</span>
      <span className="pill">state: {s.state}</span>
    </div>
  );
}
