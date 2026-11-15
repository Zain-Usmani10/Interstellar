/** Layout placeholder for §18.7 — wire to `link.blackout` after contracts 1.2.0. */

type Props = {
  visible: boolean;
  preview?: boolean;
};

export function BlackoutBanner({ visible, preview }: Props) {
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
        No telemetry while the blackout is active. Confirmed marker holds the
        last received position; the ghost path is a labelled estimate only.
      </p>
      {preview ? (
        <p className="blackout-preview-tag">Layout preview · contracts 1.2.0 pending</p>
      ) : null}
    </div>
  );
}
