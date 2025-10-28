import type { BatchSummary } from "../types/batch";
import { downloadReport } from "../services/reports";

type Props = {
  title: string;
  batches: BatchSummary[];
  emptyMessage: string;
};

export function BatchSection({ title, batches, emptyMessage }: Props) {
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
          {batches.map((batch) => (
            <li key={batch.id}>
              <div className="batch-header">
                <strong>{batch.id}</strong>
                <span className={`status status-${batch.status}`}>{formatStatus(batch.status)}</span>
              </div>
              <p className="muted-text">{new Date(batch.createdAt).toLocaleString()}</p>
              <p className="muted-text">{batch.files.length} fichier(s)</p>
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
            </li>
          ))}
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
