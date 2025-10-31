import type { BatchSummary, Observation } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
};

export function ObservationsPanel({ batch }: Props) {
  if (!batch) {
    return (
      <section className="card">
        <h2>Observations IA</h2>
        <p className="muted-text">Synchronisez un lot complété pour afficher les observations locales et Gemini.</p>
      </section>
    );
  }

  const observations = batch.observations ?? [];
  const local = observations.filter((obs) => (obs.source ?? "").toLowerCase() !== "gemini");
  const gemini = observations.filter((obs) => (obs.source ?? "").toLowerCase() === "gemini");

  return (
    <section className="card">
      <div className="section-header">
        <h2>Observations IA</h2>
        <span className="pill">{observations.length}</span>
      </div>

      {observations.length === 0 ? (
        <p className="muted-text">Aucune observation détectée pour ce lot.</p>
      ) : (
        <div className="observation-grid">
          <ObservationGroup title="Vision locale" observations={local} />
        </div>
      )}
    </section>
  );
}

function ObservationGroup({ title, observations }: { title: string; observations: Observation[] }) {
  if (observations.length === 0) {
    return (
      <div className="observation-group empty">
        <h3>{title}</h3>
        <p className="muted-text">Aucune donnée pour le moment.</p>
      </div>
    );
  }

  return (
    <div className="observation-group">
      <h3>{title}</h3>
      <ul>
        {observations.map((obs, index) => {
          const severityRaw = (obs.severity ?? "inconnu").toLowerCase();
          const severityClass = severityRaw.replace(/[^a-z]/g, "") || "inconnu";
          const contextValue = obs.extra?.context;
          return (
            <li key={`${obs.filename}-${obs.label}-${index}`}>
              <div className={`badge severity-${severityClass}`}>{obs.severity ?? "N/A"}</div>
              <div className="observation-content">
                <p className="observation-label">{obs.label}</p>
                <p className="observation-meta">
                  {obs.filename}
                  {typeof obs.confidence === "number" ? ` · ${(obs.confidence * 100).toFixed(0)}%` : ""}
                  {obs.createdAt ? ` · ${new Date(obs.createdAt).toLocaleString()}` : ""}
                </p>
                {typeof contextValue === "string" && <p className="observation-context">{contextValue}</p>}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
