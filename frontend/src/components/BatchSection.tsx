import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, FileText, Loader2 } from "lucide-react";

import type { BatchSummary, BatchTimelineEntry } from "../types/batch";
import { downloadReport } from "../services/reports";
import { useToast } from "./ToastProvider";

type Props = {
  title: string;
  batches: BatchSummary[];
  emptyMessage: string;
  onRetry?: (batchId: string) => Promise<void>;
  onRemove?: (batchId: string) => Promise<void>;
};

export function BatchSection({ title, batches, emptyMessage, onRetry, onRemove }: Props) {
  const [retrying, setRetrying] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const { pushToast, dismissToast } = useToast();

  return (
    <section className="card">
      <div className="section-header">
        <h2>{title}</h2>
        <span className="pill">{batches.length}</span>
      </div>
      {batches.length === 0 ? (
        <p className="muted-text">{emptyMessage}</p>
      ) : (
        <ul className="batch-list">
          {batches.map((batch) => {
            const size = formatSize(batch.files.reduce((total, file) => total + file.size, 0));
            const isRetryable = onRetry && (batch.status === "failed" || batch.status === "pending");
            const canRemove = onRemove && (batch.status === "failed" || batch.status === "pending");
            const progress = clampProgress(
              batch.status === "completed" ? 100 : batch.progress ?? 0
            );
            const showProgress =
              batch.status === "processing" || batch.status === "uploading" || (progress > 0 && progress < 100);

            return (
              <li key={batch.id}>
                <div className="batch-header">
                  <strong>{batch.id}</strong>
                  <span className={`status status-${batch.status}`}>{formatStatus(batch.status)}</span>
                </div>
                <p className="muted-text">Ajouté le {new Date(batch.createdAt).toLocaleString()}</p>
                <p className="muted-text subtle">{batch.files.length} fichier(s) • {size}</p>

                {showProgress && (
                  <div className="progress-card">
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${progress}%` }} />
                    </div>
                    <span className="progress-label">{progress}%</span>
                  </div>
                )}

                <ul className="file-preview-list">
                  {batch.files.slice(0, 4).map((file) => (
                    <li key={file.id}>{file.name}</li>
                  ))}
                  {batch.files.length > 4 && <li>+ {batch.files.length - 4} fichier(s)</li>}
                </ul>

                {batch.report && (
                  <div className="report-card">
                    <div className="report-icon">
                      <FileText size={18} />
                    </div>
                    <div className="report-content">
                      <p className="report-title">Rapport disponible</p>
                      {batch.report.hash && (
                        <p className="report-hash">
                          Hash SHA-256&nbsp;
                          <code>{truncateHash(batch.report.hash)}</code>
                        </p>
                      )}
                      <div className="report-actions">
                        <span className="report-status">
                          <CheckCircle2 size={14} />
                          Intégrité vérifiée
                        </span>
                        {batch.report.downloadUrl && (
                          <button
                            type="button"
                            className="link-button"
                            disabled={downloading === batch.id}
                            onClick={() =>
                              (async () => {
                                if (!batch.report?.downloadUrl) return;
                                const toastId = pushToast("Téléchargement du rapport en cours…", "info", { duration: 0 });
                                setDownloading(batch.id);
                                try {
                                  await downloadReport(batch.id, batch.report.downloadUrl);
                                  dismissToast(toastId);
                                  pushToast("Rapport téléchargé avec succès.", "success");
                                } catch (error) {
                                  console.error("Download failed", error);
                                  dismissToast(toastId);
                                  pushToast("Impossible de télécharger le rapport pour le moment.", "error");
                                } finally {
                                  setDownloading(null);
                                }
                              })()
                            }
                          >
                            {downloading === batch.id ? "Téléchargement…" : "Télécharger le PDF"}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {batch.lastError && <p className="error">{batch.lastError}</p>}

                {batch.timeline.length > 0 && (
                  <div className="batch-timeline">
                    <p className="timeline-title">Chronologie d’analyse</p>
                    <ol>
                      {batch.timeline.map((entry, index) => (
                        <TimelineItem
                          key={entry.id}
                          entry={entry}
                          isLatest={index === batch.timeline.length - 1}
                        />
                      ))}
                    </ol>
                  </div>
                )}

                {(isRetryable || canRemove) && (
                  <div className="batch-actions">
                    {isRetryable && (
                      <button
                        type="button"
                        className="retry-button"
                        disabled={retrying === batch.id}
                        onClick={() => {
                          if (!onRetry) return;
                          setRetrying(batch.id);
                          onRetry(batch.id)
                            .catch((error) => console.error("Retry failed", error))
                            .finally(() => setRetrying(null));
                        }}
                      >
                        {retrying === batch.id ? "Nouvelle tentative…" : "Réessayer"}
                      </button>
                    )}
                    {canRemove && (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={removing === batch.id}
                        onClick={() => {
                          if (!onRemove) return;
                          setRemoving(batch.id);
                          onRemove(batch.id)
                            .catch((error) => console.error("Remove failed", error))
                            .finally(() => setRemoving(null));
                        }}
                      >
                        {removing === batch.id ? "Suppression…" : "Retirer"}
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function formatStatus(status: BatchSummary["status"]): string {
  switch (status) {
    case "pending":
      return "En attente";
    case "uploading":
      return "Envoi en cours";
    case "processing":
      return "Analyse en cours";
    case "completed":
      return "Terminé";
    case "failed":
      return "Échec";
    default:
      return status;
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} o`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} Ko`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

function truncateHash(hash: string): string {
  if (hash.length <= 16) {
    return hash;
  }
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`;
}

type TimelineProps = {
  entry: BatchTimelineEntry;
  isLatest: boolean;
};

function TimelineItem({ entry, isLatest }: TimelineProps) {
  const icon = iconForKind(entry.kind);
  const detail = describeDetails(entry);

  return (
    <li className={`timeline-item ${isLatest ? "timeline-item-active" : ""}`}>
      <span className={`timeline-icon icon-${entry.kind}`}>{icon}</span>
      <div className="timeline-content">
        <p className="timeline-label">{entry.label}</p>
        <p className="timeline-meta">{formatTimestamp(entry.timestamp)}</p>
        {detail && <p className="timeline-detail">{detail}</p>}
      </div>
    </li>
  );
}

function iconForKind(kind: BatchTimelineEntry["kind"]) {
  switch (kind) {
    case "success":
      return <CheckCircle2 size={16} />;
    case "warning":
      return <Clock3 size={16} />;
    case "error":
      return <AlertTriangle size={16} />;
    default:
      return <Loader2 size={16} />;
  }
}

function describeDetails(entry: BatchTimelineEntry): string | null {
  const details = entry.details ?? {};
  if ("file" in details && "position" in details && "total" in details) {
    const position = Number(details.position);
    const total = Number(details.total);
    const file = String(details.file ?? "");
    return `Fichier ${Number.isFinite(position) ? position : "?"}/${Number.isFinite(total) ? total : "?"} — ${file}`;
  }
  if ("fileCount" in details) {
    const count = Number(details.fileCount);
    return `${Number.isFinite(count) ? count : "?"} fichier(s)`;
  }
  if ("hasMetadata" in details) {
    return details.hasMetadata ? "Métadonnées détectées" : "Aucune métadonnée trouvée";
  }
  if ("observationCount" in details) {
    const count = Number(details.observationCount);
    return `${Number.isFinite(count) ? count : "?"} observation(s) détectée(s)`;
  }
  if ("score" in details && typeof details.score === "number") {
    return `Score global : ${(details.score as number).toFixed(2)}`;
  }
  if ("hasRisk" in details) {
    return details.hasRisk ? "Score de risque disponible" : "Aucun risque identifié";
  }
  if ("hash" in details) {
    return `Hash : ${truncateHash(String(details.hash))}`;
  }
  if ("message" in details) {
    return String(details.message);
  }
  if ("label" in details && typeof details.label === "string") {
    return details.label;
  }
  return null;
}

function formatTimestamp(value: string): string {
  try {
    const date = new Date(value);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return value;
  }
}

function clampProgress(value: number): number {
  const rounded = Math.round(value);
  if (Number.isNaN(rounded)) {
    return 0;
  }
  return Math.min(100, Math.max(0, rounded));
}
