from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from app.pipelines.models import Observation, PipelineResult, RiskBreakdown, RiskScore


@dataclass(slots=True)
class ReportContext:
    batch_id: str
    observations: Iterable[Observation]
    risk: RiskScore | None
    summary_text: str | None
    summary_findings: list[str] | None
    summary_recommendations: list[str] | None
    summary_status: str | None
    summary_source: str | None


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

    def build_from_pipeline(self, result: PipelineResult) -> ReportArtifact:
        context = ReportContext(
            batch_id=result.batch_id,
            observations=result.observations,
            risk=result.risk,
            summary_text=result.summary_text,
            summary_findings=result.summary_findings or [],
            summary_recommendations=result.summary_recommendations or [],
            summary_status=result.summary_status,
            summary_source=result.summary_source,
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
        buffer.append(Paragraph(f"Batch ID : <b>{context.batch_id}</b>", self.body_style))

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
        data = [["Fichier", "Label", "Sévérité", "Confiance"]]
        for obs in observations:
            data.append(
                [
                    obs.source_file,
                    obs.label.title(),
                    obs.severity.title(),
                    f"{obs.confidence:.2f}",
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
                elements.append(Paragraph(f"- {finding}", self.body_style))

        if context.summary_recommendations:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("Recommandations :", self.body_style))
            for rec in context.summary_recommendations:
                elements.append(Paragraph(f"- {rec}", self.body_style))

        return elements

    def _compute_checksum(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as pdf_file:
            while chunk := pdf_file.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()
