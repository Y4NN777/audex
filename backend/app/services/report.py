from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.pipelines.models import OCRResult, Observation, PipelineResult, RiskBreakdown, RiskScore


@dataclass(slots=True)
class ReportContext:
    batch_id: str
    generated_at: datetime
    observations: Sequence[Observation]
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
    """Generate a PDF report summarizing pipeline results."""

    def __init__(self, output_dir: Path, logo_path: Path | None = None) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logo_path = logo_path

        self.title_style = ParagraphStyle(
            name="Title",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=12,
        )
        self.section_title_style = ParagraphStyle(
            name="SectionTitle",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceAfter=8,
        )
        self.body_style = ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=6,
        )
        self.body_small_style = ParagraphStyle(
            name="BodySmall",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=4,
        )
        self.cover_title_style = ParagraphStyle(
            name="CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            alignment=TA_CENTER,
            spaceAfter=24,
        )
        self.cover_meta_style = ParagraphStyle(
            name="CoverMeta",
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        self.badge_style = ParagraphStyle(
            name="Badge",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1d4ed8"),
            spaceAfter=6,
        )
        self.disclaimer_style = ParagraphStyle(
            name="Disclaimer",
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#4b5563"),
            spaceBefore=6,
            spaceAfter=4,
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
            generated_at=datetime.now(),
            observations=tuple(result.observations or []),
            risk=result.risk,
            ocr_texts=tuple(result.ocr_texts or []),
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
        story: list = []
        doc = SimpleDocTemplate(
            str(destination),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        story.extend(self._build_cover(context))
        story.append(PageBreak())

        story.extend(self._build_dashboard_section(context))
        story.append(PageBreak())

        story.extend(self._build_summary_block(context))
        story.append(PageBreak())

        story.extend(self._build_observations_section(context))
        story.append(PageBreak())

        story.extend(self._build_annexes_section(context))

        doc.build(story)

    def _build_cover(self, context: ReportContext) -> list:
        elements: list = []

        if self.logo_path and self.logo_path.exists():
            logo = Image(str(self.logo_path), width=4 * cm, height=4 * cm)
            logo.hAlign = "CENTER"
            elements.append(logo)
            elements.append(Spacer(1, 18))

        elements.append(Paragraph("AUDEX", self.badge_style))
        elements.append(Paragraph("Rapport d'audit", self.cover_title_style))

        generated_at = context.generated_at.strftime("%d/%m/%Y %H:%M")
        meta_rows: list[list[str]] = [
            ["Batch ID", context.batch_id],
            ["Date de génération", generated_at],
            ["Responsable", "Pipeline automatique AUDEX"],
        ]
        if context.risk:
            normalized = f"{context.risk.normalized_score * 100:.0f}%"
            meta_rows.insert(
                1,
                ["Score global", f"{context.risk.total_score:.1f} pts (normalisé {normalized})"],
            )
        meta_rows.append(
            [
                "Statut synthèse IA",
                f"{context.summary_status or 'non générée'} ({context.summary_source or context.gemini_provider or '-'})",
            ]
        )
        meta_rows.append(["Statut Gemini", context.gemini_status or "non exécutée"])

        meta_table = Table(meta_rows, colWidths=[7 * cm, 9 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e0e7ff")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7d2fe")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 18))

        summary_text = context.summary_text or "Synthèse indisponible pour ce lot."
        elements.append(Paragraph("Résumé exécutif", self.section_title_style))
        elements.append(Paragraph(summary_text, self.body_style))

        if context.summary_recommendations:
            head_rec = context.summary_recommendations[0]
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"Recommandation prioritaire : <b>{head_rec}</b>", self.badge_style))

        blockchain_rows = [
            ["Statut blockchain", "En attente d'ancrage (MVP)"],
            ["Hash SHA-256", "Généré après publication du rapport"],
            ["Identifiant / lien", "Non disponible"],
        ]
        blockchain_table = Table(blockchain_rows, colWidths=[7 * cm, 9 * cm])
        blockchain_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(Spacer(1, 18))
        elements.append(blockchain_table)

        return elements

    def _build_dashboard_section(self, context: ReportContext) -> list:
        elements: list = [Paragraph("Tableau de bord synthétique", self.title_style)]

        observations = list(context.observations)
        total_observations = len(observations)
        severe = sum(1 for obs in observations if (obs.severity or "").lower() == "high")
        timeline_points = len(context.timeline)

        metrics_rows = [
            ["Observations détectées", str(total_observations)],
            ["Observations critiques", str(severe)],
            ["Synthèse IA", context.summary_status or "non générée"],
            ["Statut Gemini", context.gemini_status or "non exécutée"],
            ["Timeline - étapes", str(timeline_points)],
        ]
        if context.risk:
            normalized = f"{context.risk.normalized_score * 100:.0f}%"
            metrics_rows.insert(0, ["Score global", f"{context.risk.total_score:.1f} pts"])
            metrics_rows.insert(1, ["Score normalisé", normalized])

        metrics_table = Table(metrics_rows, colWidths=[7 * cm, 9 * cm])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f4f6")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ]
            )
        )
        elements.append(Spacer(1, 12))
        elements.append(metrics_table)

        if context.risk and context.risk.breakdown:
            elements.append(Spacer(1, 18))
            elements.append(Paragraph("Scores par catégorie", self.section_title_style))
            chart = self._create_risk_chart(context)
            if chart is not None:
                chart.hAlign = "CENTER"
                elements.append(chart)
            else:
                elements.append(Paragraph("Graphique indisponible (matplotlib non disponible).", self.body_small_style))

            elements.append(Spacer(1, 12))
            elements.append(self._build_risk_table(context.risk.breakdown))
        else:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Aucun score de risque calculé pour ce lot.", self.body_style))

        if context.timeline:
            elements.append(Spacer(1, 18))
            elements.append(Paragraph("Timeline de traitement", self.section_title_style))
            elements.append(self._build_timeline_table(context.timeline))
        else:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Timeline de traitement indisponible.", self.body_small_style))

        return elements

    def _build_summary_block(self, context: ReportContext) -> list:
        elements: list = [Paragraph("Synthèse IA & recommandations", self.title_style)]
        elements.extend(self._build_summary_section(context))

        return elements

    def _build_observations_section(self, context: ReportContext) -> list:
        elements: list = [Paragraph("Observations détaillées", self.title_style)]
        observations = list(context.observations)

        if observations:
            elements.append(self._build_observation_table(observations))
            stats_table = self._build_observation_stats_table(observations)
            if stats_table is not None:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Répartition des sévérités", self.section_title_style))
                elements.append(stats_table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Prévisualisations visuelles", self.section_title_style))
            elements.append(
                Paragraph(
                    "Les vignettes seront intégrées dès que la pipeline vision exportera des images annotées.",
                    self.body_small_style,
                )
            )
        else:
            elements.append(Paragraph("Aucune observation n'a été enregistrée pour ce lot.", self.body_style))

        return elements

    def _build_annexes_section(self, context: ReportContext) -> list:
        elements: list = [Paragraph("Annexes techniques & traçabilité", self.title_style)]

        elements.append(Paragraph("Extraits OCR pertinents", self.section_title_style))
        elements.extend(self._build_ocr_section(context.ocr_texts))

        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Métadonnées Gemini & synthèse", self.section_title_style))
        elements.append(self._build_metadata_table(context))

        if context.timeline:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Timeline complète", self.section_title_style))
            elements.append(self._build_timeline_table(context.timeline))

        elements.append(Spacer(1, 18))
        elements.append(Paragraph("Clauses & disclaimers", self.section_title_style))
        elements.extend(self._build_disclaimer_section())

        return elements

    def _build_observation_stats_table(self, observations: Sequence[Observation]) -> Table | None:
        if not observations:
            return None

        severity_counts: dict[str, int] = {}
        for obs in observations:
            key = (obs.severity or "unknown").title()
            severity_counts[key] = severity_counts.get(key, 0) + 1

        rows = [["Sévérité", "Occurrences"]]
        for severity, count in sorted(severity_counts.items()):
            rows.append([severity, str(count)])

        table = Table(rows, hAlign="LEFT", colWidths=[7 * cm, 4 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
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

    def _build_disclaimer_section(self) -> list:
        disclaimers = [
            "Ce document est généré automatiquement par la plateforme AUDEX. Il doit être validé par un auditeur "
            "certifié avant diffusion externe.",
            "Les scores et recommandations sont fournis à titre indicatif et peuvent nécessiter une analyse terrain "
            "complémentaire.",
            "Les intégrations blockchain et visualisations avancées seront finalisées dans les prochaines itérations "
            "du MVP (REPORT-008).",
        ]
        return [Paragraph(item, self.disclaimer_style) for item in disclaimers]

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
