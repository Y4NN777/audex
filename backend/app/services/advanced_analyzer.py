"""Analyse avancée des images via Gemini 2.0 (spec QHSE Burkina)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from app.core.config import settings
from app.pipelines.models import Observation

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiAnalysisResult:
    observations: List[Observation]
    summary: str | None
    status: str
    warnings: List[str]
    prompt_hash: str | None = None
    duration_ms: int | None = None


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class AdvancedAnalyzer:
    """Orchestrateur Gemini (moyen terme : stub offline, prêt pour API réelle)."""

    def __init__(self) -> None:
        self.enabled = settings.GEMINI_ENABLED
        self.required = settings.GEMINI_REQUIRED
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.timeout = settings.GEMINI_TIMEOUT_SECONDS
        self.max_retries = settings.GEMINI_MAX_RETRIES

    def analyze(
        self,
        batch_id: str,
        image_files: Sequence[tuple[Path, str | None, str | None]],
    ) -> GeminiAnalysisResult:
        if not self.enabled:
            return GeminiAnalysisResult(observations=[], summary=None, status="disabled", warnings=[])

        if not self.api_key:
            warning = "gemini-missing-api-key"
            status = "failed" if self.required else "skipped"
            return GeminiAnalysisResult(
                observations=[],
                summary=None,
                status=status,
                warnings=[warning],
            )

        start_time = time.perf_counter()
        warnings: list[str] = []
        observations: list[Observation] = []
        last_prompt_hash: str | None = None

        for image_path, zone, site_type in image_files:
            prompt = self._build_prompt(zone_name=zone, site_type=site_type or "generic")
            prompt_hash = _hash_prompt(prompt)
            last_prompt_hash = prompt_hash
            try:
                response = self._call_gemini(image_path, prompt, prompt_hash)
            except Exception as exc:  # pragma: no cover - dépend de l'API réelle
                warning = f"gemini-error:{image_path.name}:{exc}"
                logger.warning("%s - %s", batch_id, warning)
                warnings.append(warning)
                if self.required:
                    raise
                continue

            try:
                parsed = json.loads(response)
            except json.JSONDecodeError as exc:
                warning = f"gemini-response-invalid:{image_path.name}:{exc}"
                logger.warning("%s - %s", batch_id, warning)
                warnings.append(warning)
                if self.required:
                    raise
                continue

            observations.extend(gemini_to_observations(parsed, image_path, zone_name=zone))

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        summary = build_gemini_summary(observations, warnings)
        status = "ok" if observations or summary else "no_insights"
        return GeminiAnalysisResult(
            observations=observations,
            summary=summary,
            status=status,
            warnings=warnings,
            prompt_hash=last_prompt_hash,
            duration_ms=duration_ms,
        )

    def _build_prompt(self, zone_name: str | None, site_type: str = "generic") -> str:
        zone_context = f"Zone : {zone_name}" if zone_name else "Zone non spécifiée"
        site_contexts = {
            "datacenter": "Site critique infrastructure télécom. Risques : intrusion, sabotage, vol équipements.",
            "bank": "Site financier. Risques : braquage, intrusion, attaque explosive.",
            "embassy": "Site diplomatique. Risques : attentat, manifestations, intrusion.",
            "industrial": "Site industriel. Risques : sabotage, vol, intrusion.",
            "ngo": "Site ONG internationale. Risques : enlèvement personnel, intrusion, vol.",
        }
        site_info = site_contexts.get(site_type.lower(), "Site sensible nécessitant audit de sûreté.")

        return f"""Tu es un expert en sûreté/sécurité physique analysant cette photo d'audit au Burkina Faso.

CONTEXTE SITE :
{zone_context}
{site_info}

CONTEXTE SÉCURITAIRE BURKINA FASO :
- Menace terroriste active (JNIM, EIGS)
- Risque criminalité élevé (braquages, vols à main armée)
- Infrastructure sécuritaire limitée
- Normes internationales OSAC / ISO 31000 à respecter

ANALYSE À EFFECTUER (scores 0-10) :

1. PÉRIMÈTRE (perimeter_score) :
   - État clôtures/murs (hauteur ≥2.5m, intégrité, barbelés concertina)
   - Portails/barrières (robustesse, contrôle accès)
   - Points faibles : trous, sections basses, végétation facilitant escalade
   - Éclairage périmétrique (zones sombres = vulnérabilité)

2. CONTRÔLE D'ACCÈS (access_control_score) :
   - Guérites/postes garde (positionnement, visibilité)
   - Barrières physiques entrées (chicanes, plots anti-bélier, distance VBIED ≥25m)
   - Séparation piétons/véhicules
   - Caméras surveillance (angles morts, état)

3. SÉCURITÉ INCENDIE (fire_safety_score) :
   - Extincteurs (présence, accessibilité, contrôle à jour)
   - Détecteurs fumée visibles
   - Issues secours (dégagées, signalées, éclairées)
   - RIA/hydrants (présence, signalisation)

4. SOLIDITÉ STRUCTURELLE (structural_score) :
   - Fenêtres (barreaux, films anti-effraction)
   - Portes (blindées, serrures multipoints)
   - Toiture/murs (points escalade possibles)
   - Protection anti-projectiles (sacs sable, abris renforcés)

DÉTECTE LES VULNÉRABILITÉS :
- fence_breach, missing_barrier, unlit_area, camera_blind_spot,
  missing_signage, weak_access_point, vegetation_risk,
  unsecured_generator, inadequate_guard_post, missing_fire_equipment

RÉPONDS UNIQUEMENT EN JSON VALIDE :
{{
    "security_level": "low|medium|high|critical",
    "perimeter_score": 0-10,
    "access_control_score": 0-10,
    "fire_safety_score": 0-10,
    "structural_score": 0-10,
    "vulnerabilities": [
        {{
            "category": "perimeter|access|fire|structural|signage|personnel",
            "type": "fence_breach|missing_barrier|...",
            "description": "Description précise du problème",
            "severity": "low|medium|high|critical",
            "location": "Localisation dans l'image",
            "recommendation": "Action corrective recommandée"
        }}
    ],
    "security_assets": [
        {{
            "type": "camera|guard|barrier|lighting|fence|signage|fire_extinguisher",
            "condition": "good|degraded|non_functional",
            "coverage": "adequate|partial|insufficient"
        }}
    ],
    "immediate_risks": [
        "Liste des risques nécessitant action immédiate"
    ]
}}"""

    def _call_gemini(self, image_path: Path, prompt: str, prompt_hash: str) -> str:
        """Appel au modèle Gemini (stub offline pour le MVP)."""

        # Placeholder : renvoie un JSON minimal.
        # Lorsque l'appel réel sera implémenté, cette méthode devra :
        #  - utiliser google-generativeai ou une requête HTTP
        #  - gérer les retries / timeouts
        #  - retourner la chaîne JSON reçue
        logger.debug("Gemini disabled for offline mode. Returning empty response for %s", image_path)
        return json.dumps(
            {
                "security_level": "medium",
                "perimeter_score": 5,
                "access_control_score": 5,
                "fire_safety_score": 5,
                "structural_score": 5,
                "vulnerabilities": [],
                "security_assets": [],
                "immediate_risks": [],
            }
        )


def gemini_to_observations(
    gemini_result: dict,
    image_path: Path,
    zone_name: str | None = None,
) -> list[Observation]:
    """Convertit la réponse JSON Gemini en observations AUDEX."""

    observations: list[Observation] = []
    category_map = {
        "perimeter": "access_control",
        "access": "access_control",
        "fire": "incendie",
        "structural": "malveillance",
        "signage": "hygiene",
        "personnel": "access_control",
    }

    for vuln in gemini_result.get("vulnerabilities", []):
        category = vuln.get("category")
        qhse_category = category_map.get(category, "malveillance")
        observations.append(
            Observation(
                source_file=image_path.name,
                label=f"security_{vuln.get('type', 'unknown')}",
                confidence=0.75,
                severity=str(vuln.get("severity", "medium")),
                extra={
                    "source": "gemini",
                    "category": qhse_category,
                    "description": vuln.get("description"),
                    "location": vuln.get("location"),
                    "recommendation": vuln.get("recommendation"),
                    "zone": zone_name,
                },
            )
        )

    security_level = gemini_result.get("security_level")
    if security_level in {"low", "critical"}:
        observations.append(
            Observation(
                source_file=image_path.name,
                label="security_level_alert",
                confidence=0.8,
                severity="critical" if security_level == "critical" else "high",
                extra={
                    "source": "gemini",
                    "category": "malveillance",
                    "security_level": security_level,
                    "perimeter_score": gemini_result.get("perimeter_score"),
                    "access_control_score": gemini_result.get("access_control_score"),
                    "fire_safety_score": gemini_result.get("fire_safety_score"),
                    "structural_score": gemini_result.get("structural_score"),
                    "immediate_risks": gemini_result.get("immediate_risks", []),
                    "zone": zone_name,
                },
            )
        )

    return observations


def build_gemini_summary(observations: Iterable[Observation], warnings: Iterable[str]) -> str | None:
    payload = {
        "observations": [
            {
                "label": obs.label,
                "severity": obs.severity,
                "source": obs.extra.get("source") if isinstance(obs.extra, dict) else None,
            }
            for obs in observations
        ],
        "warnings": list(warnings),
    }
    if not payload["observations"] and not payload["warnings"]:
        return None
    return json.dumps(payload, ensure_ascii=False)
