import { useState } from "react";
import { CheckCircle2, FileText } from "lucide-react";

import type { BatchSummary, BatchTimelineEntry } from "../types/batch";
import { downloadReport } from "../services/reports";
import { useToast } from "./ToastProvider";

const STEP_DEFINITIONS = [
  { id: "ingestion", label: "Fichiers reçus", threshold: 5, codes: ["ingestion:"] },
  { id: "metadata", label: "Métadonnées extraites", threshold: 15, codes: ["metadata:"] },
  { id: "vision", label: "Analyse visuelle", threshold: 45, codes: ["vision:"] },
  { id: "ocr", label: "OCR & texte", threshold: 65, codes: ["ocr:"] },
  { id: "scoring", label: "Scoring calculé", threshold: 85, codes: ["scoring:"] },
  { id: "report", label: "Rapport disponible", threshold: 100, codes: ["report:"] }
] as const;

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
            const timelineProgress = computeProgressFromTimeline(batch.timeline ?? []);
            const rawProgress =
              batch.status === "completed" ? 100 : Math.max(batch.progress ?? 0, timelineProgress);
            const progress = clampProgress(rawProgress);
            const showProgress = progress > 0;
            const steps = buildStepStates(batch, progress);

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

                {steps.length > 0 && (
                  <div className="stepper">
                    {steps.map((step, index) => (
                      <div key={step.id} className={`step ${step.state}`}>
                        <div className="step-marker">{index + 1}</div>
                        <div className="step-info">
                          <p className="step-title">{step.label}</p>
                          <p className="step-caption">{step.detail ?? "En attente"}</p>
                        </div>
                      </div>
                    ))}
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

function clampProgress(value: number): number {
  const rounded = Math.round(value);
  if (Number.isNaN(rounded)) {
    return 0;
  }
  return Math.min(100, Math.max(0, rounded));
}

function computeProgressFromTimeline(timeline: BatchTimelineEntry[]): number {
  if (!timeline.length) {
    return 0;
  }
  return timeline.reduce((max, entry) => {
    if (typeof entry.progress === "number" && Number.isFinite(entry.progress)) {
      return Math.max(max, entry.progress);
    }
    return max;
  }, 0);
}

type StepState = "done" | "current" | "pending";

type StepView = {
  id: string;
  label: string;
  state: StepState;
  detail?: string;
};

function buildStepStates(batch: BatchSummary, progress: number): StepView[] {
  const timeline = batch.timeline ?? [];
  const steps: StepView[] = [];

  for (let index = 0; index < STEP_DEFINITIONS.length; index += 1) {
    const def = STEP_DEFINITIONS[index];
    const done = progress >= def.threshold;
    const previousDone = index === 0 ? true : steps[index - 1].state === "done";
    const state: StepState = done ? "done" : previousDone ? "current" : "pending";
    const latestEntry = findLatestEntry(timeline, def.codes);
    const detail = latestEntry ? `${latestEntry.label} — ${formatTimestamp(latestEntry.timestamp)}` : undefined;
    steps.push({ id: def.id, label: def.label, state, detail });
  }

  return steps;
}

function findLatestEntry(
  timeline: BatchTimelineEntry[],
  codes: readonly string[]
): BatchTimelineEntry | undefined {
  for (let index = timeline.length - 1; index >= 0; index -= 1) {
    const entry = timeline[index];
    if (codes.some((code) => entry.stage.startsWith(code))) {
      return entry;
    }
  }
  return undefined;
}

function formatTimestamp(value: string): string {
  try {
    const date = new Date(value);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return value;
  }
}
