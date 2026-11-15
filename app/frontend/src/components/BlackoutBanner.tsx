/** Plan §18.7 — shown while `link.blackout` is true. */

type Props = {
  visible: boolean;
};

export function BlackoutBanner({ visible }: Props) {
  if (!visible) return null;
  return (
    <div
      className="blackout-banner"
      role="status"
      aria-live="polite"
      aria-label="Contact lost"
    >
      <p className="blackout-title">Contact lost</p>
      <p className="blackout-copy">
        No telemetry. Confirmed marker holds the last received position; ghost
        path values are estimates only.
      </p>
    </div>
  );
}
