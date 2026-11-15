import type { FaultHistoryEntry } from "../api/missionTypes";

type Props = {
  entries: FaultHistoryEntry[];
};

export function FaultHistory({ entries }: Props) {
  return (
    <section className="fault-history" aria-label="Fault history">
      <h3>Fault history</h3>
      {entries.length === 0 ? (
        <p className="muted">No masked faults, SAFE, ABORTED, or uncaptured yet.</p>
      ) : (
        <ol className="fault-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <span className="fault-kind">{entry.kind}</span>
              <span className="muted">seq {entry.at_seq}</span>
              <span>{entry.detail}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
