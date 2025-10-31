import type { BatchSummary } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
};

export function TimelinePanel({ batch }: Props) {
  if (!batch) {
    return (
      <section className="card timeline-card">
        <h2>Chronologie pipeline</h2>
        <p className="muted-text">Les évènements du pipeline s’affichent ici dès qu’un lot est en cours de traitement.</p>
      </section>
    );
  }

  const timeline = batch.timeline ?? [];

  return (
    <section className="card timeline-card">
      <div className="section-header">
        <h2>Chronologie pipeline</h2>
        <span className="pill">{timeline.length}</span>
      </div>

      {timeline.length === 0 ? (
        <p className="muted-text">Les évènements seront disponibles dès que le pipeline publie des étapes.</p>
      ) : (
        <ol className="timeline">
          {timeline.map((event) => (
            <li key={event.id}>
              <div className={`timeline-dot kind-${event.kind}`} />
              <div className="timeline-body">
                <p className="timeline-label">{event.label}</p>
                <p className="timeline-meta">
                  {new Date(event.timestamp).toLocaleString()}
                  {typeof event.progress === "number" ? ` · ${event.progress}%` : ""}
                </p>
                {event.details && Object.keys(event.details).length > 0 && (
                  <pre className="timeline-details">{JSON.stringify(event.details, null, 2)}</pre>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
