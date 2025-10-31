import type { BatchSummary, BatchTimelineEntry } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
  eventsConnected: boolean;
  eventsAvailable: boolean;
  connectionError?: string | null;
  onRefresh?: () => void;
};

const STAGE_DICTIONARY: Record<string, { label: string; description?: string }> = {
  "ingestion:received": { label: "Déposé", description: "Fichiers reçus sur la plateforme." },
  "metadata:extracted": { label: "Préparation", description: "Information de base extraite des documents." },
  "analysis:start": { label: "Analyse IA", description: "Début de l’examen automatique des documents." },
  "analysis:complete": { label: "Analyse IA", description: "Analyse automatique finalisée." },
  "scoring:complete": { label: "Évaluation", description: "Score de risque calculé pour ce lot." },
  "report:generated": { label: "Rapport", description: "Rapport en cours de finalisation." },
  "report:available": { label: "Rapport prêt", description: "Rapport disponible au téléchargement." },
  "pipeline:error": { label: "Incident", description: "Un incident nécessite une vérification." }
};

const HIDDEN_STAGES = new Set<string>([
  "vision:start",
  "vision:complete",
  "ocr:warmup:start",
  "ocr:warmup:complete",
  "ocr:warmup:error",
  "ocr:start",
  "ocr:complete",
  "analysis:status"
]);

function dedupeTimeline(events: BatchTimelineEntry[]): BatchTimelineEntry[] {
  const result: BatchTimelineEntry[] = [];
  for (const event of events) {
    const last = result[result.length - 1];
    if (
      last &&
      last.stage === event.stage &&
      new Date(last.timestamp).getTime() === new Date(event.timestamp).getTime() &&
      (last.progress ?? null) === (event.progress ?? null)
    ) {
      continue;
    }
    result.push(event);
  }
  return result;
}

export function TimelinePanel({ batch, eventsConnected, eventsAvailable, connectionError, onRefresh }: Props) {
  const rawTimeline = (batch?.timeline ?? []).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const timeline = dedupeTimeline(rawTimeline.filter((event) => !HIDDEN_STAGES.has(event.stage)));
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
        <div className="timeline-scroll">
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
        </div>
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

const VISIBLE_DETAIL_KEYS = new Set(["fileCount", "hasMetadata", "hash", "message", "reportUrl", "report_url"]);

function renderDetails(details?: Record<string, unknown>) {
  if (!details || Object.keys(details).length === 0) {
    return null;
  }

  const entries = Object.entries(details).filter(([key]) => VISIBLE_DETAIL_KEYS.has(key));
  if (entries.length === 0) {
    return null;
  }

  return (
    <details className="timeline-details">
      <summary>Détails techniques</summary>
      <div className="timeline-details-grid">
        {entries.map(([key, value]) => (
          <div key={key} className="timeline-detail-row">
            <span className="timeline-detail-key">{translateDetailKey(key)}</span>
            <span className="timeline-detail-value">{formatDetailValue(value)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

function translateDetailKey(key: string): string {
  switch (key) {
    case "fileCount":
      return "Nombre de fichiers déposés";
    case "hasMetadata":
      return "Métadonnées détectées";
    case "hash":
      return "Code d’intégrité";
    case "reportUrl":
    case "report_url":
      return "Lien du rapport";
    case "message":
      return "Message";
    default:
      return key;
  }
}

function formatDetailValue(value: unknown): string {
  if (typeof value === "string") {
    if (value.startsWith("tmp/") || value.startsWith("/tmp/")) {
      return "Lien technique disponible dans le journal";
    }
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
