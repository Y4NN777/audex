import { AlertCircle, ArrowDownToLine, Copy, Hash } from "lucide-react";

import { downloadReport } from "../services/reports";
import type { BatchSummary, ReportInsights } from "../types/batch";
import { formatBytes } from "../utils/format";
import { useToast } from "./ToastProvider";

type Props = {
  batch: BatchSummary | null;
  onRefresh?: () => void;
};

export function ReportHero({ batch, onRefresh }: Props) {
  const { pushToast, dismissToast } = useToast();

  if (!batch) {
    return (
      <section className="report-hero empty">
        <div>
          <h1>AUDEX Shell — cockpit offline-first</h1>
          <p className="hero-subtitle">
            Déposez vos lots, suivez l’analyse IA et retrouvez vos rapports PDF enrichis dès que la synchronisation est
            terminée. Sélectionnez un lot traité pour consulter ses observations.
          </p>
        </div>
      </section>
    );
  }

  const totalSize = formatBytes(batch.files.reduce((total, file) => total + (file.size || 0), 0));
  const { insights } = batch;
  const normalizedScore = insights?.risk?.normalizedScore;
  const scorePercent = typeof normalizedScore === "number" ? Math.round(normalizedScore * 100) : null;
  const summaryText =
    insights?.summary?.text ?? insights?.geminiSummary ?? "Synthèse en cours de préparation…";

  const handleDownload = async () => {
    if (!batch.report?.downloadUrl) {
      return;
    }
    const toastId = pushToast("Téléchargement du rapport…", "info", { duration: 0 });
    try {
      await downloadReport(batch.id, batch.report.downloadUrl);
      dismissToast(toastId);
      pushToast("Rapport téléchargé", "success");
    } catch (error) {
      console.error("Download failed", error);
      dismissToast(toastId);
      pushToast("Impossible de télécharger le rapport pour le moment.", "error");
    }
  };

  const handleCopyHash = async (hash: string) => {
    try {
      await navigator.clipboard.writeText(hash);
      pushToast("Code d’intégrité copié", "success");
    } catch (error) {
      console.error("Copy hash failed", error);
      pushToast("Impossible de copier ce code pour le moment.", "error");
    }
  };

  return (
    <section className="report-hero">
      <div className="report-hero__header">
        <div>
          <p className="hero-kicker">Lot synchronisé</p>
          <h1>Rapport d’audit · {batch.id}</h1>
          <p className="hero-subtitle">{summaryText}</p>
        </div>
        <div className="report-actions">
          {onRefresh && (
            <button type="button" className="ghost-button" onClick={onRefresh}>
              Actualiser
            </button>
          )}
          {batch.report?.downloadUrl && (
            <button type="button" className="primary-button icon" onClick={handleDownload}>
              <ArrowDownToLine size={18} />
              Télécharger le PDF
            </button>
          )}
        </div>
      </div>

      <div className="report-hero__grid">
        <article className="hero-card score">
          <div>
            <p className="hero-card-kicker">Score global</p>
            <p className="hero-card-value">{scorePercent !== null ? `${scorePercent}%` : "N/A"}</p>
          </div>
          <p className="hero-card-caption">
            Calculé à partir des constats automatisés et du diagnostic IA. Dernière mise à jour&nbsp;
            {insights?.risk?.createdAt ? new Date(insights.risk.createdAt).toLocaleString() : "—"}
          </p>
        </article>

        <article className="hero-card">
          <p className="hero-card-kicker">Synthèse IA</p>
          <p className="hero-card-title">{formatSummaryStatus(insights)}</p>
          <p className="hero-card-caption">
            {insights?.summary?.source ? formatSummarySource(insights.summary.source) : "Analyse automatique AUDEX"}
          </p>
          {insights?.summary?.warnings?.length ? (
            <ul className="hero-warning-list">
              {insights.summary.warnings.map((warning) => (
                <li key={warning}>
                  <AlertCircle size={14} />
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}
        </article>

        <article className="hero-card">
          <p className="hero-card-kicker">Statut blockchain</p>
          {batch.report?.hash ? (
            <>
              <p className="hero-card-title">Code d’intégrité disponible</p>
              <div className="report-hash-row">
                <p className="hero-card-caption hash">
                  <Hash size={14} />
                  {truncateHash(batch.report.hash)}
                </p>
                <button type="button" className="ghost-button" onClick={() => handleCopyHash(batch.report!.hash)}>
                  <Copy size={14} /> Copier
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="hero-card-title">En attente d’ancrage</p>
              <p className="hero-card-caption">
                Le hash du rapport sera publié une fois l’ancrage blockchain finalisé.
              </p>
            </>
          )}
        </article>

        <article className="hero-card meta">
          <p className="hero-card-kicker">Résumé lot</p>
          <ul>
            <li>
              <span>Créé le</span>
              <span>{new Date(batch.createdAt).toLocaleString()}</span>
            </li>
            <li>
              <span>Fichiers</span>
              <span>{batch.files.length}</span>
            </li>
            <li>
              <span>Volume total</span>
              <span>{totalSize}</span>
            </li>
            <li>
              <span>Statut pipeline</span>
              <span className={`status-text status-${batch.status}`}>{formatStatus(batch.status)}</span>
            </li>
          </ul>
        </article>
      </div>
    </section>
  );
}

function truncateHash(hash: string): string {
  if (hash.length <= 18) {
    return hash;
  }
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`;
}

function formatSummaryStatus(insights?: ReportInsights): string {
  const status = (insights?.summary?.status ?? insights?.geminiStatus ?? "").toLowerCase();
  switch (status) {
    case "ok":
      return "Analyse terminée";
    case "no_insights":
      return "Analyse terminée (aucun écart majeur)";
    case "disabled":
      return "Analyse désactivée";
    case "failed":
      return "Analyse interrompue";
    case "skipped":
      return "Analyse non réalisée";
    default:
      return "Analyse en cours";
  }
}

function formatSummarySource(source: string): string {
  const normalized = source.toLowerCase();
  if (normalized.includes("gemini")) {
    return "Analyse IA automatisée";
  }
  if (normalized.includes("manual")) {
    return "Analyse saisie manuellement";
  }
  return `Source ${source}`;
}

function formatStatus(status: BatchSummary["status"]): string {
  switch (status) {
    case "pending":
      return "En attente";
    case "uploading":
      return "Téléversement";
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
