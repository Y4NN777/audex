import { AlertTriangle, CheckCircle2, ClipboardList, Info } from "lucide-react";

import type { BatchSummary, ReportInsights } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
};

export function SummaryPanel({ batch }: Props) {
  if (!batch) {
    return (
      <section className="card">
        <h2>Synthèse IA & recommandations</h2>
        <p className="muted-text">Sélectionnez un lot complété pour afficher la synthèse IA et les recommandations.</p>
      </section>
    );
  }

  const insights = batch.insights;
  const summary = insights?.summary;
  const findings = summary?.findings ?? [];
  const recommendations = summary?.recommendations ?? [];
  const warnings = summary?.warnings ?? [];
  const breakdown = insights?.risk?.breakdown ?? [];

  return (
    <section className="card">
      <div className="section-header">
        <h2>Synthèse IA & recommandations</h2>
        <span className="pill">{recommendations.length || findings.length || warnings.length ? "MAJ" : "En cours"}</span>
      </div>

      {renderSummaryHeader(insights)}

      <div className="summary-grid">
        {findings.length > 0 && (
          <div className="summary-column">
            <h3>
              <ClipboardList size={16} />
              Constats clés
            </h3>
            <ul>
              {findings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {recommendations.length > 0 && (
          <div className="summary-column">
            <h3>
              <CheckCircle2 size={16} />
              Recommandations
            </h3>
            <ul>
              {recommendations.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {warnings.length > 0 && (
          <div className="summary-column">
            <h3 className="warning">
              <AlertTriangle size={16} />
              Points de vigilance
            </h3>
            <ul>
              {warnings.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {breakdown.length > 0 && (
        <div className="risk-breakdown">
          <h3>Répartition des risques</h3>
          <ul>
            {breakdown.map((item) => (
              <li key={item.label}>
                <span className={`badge severity-${item.severity.toLowerCase()}`}>{item.severity}</span>
                <div>
                  <p className="breakdown-label">{item.label}</p>
                  <p className="breakdown-meta">
                    {item.count} observation(s) · Score {item.score.toFixed(1)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function renderSummaryHeader(insights: ReportInsights | undefined) {
  if (!insights) {
    return (
      <div className="summary-header">
        <Info size={18} />
        <p className="muted-text">Synthèse IA en cours de génération…</p>
      </div>
    );
  }
  const summary = insights.summary;
  const statusLabel = formatSummaryStatus(summary?.status ?? insights.geminiStatus);
  const sourceLabel = summary?.source ? formatSummarySource(summary.source) : undefined;
  const durationLabel = summary?.durationMs ? `${Math.round(summary.durationMs / 1000)} s` : undefined;
  return (
    <div className="summary-header">
      <Info size={18} />
      <div>
        <p className="summary-status">
          {statusLabel}
          {sourceLabel ? ` · ${sourceLabel}` : ""}
          {durationLabel ? ` · ${durationLabel}` : ""}
        </p>
        {summary?.text && <p className="summary-text">{summary.text}</p>}
        {!summary?.text && (
          <p className="muted-text">La synthèse détaillée est en cours de rédaction par l’assistant IA.</p>
        )}
      </div>
    </div>
  );
}

function formatSummaryStatus(status?: string): string {
  switch ((status ?? "").toLowerCase()) {
    case "ok":
      return "Analyse terminée";
    case "no_insights":
      return "Analyse terminée (aucun point critique)";
    case "disabled":
      return "Analyse désactivée";
    case "failed":
      return "Analyse interrompue";
    case "skipped":
      return "Analyse non effectuée";
    default:
      return "Synthèse en préparation";
  }
}

function formatSummarySource(source: string): string {
  if (!source) {
    return "";
  }
  switch (source.toLowerCase()) {
    case "google-gemini":
    case "gemini":
      return "Analyse IA automatique";
    case "manual":
      return "Analyse saisie manuellement";
    default:
      return `Source ${source}`;
  }
}
