import { useState } from "react";

import type { BatchSummary } from "../types/batch";
import { downloadReport } from "../services/reports";

type Props = {
  title: string;
  batches: BatchSummary[];
  emptyMessage: string;
  onRetry?: (batchId: string) => Promise<void>;
};

export function BatchSection({ title, batches, emptyMessage, onRetry }: Props) {
  const [retrying, setRetrying] = useState<string | null>(null);

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

            return (
              <li key={batch.id}>
                <div className="batch-header">
                  <strong>{batch.id}</strong>
                  <span className={`status status-${batch.status}`}>{formatStatus(batch.status)}</span>
                </div>
                <p className="muted-text">Ajouté le {new Date(batch.createdAt).toLocaleString()}</p>
                <p className="muted-text subtle">{batch.files.length} fichier(s) • {size}</p>

                <ul className="file-preview-list">
                  {batch.files.slice(0, 4).map((file) => (
                    <li key={file.id}>{file.name}</li>
                  ))}
                  {batch.files.length > 4 && <li>+ {batch.files.length - 4} fichier(s)</li>}
                </ul>

                {batch.report?.hash && <p className="muted-text subtle">Hash SHA-256 : {batch.report.hash}</p>}
                {batch.report?.downloadUrl && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() =>
                      downloadReport(batch.id, batch.report?.downloadUrl).catch((error) => {
                        console.error("Download failed", error);
                        alert("Impossible de télécharger le rapport pour le moment.");
                      })
                    }
                  >
                    Télécharger le rapport
                  </button>
                )}

                {batch.lastError && <p className="error">{batch.lastError}</p>}

                {isRetryable && (
                  <div className="batch-actions">
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
      return "Analyse";
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
