from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.core.config import settings
from app.pipelines.models import OCRResult, Observation, RiskScore

logger = logging.getLogger(__name__)

SEVERITY_TRANSLATIONS: dict[str, str] = {
    "low": "faible",
    "medium": "modérée",
    "high": "élevée",
    "critical": "critique",
}

VOCABULARY_REPLACEMENTS: dict[str, str] = {
    "yolo": "analyse visuelle",
    "gemini": "analyse distante",
    "pipeline": "flux d'analyse",
    "batch": "lot",
}

SUMMARY_CHAR_LIMIT = 3000  # Augmenté pour permettre des synthèses plus détaillées


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
    PROMPT_VERSION = "summary-1.1"

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
            summary = self._compose_summary(summary, request.risk)
            findings = self._sanitize_list(findings)
            recommendations = self._sanitize_list(recommendations)
            warnings = self._sanitize_list(warnings, limit=3, sentence_case=False)
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
        risk_section = "Aucun score de risque enregistré."
        if request.risk:
            lines = [
                f"- Score global : {request.risk.total_score:.1f} / 100",
                f"- Score normalisé : {request.risk.normalized_score * 100:.0f}%",
            ]
            if request.risk.breakdown:
                lines.append("- Principales catégories :")
                for breakdown in request.risk.breakdown[:5]:
                    severity = self._translate_severity(breakdown.severity)
                    lines.append(
                        f"  * {breakdown.label} · gravité {severity} · {breakdown.count} cas · score {breakdown.score:.1f}"
                    )
            risk_section = "\n".join(lines)

        def _format_observations(
            observations: Iterable[Observation] | None,
            label: str,
        ) -> str:
            if not observations:
                return f"Aucune observation {label}."
            lines = [f"Observations {label} :"]
            for obs in list(observations)[:5]:
                severity = self._translate_severity(obs.severity)
                confidence = "-"
                if obs.confidence is not None:
                    try:
                        confidence = f"{obs.confidence * 100:.0f}%"
                    except TypeError:
                        confidence = str(obs.confidence)
                lines.append(
                    f"- {obs.source_file} • {obs.label} (gravité {severity}, confiance {confidence})"
                )
            return "\n".join(lines)

        local_obs = _format_observations(request.observations_local, "terrain")
        remote_obs = _format_observations(request.observations_gemini, "analyse distante")

        ocr_snippets = "Aucun extrait OCR pertinent."
        if request.ocr_texts:
            snippets: list[str] = []
            for entry in request.ocr_texts[:5]:
                snippet = entry.text.strip().replace("\n", " ")
                if snippet:
                    snippets.append(f"- {entry.source_file} • {snippet[:160]}")
            if snippets:
                ocr_snippets = "Extraits OCR :\n" + "\n".join(snippets)

        summary_schema = {
            "summary": {
                "context": "Contexte global et niveau de risque",
                "critical_areas": "Zones critiques et impacts business",
                "priorities": "Points de vigilance prioritaires",
                "major_risks": "Risques majeurs ou confirmation d'absence",
            },
            "key_findings": [
                {
                    "observation": "Description détaillée de l'observation",
                    "context": "Contexte spécifique (lieu, moment, conditions)",
                    "evidence": "Citations des preuves (extraits OCR, photos)",
                    "impact": "Impact sur la sécurité/conformité",
                    "severity": "Niveau de gravité",
                    "confidence": "Niveau de confiance",
                }
            ],
            "recommendations": [
                {
                    "action": "Description détaillée de l'action à entreprendre",
                    "owner": "Équipe responsable suggérée",
                    "timeline": "Délai de mise en œuvre recommandé",
                    "effort": "Estimation de l'effort requis",
                    "impact": "Impact attendu après mise en œuvre",
                }
            ],
            "warnings": [
                {
                    "type": "missing_data|contradiction|expertise_needed",
                    "description": "Description détaillée du warning",
                    "impact": "Impact potentiel sur l'analyse",
                }
            ],
        }
        schema_json = json.dumps(summary_schema, ensure_ascii=False, indent=2)

        prompt = f"""
Tu es un consultant QHSE. Fournis une synthèse claire et actionnable en français. Interdiction de citer les moteurs
(YOLO, Gemini, pipeline).

### Contexte audit
- Identifiant lot : {request.batch_id}

### Score de risque
{risk_section}

### Observations terrain
{local_obs}

### Observations analyse distante
{remote_obs}

### Extraits clés (OCR)
{ocr_snippets}

### Consignes de rédaction
- Style professionnel de consultant QHSE, précis et factuel.
- Résumé structuré en 3-4 phrases (≤ 420 caractères) couvrant :
  * Contexte global et niveau de risque
  * Zones critiques identifiées et impacts business
  * Points de vigilance prioritaires
  * Mention explicite des risques majeurs ou confirmer l'absence d'anomalie critique
- Constats clés (3-5 points) :
  * Détailler le contexte de chaque observation
  * Citer les preuves concrètes (extraits OCR, observations terrain)
  * Évaluer l'impact potentiel sur la sécurité/conformité
  * Mentionner la gravité et le niveau de confiance
- Recommandations (exactement 2) :
  * Actions concrètes et immédiatement actionnables
  * Préciser le responsable suggéré (équipe QHSE, maintenance, etc.)
  * Inclure un délai de mise en œuvre recommandé
  * Estimer l'effort et l'impact attendu
- Ajouter des warnings si :
  * Zones inaccessibles ou données manquantes
  * Contradiction entre observations terrain et analyse
  * Risque nécessitant une expertise complémentaire
- Format JSON strict obligatoire, pas de commentaires additionnels
### Format attendu
{schema_json}
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

    def _translate_severity(self, severity: str | None) -> str:
        if not severity:
            return "non précisée"
        return SEVERITY_TRANSLATIONS.get(severity.lower(), severity)

    def _risk_intro(self, risk: RiskScore | None) -> str | None:
        if not risk:
            return None
        pct = max(0.0, min(1.0, risk.normalized_score)) * 100
        level = self._risk_level_from_percentage(pct)
        return f"Site audité : risque {level} ({pct:.0f}%)."

    def _risk_level_from_percentage(self, pct: float) -> str:
        if pct < 20:
            return "faible"
        if pct < 50:
            return "modéré"
        if pct < 75:
            return "élevé"
        return "critique"

    def _compose_summary(self, summary: str | None, risk: RiskScore | None) -> str | None:
        sanitized = self._sanitize_text(summary)
        if not sanitized:
            return None
        intro = self._risk_intro(risk)
        if intro:
            merged = f"{intro} {sanitized}".strip()
        else:
            merged = sanitized.strip()
        merged = self._ensure_sentence_case(merged)
        return self._truncate_text(merged, SUMMARY_CHAR_LIMIT)

    def _sanitize_list(
        self,
        values: Iterable[str] | None,
        *,
        limit: int = 4,
        sentence_case: bool = True,
    ) -> list[str]:
        cleaned: list[str] = []
        if not values:
            return cleaned
        for value in values:
            sanitized = self._sanitize_text(value)
            if not sanitized:
                continue
            if sentence_case:
                sanitized = self._ensure_sentence_case(sanitized)
            cleaned.append(sanitized)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _sanitize_text(self, text: str | None) -> str | None:
        if not text:
            return None
        sanitized = text.strip()
        for term, replacement in VOCABULARY_REPLACEMENTS.items():
            sanitized = re.sub(term, replacement, sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def _ensure_sentence_case(self, text: str) -> str:
        if not text:
            return text
        stripped = text.strip()
        if not stripped:
            return stripped
        return stripped[0].upper() + stripped[1:]

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def _parse_response(self, payload: str) -> tuple[str | None, list[str], list[str], list[str]]:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            return None, [], [], [f"summary-invalid-json:{exc}"]

        # Construire le résumé à partir des composants
        summary_dict = parsed.get("summary", {})
        if isinstance(summary_dict, dict):
            summary_parts = []
            if summary_dict.get("context"):
                summary_parts.append(str(summary_dict["context"]))
            if summary_dict.get("critical_areas"):
                summary_parts.append(str(summary_dict["critical_areas"]))
            if summary_dict.get("priorities"):
                summary_parts.append(str(summary_dict["priorities"]))
            if summary_dict.get("major_risks"):
                summary_parts.append(str(summary_dict["major_risks"]))
            summary = " ".join(summary_parts) if summary_parts else None
        else:
            summary = str(summary_dict) if summary_dict else None

        # Transformer les constats détaillés en texte
        findings = []
        for finding in parsed.get("key_findings") or []:
            if isinstance(finding, dict):
                finding_parts = []
                if finding.get("observation"):
                    finding_parts.append(str(finding["observation"]))
                if finding.get("context"):
                    finding_parts.append(f"Contexte : {finding['context']}")
                if finding.get("evidence"):
                    finding_parts.append(f"Preuves : {finding['evidence']}")
                if finding.get("impact"):
                    finding_parts.append(f"Impact : {finding['impact']}")
                if finding.get("severity") and finding.get("confidence"):
                    finding_parts.append(f"(Gravité {finding['severity']}, confiance {finding['confidence']})")
                findings.append(" - ".join(finding_parts))
            else:
                findings.append(str(finding))

        # Transformer les recommandations détaillées en texte
        recommendations = []
        for rec in parsed.get("recommendations") or []:
            if isinstance(rec, dict):
                rec_parts = []
                if rec.get("action"):
                    rec_parts.append(str(rec["action"]))
                if rec.get("owner"):
                    rec_parts.append(f"Responsable : {rec['owner']}")
                if rec.get("timeline"):
                    rec_parts.append(f"Délai : {rec['timeline']}")
                if rec.get("effort"):
                    rec_parts.append(f"Effort : {rec['effort']}")
                if rec.get("impact"):
                    rec_parts.append(f"Impact attendu : {rec['impact']}")
                recommendations.append(" - ".join(rec_parts))
            else:
                recommendations.append(str(rec))

        # Transformer les warnings détaillés en texte
        warnings = []
        for warn in parsed.get("warnings") or []:
            if isinstance(warn, dict):
                warn_parts = []
                if warn.get("type"):
                    warn_parts.append(f"[{warn['type']}]")
                if warn.get("description"):
                    warn_parts.append(str(warn["description"]))
                if warn.get("impact"):
                    warn_parts.append(f"Impact : {warn['impact']}")
                warnings.append(" - ".join(warn_parts))
            else:
                warnings.append(str(warn))

        def _ensure_list(value: list | str | None) -> list[str]:
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
        text = self._compose_summary(text, request.risk) or text
        findings = self._sanitize_list(["Analyse avancée indisponible"])
        recommendations = self._sanitize_list(
            ["Relancer la synthèse distante quand la connexion est rétablie."]
        )
        warnings = self._sanitize_list([f"summary-fallback:{error}"], sentence_case=False)
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
