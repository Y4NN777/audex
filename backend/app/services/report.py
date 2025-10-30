from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.pipelines.models import OCRResult, Observation, PipelineResult, RiskBreakdown, RiskScore


@dataclass(slots=True)
class ReportContext:
    batch_id: str
    observations: Iterable[Observation]
    risk: RiskScore | None
    ocr_texts: Sequence[OCRResult]
    gemini_status: str | None
    gemini_provider: str | None
    gemini_duration_ms: int | None
    gemini_prompt_hash: str | None
    summary_text: str | None
    summary_findings: list[str] | None
    summary_recommendations: list[str] | None
    summary_status: str | None
    summary_source: str | None
    summary_prompt_hash: str | None
    summary_response_hash: str | None
    summary_warnings: list[str] | None
    timeline: Sequence[dict[str, object]]
    storage_root: Path | None


@dataclass(slots=True)
class ReportArtifact:
    path: Path
    checksum_sha256: str


class ReportBuilder:
    """Generate a minimal PDF report summarizing pipeline results."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.title_style = ParagraphStyle(
            name="Title",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=12,
        )
        self.body_style = ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=6,
        )

    def build_from_pipeline(
        self,
        result: PipelineResult,
        *,
        timeline: Sequence[dict[str, object]] | None = None,
        storage_root: Path | None = None,
    ) -> ReportArtifact:
        context = ReportContext(
            batch_id=result.batch_id,
            observations=result.observations,
            risk=result.risk,
            ocr_texts=result.ocr_texts,
            gemini_status=result.gemini_status,
            gemini_provider=result.gemini_provider,
            gemini_duration_ms=result.gemini_duration_ms,
            gemini_prompt_hash=result.gemini_prompt_hash,
            summary_text=result.summary_text,
            summary_findings=result.summary_findings or [],
            summary_recommendations=result.summary_recommendations or [],
            summary_status=result.summary_status,
            summary_source=result.summary_source,
            summary_prompt_hash=result.summary_prompt_hash,
            summary_response_hash=result.summary_response_hash,
            summary_warnings=result.summary_warnings or [],
            timeline=timeline or [],
            storage_root=storage_root,
        )
        filename = f"report-{context.batch_id}.pdf"
        destination = self.output_dir / filename
        self._render_pdf(destination, context)

        checksum = self._compute_checksum(destination)
        return ReportArtifact(path=destination, checksum_sha256=checksum)

    def _render_pdf(self, destination: Path, context: ReportContext) -> None:
        buffer: list = []
        doc = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm)

        buffer.append(Paragraph("Rapport d'audit AUDEX", self.title_style))
        buffer.append(
            Paragraph(
                f"Batch ID : <b>{context.batch_id}</b><br/>"
                f"Analyse avancée : <b>{context.gemini_status or 'non exécutée'}</b>"
                f" (source : {context.gemini_provider or '-'})",
                self.body_style,
            )
        )

        if context.risk:
            buffer.append(Spacer(1, 12))
            buffer.append(Paragraph("Synthèse du score de risque", self.title_style))
            buffer.append(
                Paragraph(
                    f"Score total : <b>{context.risk.total_score}</b> "
                    f"(normalisé {context.risk.normalized_score})",
                    self.body_style,
                )
            )
            buffer.append(self._build_risk_table(context.risk.breakdown))

        buffer.append(Spacer(1, 12))
        buffer.append(Paragraph("Observations clés", self.title_style))
        if context.observations:
            buffer.append(self._build_observation_table(list(context.observations)))
        else:
            buffer.append(Paragraph("Aucune observation enregistrée.", self.body_style))

        buffer.append(Spacer(1, 12))
        buffer.append(Paragraph("Synthèse IA", self.title_style))
        buffer.extend(self._build_summary_section(context))

        buffer.append(Spacer(1, 12))
        buffer.append(Paragraph("Extraits OCR pertinents", self.title_style))
        buffer.extend(self._build_ocr_section(context.ocr_texts))

        buffer.append(Spacer(1, 12))
        buffer.append(Paragraph("Informations techniques", self.title_style))
        buffer.append(self._build_metadata_table(context))

        if context.risk and context.risk.breakdown:
            buffer.append(Spacer(1, 12))
            buffer.append(Paragraph("Visualisation des scores", self.title_style))
            chart = self._create_risk_chart(context)
            if chart is not None:
                buffer.append(chart)

        if context.timeline:
            buffer.append(Spacer(1, 12))
            buffer.append(Paragraph("Timeline de traitement", self.title_style))
            buffer.append(self._build_timeline_table(context.timeline))

        buffer.append(Spacer(1, 12))
        buffer.append(Paragraph("Visualisations (placeholder)", self.title_style))
        buffer.append(
            Paragraph(
                "Les graphiques radar/cartes de chaleur seront intégrés lors de la prochaine itération (REPORT-008).",
                self.body_style,
            )
        )

        doc.build(buffer)

    def _build_risk_table(self, breakdown: Iterable[RiskBreakdown]) -> Table:
        data = [["Catégorie", "Sévérité", "Occurrences", "Score"]]
        for item in breakdown:
            data.append([item.label.title(), item.severity.title(), str(item.count), f"{item.score:.2f}"])

        table = Table(data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#e5e7eb"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _build_observation_table(self, observations: list[Observation]) -> Table:
        data = [["Fichier", "Label", "Sévérité", "Confiance", "Source", "Zone"]]
        for obs in observations:
            extra = obs.extra if isinstance(obs.extra, dict) else {}
            data.append(
                [
                    obs.source_file,
                    obs.label.title(),
                    obs.severity.title(),
                    f"{obs.confidence:.2f}",
                    str(extra.get("source", "local")),
                    str(extra.get("zone", "-")),
                ]
            )
        table = Table(data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _build_summary_section(self, context: ReportContext) -> list:
        elements: list = []
        status = context.summary_status or "non générée"
        source = context.summary_source or "-"
        summary_text = context.summary_text or "Synthèse indisponible."

        elements.append(Paragraph(f"Statut : <b>{status}</b> (source : {source})", self.body_style))
        elements.append(Paragraph(summary_text, self.body_style))

        if context.summary_findings:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("Points clés :", self.body_style))
            for finding in context.summary_findings:
                elements.append(Paragraph(f"• {finding}", self.body_style))

        if context.summary_recommendations:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("Recommandations :", self.body_style))
            for rec in context.summary_recommendations:
                elements.append(Paragraph(f"• {rec}", self.body_style))

        if context.summary_warnings:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("Avertissements :", self.body_style))
            for warning in context.summary_warnings:
                elements.append(Paragraph(f"• {warning}", self.body_style))

        return elements

    def _build_ocr_section(self, ocr_entries: Sequence[OCRResult]) -> list:
        if not ocr_entries:
            return [Paragraph("Aucun extrait OCR disponible.", self.body_style)]

        items: list = []
        for entry in ocr_entries[:5]:
            text = entry.text.strip().replace("\n", " ")
            snippet = text if len(text) <= 160 else f"{text[:157]}..."
            items.append(Paragraph(f"<b>{entry.source_file}</b> — {snippet}", self.body_style))
        return items

    def _build_metadata_table(self, context: ReportContext) -> Table:
        data = [
            ["Statut Gemini", context.gemini_status or "non exécuté"],
            ["Source Gemini", context.gemini_provider or "-"],
            ["Durée Gemini (ms)", str(context.gemini_duration_ms or "-")],
            ["Hash prompt Gemini", context.gemini_prompt_hash or "-"],
            ["Statut synthèse", context.summary_status or "non générée"],
            ["Source synthèse", context.summary_source or "-"],
            ["Hash prompt synthèse", context.summary_prompt_hash or "-"],
            ["Hash réponse synthèse", context.summary_response_hash or "-"],
        ]
        table = Table(data, hAlign="LEFT", colWidths=[6 * cm, 10 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f3f4f6"), colors.white]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _create_risk_chart(self, context: ReportContext) -> Image | None:
        try:
            import io
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            labels = [item.label.title() for item in context.risk.breakdown]
            scores = [item.score for item in context.risk.breakdown]

            fig, ax = plt.subplots(figsize=(4, 3))
            bars = ax.bar(labels, scores, color="#2563eb")
            ax.set_title("Scores par catégorie")
            ax.set_ylabel("Score")
            ax.set_ylim(bottom=0)
            ax.bar_label(bars, fmt="%.1f")
            fig.tight_layout()

            buffer = io.BytesIO()
            fig.savefig(buffer, format="PNG")
            plt.close(fig)
            buffer.seek(0)

            img = Image(buffer, width=12 * cm, height=9 * cm)
            return img
        except Exception:  # noqa: BLE001
            return None

    def _build_timeline_table(self, timeline: Sequence[dict[str, object]]) -> Table:
        data = [["Horodatage", "Étape", "Détails", "Progression"]]
        for stage in timeline:
            timestamp = stage.get("timestamp") or stage.get("time") or "-"
            label = stage.get("label") or stage.get("code") or "-"
            details = stage.get("details") or {}
            if isinstance(details, dict) and details:
                detail_str = ", ".join(f"{k}: {v}" for k, v in details.items())
            else:
                detail_str = "-"
            progress = stage.get("progress")
            progress_str = f"{progress}%" if progress is not None else "-"
            data.append([str(timestamp), str(label), detail_str, progress_str])

        table = Table(data, hAlign="LEFT", colWidths=[5 * cm, 5 * cm, 6 * cm, 2 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f3f4f6"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _compute_checksum(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as pdf_file:
            while chunk := pdf_file.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()
