import type { LinkMode } from "../state/useCoreBridge";

type Props = { linkMode: LinkMode };

export function MockBanner({ linkMode }: Props) {
  if (linkMode === "live") {
    return (
      <div className="mock-banner live" role="status">
        <strong>LIVE CORE</strong>
        <span>
          Selection goes through the backend input session + WS{" "}
          <code>selection</code> events, then{" "}
          <code>GET /api/v1/planets/&#123;id&#125;/info</code>. Mission panel is
          still stubbed.
        </span>
      </div>
    );
  }

  return (
    <div className="mock-banner" role="status">
      <strong>{linkMode === "connecting" ? "CONNECTING" : "OFFLINE MOCK"}</strong>
      <span>
        {linkMode === "connecting"
          ? "Reaching backend at 127.0.0.1:8000…"
          : "Backend unreachable — local fixtures only (highlight/card still work). Start with app/scripts/start-backend.sh simulator."}
      </span>
    </div>
  );
}
