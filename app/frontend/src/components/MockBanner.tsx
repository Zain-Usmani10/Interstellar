export function MockBanner() {
  return (
    <div className="mock-banner" role="status">
      <strong>MOCK DATA</strong>
      <span>
        Local fixtures only — not NASA/JPL Horizons, not EONET, not FPGA
        telemetry. Swap to real APIs when contracts land.
      </span>
    </div>
  );
}
