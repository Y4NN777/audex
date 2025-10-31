import type { BatchSummary, BatchTimelineEntry } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
  eventsConnected: boolean;
  eventsAvailable: boolean;
  connectionError?: string | null;
  onRefresh?: () => void;
};

const STAGE_DICTIONARY: Record<string, { label: string; description?: string }> = {
  "ingestion:received": { label: "Ingestion", description: "Fichiers reçus et stockés" },
  "metadata:extracted": { label: "Métadonnées", description: "Extraction des métadonnées" },
  "vision:start": { label: "Vision", description: "Analyse visuelle en cours" },
  "vision:complete": { label: "Vision", description: "Analyse visuelle terminée" },
  "ocr:warmup:start": { label: "OCR", description: "Initialisation du moteur EasyOCR" },
  "ocr:warmup:complete": { label: "OCR", description: "EasyOCR prêt" },
  "ocr:warmup:error": { label: "OCR", description: "Erreur de chargement EasyOCR" },
  "ocr:start": { label: "OCR", description: "Lecture OCR en cours" },
  "ocr:complete": { label: "OCR", description: "Textes OCR prêts" },
  "analysis:start": { label: "Analyse IA", description: "Synthèse IA démarrée" },
  "analysis:status": { label: "Analyse IA", description: "Pipeline en cours" },
  "analysis:complete": { label: "Analyse IA", description: "Synthèse IA terminée" },
  "scoring:complete": { label: "Scoring", description: "Score de risque calculé" },
  "report:generated": { label: "Rapport", description: "PDF généré" },
  "report:available": { label: "Rapport", description: "PDF disponible au téléchargement" },
  "pipeline:error": { label: "Erreur", description: "Incident durant le traitement" }
};

export function TimelinePanel({ batch, eventsConnected, eventsAvailable, connectionError, onRefresh }: Props) {
  const timeline = (batch?.timeline ?? []).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const hasData = timeline.length > 0;

  return (
    <section className="card">
      <div className="section-header">
        <h2>Chronologie pipeline</h2>
        <span className="pill">{timeline.length}</span>
      </div>

      <div className="timeline-header">
        <div className={`timeline-status ${eventsAvailable ? (eventsConnected ? "online" : "offline") : "unavailable"}`}>
          <span className="status-indicator" />
          <p>
            Flux temps réel&nbsp;
            <strong>{eventsAvailable ? (eventsConnected ? "connecté" : "en reconnection…") : "indisponible"}</strong>
          </p>
        </div>
        {onRefresh && (
          <button type="button" className="ghost-button" onClick={onRefresh}>
            Actualiser
          </button>
        )}
      </div>

      {connectionError && <p className="timeline-warning">{connectionError}</p>}

      {!eventsAvailable && (
        <p className="muted-text">
          Les évènements temps réel ne sont plus disponibles. Vous pouvez patienter ou rafraîchir manuellement les
          données.
        </p>
      )}

      {!hasData ? (
        <p className="muted-text">Les évènements apparaîtront ici dès que le pipeline publie ses étapes.</p>
      ) : (
        <ol className="timeline">
          {timeline.map((event) => {
            const meta = resolveStageMetadata(event);
            return (
              <li key={event.id}>
                <div className={`timeline-dot kind-${event.kind}`} />
                <div className="timeline-body">
                  <div className="timeline-chip">{meta.label}</div>
                  <p className="timeline-label">{event.label}</p>
                  <p className="timeline-meta">
                    {new Date(event.timestamp).toLocaleString()}
                    {typeof event.progress === "number" ? ` · ${event.progress}%` : ""}
                  </p>
                  {meta.description && <p className="timeline-description">{meta.description}</p>}
                  {renderDetails(event.details)}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function resolveStageMetadata(event: BatchTimelineEntry): { label: string; description?: string } {
  const dictionaryEntry = STAGE_DICTIONARY[event.stage];
  if (dictionaryEntry) {
    return dictionaryEntry;
  }
  const prefix = event.stage.split(":")[0];
  switch (prefix) {
    case "ingestion":
      return { label: "Ingestion" };
    case "metadata":
      return { label: "Métadonnées" };
    case "vision":
      return { label: "Vision" };
    case "ocr":
      return { label: "OCR" };
    case "analysis":
      return { label: "Analyse IA" };
    case "scoring":
      return { label: "Scoring" };
    case "report":
      return { label: "Rapport" };
    default:
      return { label: "Étape pipeline" };
  }
}

function renderDetails(details?: Record<string, unknown>) {
  if (!details || Object.keys(details).length === 0) {
    return null;
  }

  return (
    <div className="timeline-details-grid">
      {Object.entries(details).map(([key, value]) => (
        <div key={key} className="timeline-detail-row">
          <span className="timeline-detail-key">{translateDetailKey(key)}</span>
          <span className="timeline-detail-value">{formatDetailValue(value)}</span>
        </div>
      ))}
    </div>
  );
}

function translateDetailKey(key: string): string {
  switch (key) {
    case "fileCount":
      return "Nombre de fichiers";
    case "hasMetadata":
      return "Métadonnées";
    case "hash":
      return "Hash";
    case "path":
      return "Chemin";
    case "message":
      return "Message";
    case "languages":
      return "Langues";
    case "file":
      return "Fichier";
    case "position":
      return "Position";
    case "total":
      return "Total";
    default:
      return key;
  }
}

function formatDetailValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return `${value}`;
  }
  if (typeof value === "boolean") {
    return value ? "Oui" : "Non";
  }
  return JSON.stringify(value);
}
