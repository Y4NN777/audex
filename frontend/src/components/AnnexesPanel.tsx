import type { BatchSummary, OCRText } from "../types/batch";

type Props = {
  batch: BatchSummary | null;
};

export function AnnexesPanel({ batch }: Props) {
  if (!batch) {
    return (
      <section className="card">
        <h2>Annexes OCR & métadonnées</h2>
        <p className="muted-text">Les extraits OCR et métadonnées apparaîtront ici après traitement.</p>
      </section>
    );
  }

  const ocrTexts = batch.ocrTexts ?? [];

  return (
    <section className="card">
      <div className="section-header">
        <h2>Annexes OCR & métadonnées</h2>
        <span className="pill">{ocrTexts.length}</span>
      </div>

      {ocrTexts.length === 0 ? (
        <p className="muted-text">Aucun extrait OCR disponible pour ce lot.</p>
      ) : (
        <ul className="ocr-list">
          {ocrTexts.map((item) => (
            <li key={`${item.filename}-${item.engine}`}>
              <div className="ocr-header">
                <strong>{item.filename}</strong>
                <span className="badge engine">{item.engine}</span>
              </div>
              {item.confidence !== undefined && (
                <p className="ocr-meta">Confiance&nbsp;: {(item.confidence * 100).toFixed(0)}%</p>
              )}
              {item.warnings?.length ? (
                <p className="ocr-warning">{item.warnings.join(" · ")}</p>
              ) : null}
              <pre className="ocr-content">{truncate(item.content)}</pre>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function truncate(text: string, max = 520): string {
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max)}…`;
}
