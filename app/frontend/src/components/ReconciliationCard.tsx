/** Layout placeholder for §18.7 "While out of contact" from `reconciliation`. */

export type ReconciliationView = {
  blackoutStartTick: number | null;
  blackoutEndTick: number | null;
  eventsDuringBlackout: string[];
  estimateMatched: boolean | null;
  differences: string[];
};

type Props = {
  data: ReconciliationView | null;
  preview?: boolean;
};

export function ReconciliationCard({ data, preview }: Props) {
  if (!data) return null;
  return (
    <aside
      className="reconciliation-card glass"
      aria-label="While out of contact"
    >
      <h3 className="reconciliation-title">While out of contact</h3>
      <p className="reconciliation-meta">
        Ticks {data.blackoutStartTick ?? "—"} → {data.blackoutEndTick ?? "—"}
        {data.estimateMatched == null
          ? ""
          : data.estimateMatched
            ? " · estimate matched"
            : " · estimate differed"}
      </p>
      {data.eventsDuringBlackout.length ? (
        <ul className="reconciliation-list">
          {data.eventsDuringBlackout.map((event) => (
            <li key={event}>{event}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">No events recorded during blackout.</p>
      )}
      {data.differences.length ? (
        <ul className="reconciliation-diffs">
          {data.differences.map((diff) => (
            <li key={diff}>{diff}</li>
          ))}
        </ul>
      ) : null}
      {preview ? (
        <p className="reconciliation-preview-tag">
          Layout preview · contracts 1.2.0 pending
        </p>
      ) : null}
    </aside>
  );
}
