from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.core.config import settings
from app.pipelines.models import OCRResult, Observation, RiskScore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SummaryRequest:
    batch_id: str
    risk: RiskScore | None
    observations_local: Sequence[Observation] | None
    observations_gemini: Sequence[Observation] | None
    ocr_texts: Sequence[OCRResult] | None


@dataclass(slots=True)
class SummaryResult:
    status: str
    text: str | None
    findings: list[str]
    recommendations: list[str]
    warnings: list[str]
    source: str
    prompt_hash: str | None = None
    response_hash: str | None = None
    duration_ms: int | None = None


class ReportSummaryService:
    """Generate a textual summary and recommendations based on pipeline outputs."""

    PROVIDER = "google-gemini"
    PROMPT_VERSION = "summary-1.0"

    def __init__(self) -> None:
        self.enabled = settings.GEMINI_SUMMARY_ENABLED
        self.required = settings.GEMINI_SUMMARY_REQUIRED
        self.api_key = settings.GEMINI_SUMMARY_API_KEY or settings.GEMINI_API_KEY
        self.model = settings.GEMINI_SUMMARY_MODEL
        self.timeout = settings.GEMINI_SUMMARY_TIMEOUT_SECONDS
        self.max_retries = settings.GEMINI_SUMMARY_MAX_RETRIES
        self.fallback_enabled = settings.SUMMARY_FALLBACK_ENABLED
        self.fallback_model = settings.SUMMARY_FALLBACK_MODEL

    def generate(self, request: SummaryRequest) -> SummaryResult:
        if not self.enabled:
            return SummaryResult(
                status="disabled",
                text=None,
                findings=[],
                recommendations=[],
                warnings=[],
                source="none",
            )

        if not self.api_key:
            warning = "summary-missing-api-key"
            status = "failed" if self.required else "skipped"
            return SummaryResult(
                status=status,
                text=None,
                findings=[],
                recommendations=[],
                warnings=[warning],
                source="gemini",
            )

        prompt = self._build_prompt(request)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        try:
            response_text, duration_ms = self._call_gemini(prompt)
            summary, findings, recommendations, warnings = self._parse_response(response_text)
            response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
            return SummaryResult(
                status="ok" if summary or findings or recommendations else "no_content",
                text=summary,
                findings=findings,
                recommendations=recommendations,
                warnings=warnings,
                source=self.PROVIDER,
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini summary failed for %s: %s", request.batch_id, exc)
            if self.required and not self.fallback_enabled:
                raise
            if self.fallback_enabled:
                return self._fallback_summary(request, prompt_hash, str(exc))
            return SummaryResult(
                status="failed",
                text=None,
                findings=[],
                recommendations=[],
                warnings=[f"summary-error:{exc}"],
                source=self.PROVIDER,
                prompt_hash=prompt_hash,
                response_hash=None,
                duration_ms=None,
            )

    def _build_prompt(self, request: SummaryRequest) -> str:

        risk_section = "Aucun score de risque calculé."
        if request.risk:
            lines = [
                f"- Score total : {request.risk.total_score}",
                f"- Score normalisé (0-1) : {request.risk.normalized_score}",
                "- Détails par catégorie :",
            ]
            for breakdown in request.risk.breakdown:
                lines.append(
                    f"  * {breakdown.label} :: sévérité {breakdown.severity}, "
                    f"{breakdown.count} occurrence(s), score {breakdown.score}"
                )
            risk_section = "\n".join(lines)

        def _format_observations(observations: Iterable[Observation] | None, label: str) -> str:
            if not observations:
                return f"Aucune observation {label}."
            lines = [f"Observations {label} :"]
            for obs in observations:
                lines.append(
                    f"- Fichier {obs.source_file} :: {obs.label} (sévérité {obs.severity}, confiance {obs.confidence:.2f})"
                )
            return "\n".join(lines)

        local_obs = _format_observations(request.observations_local, "locales (YOLO)")
        gemini_obs = _format_observations(request.observations_gemini, "Gemini")

        ocr_snippets = "Aucun texte OCR pertinent."
        if request.ocr_texts:
            snippets: list[str] = []
            for entry in request.ocr_texts[:5]:
                snippet = entry.text.strip().replace("\n", " ")
                if snippet:
                    snippets.append(f"- {entry.source_file}: {snippet[:160]}")
            if snippets:
                ocr_snippets = "Extraits OCR pertinents :\n" + "\n".join(snippets)

        prompt = f"""
Tu es un expert QHSE chargé de résumer un audit de site.

### Informations de contexte
Batch ID : {request.batch_id}

### Score de risque
{risk_section}

### Observations locales
{local_obs}

### Observations Gemini
{gemini_obs}

### Extraits OCR
{ocr_snippets}

### Attendu
Produis un JSON strict respectant ce schéma :
{{
  "summary": "paragraphe synthétique (max 120 mots)",
  "key_findings": ["point 1", "point 2"],
  "recommendations": ["action prioritaire 1", "action prioritaire 2"],
  "warnings": ["optionnel, message de prudence"]  // facultatif
}}

Règles :
- Pas de texte hors JSON
- Ton professionnel et factuel
- Recommandations concrètes et actionnables
- Si aucune donnée, retourner des tableaux vides
"""
        return prompt.strip()

    def _call_gemini(self, prompt: str) -> tuple[str, int]:
        start = time.perf_counter()
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "response_mime_type": "application/json",
            },
        )

        attempts = self.max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                logger.debug("Gemini summary attempt %s/%s", attempt, attempts)
                response = model.generate_content(
                    [{"role": "user", "parts": [{"text": prompt}]}],
                    request_options={"timeout": self.timeout},
                )
                text = getattr(response, "text", None)
                if text:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return text, duration_ms
                candidates = getattr(response, "candidates", None)
                if candidates:
                    candidate_content = getattr(candidates[0], "content", None)
                    candidate_parts = getattr(candidate_content, "parts", []) if candidate_content else []
                    texts = [getattr(part, "text", "") for part in candidate_parts if getattr(part, "text", "")]
                    if texts:
                        duration_ms = int((time.perf_counter() - start) * 1000)
                        return "\n".join(texts), duration_ms
                raise RuntimeError("Empty response from Gemini summary.")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < attempts:
                    time.sleep(min(2 * attempt, 6))
                    continue
                raise
        raise RuntimeError("Gemini summary failed") from last_exc

    def _parse_response(self, payload: str) -> tuple[str | None, list[str], list[str], list[str]]:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            return None, [], [], [f"summary-invalid-json:{exc}"]

        summary = parsed.get("summary")
        findings = parsed.get("key_findings") or []
        recommendations = parsed.get("recommendations") or []
        warnings = parsed.get("warnings") or []

        def _ensure_list(value) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value]
            if value is None:
                return []
            return [str(value)]

        return (
            str(summary) if summary is not None else None,
            _ensure_list(findings),
            _ensure_list(recommendations),
            _ensure_list(warnings),
        )

    def _fallback_summary(self, request: SummaryRequest, prompt_hash: str, error: str) -> SummaryResult:
        logger.info("Using fallback summary model %s due to %s", self.fallback_model, error)
        text = (
            "Analyse avancée indisponible. Résumé généré localement : "
            "les observations locales doivent être traitées selon les priorités habituelles."
        )
        findings = ["Analyse avancée indisponible"]
        recommendations = ["Relancer la synthèse Gemini quand la connexion est rétablie."]
        warnings = [f"summary-fallback:{error}"]
        return SummaryResult(
            status="fallback",
            text=text,
            findings=findings,
            recommendations=recommendations,
            warnings=warnings,
            source=self.fallback_model,
            prompt_hash=prompt_hash,
            response_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            duration_ms=None,
        )
