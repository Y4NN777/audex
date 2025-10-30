"""Analyse avancée des images via Gemini 2.0 (spec QHSE Burkina)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence, Any

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
    payloads: List[dict[str, Any]] = field(default_factory=list)
    model: str | None = None
    provider: str = "google-gemini"
    prompt_version: str | None = None


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class AdvancedAnalyzer:
    """Orchestrateur Gemini (moyen terme : stub offline, prêt pour API réelle)."""

    PROVIDER = "google-gemini"
    PROMPT_VERSION = "schema-1.4-bfa"

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
            return GeminiAnalysisResult(
                observations=[],
                summary=None,
                status="disabled",
                warnings=[],
                model=self.model,
                provider=self.PROVIDER,
                prompt_version=self.PROMPT_VERSION,
            )

        if not self.api_key:
            warning = "gemini-missing-api-key"
            status = "failed" if self.required else "skipped"
            return GeminiAnalysisResult(
                observations=[],
                summary=None,
                status=status,
                warnings=[warning],
                model=self.model,
                provider=self.PROVIDER,
                prompt_version=self.PROMPT_VERSION,
            )

        start_time = time.perf_counter()
        warnings: list[str] = []
        observations: list[Observation] = []
        last_prompt_hash: str | None = None
        payloads: list[dict[str, Any]] = []

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
            payloads.append(parsed)

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
             payloads=payloads,
             model=self.model,
             provider=self.PROVIDER,
             prompt_version=self.PROMPT_VERSION,
        )


    def _build_prompt(self, zone_name: str | None, site_type: str = "generic") -> str:
        st = (site_type or "generic").lower()
        
        PROMPT_TEMPLATE = """\
        Tu es un expert en sûreté, sécurité physique et hygiène opérant au Burkina Faso.
        Analyse cette IMAGE d’audit et produis **UNIQUEMENT** un JSON valide conforme au **Schéma v1.4** ci-dessous.

        CONTEXTE SITE :
        - Zone : {zone_name}
        - Type de site : {site_type}
        - Contexte : {site_risk_context}

        CONTEXTE SÉCURITAIRE BURKINA FASO :
        - Menace terroriste active (JNIM, EIGS)
        - Risque criminalité élevé (braquages, vols à main armée)
        - Infrastructure sécuritaire limitée
        - Normes internationales à respecter : OSAC / ISO 31000 / ISO 45001

        ANALYSE À EFFECTUER (scores 0-10)

        1. PÉRIMÈTRE (perimeter_score) :
        - État clôtures/murs (hauteur ≥ 2.5 m, intégrité, barbelés concertina)
        - Portails/barrières (robustesse, contrôle accès)
        - Points faibles : trous, sections basses, végétation facilitant escalade
        - Éclairage périmétrique (zones sombres = vulnérabilité)

        2. CONTRÔLE D’ACCÈS (access_control_score) :
        - Guérites/postes garde (positionnement, visibilité)
        - Barrières physiques entrées (chicanes, plots anti-bélier, distance VBIED ≥ 25 m)
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

        5. HYGIÈNE (hygiene_score) :
        - Propreté (sols, déchets, encombrements)
        - Accès à l’eau potable (fontaines, bouteilles)
        - Installations sanitaires (toilettes, lavabos)
        - Gestion déchets / nuisibles / signalétique EPI
        - Présence d’eau stagnante ou d’odeurs anormales

        DÉTECTE LES VULNÉRABILITÉS :
        - fence_breach, missing_barrier, unlit_area, camera_blind_spot,
        missing_signage, weak_access_point, vegetation_risk, unsecured_generator,
        inadequate_guard_post, missing_fire_equipment,
        waste_accumulation, standing_water, inadequate_sanitation, no_potable_water,
        pest_infestation, blocked_circulation, missing_PPE_signage, food_safety_noncompliance

        RÉPONDS UNIQUEMENT EN JSON VALIDE :
        {{
        "schema_version": "1.4",
        "security_level": "low|medium|high|critical",
        "perimeter_score": 0-10,
        "access_control_score": 0-10,
        "fire_safety_score": 0-10,
        "structural_score": 0-10,
        "hygiene_score": 0-10,
        "vulnerabilities": [
            {{
            "category": "perimeter|access|fire|structural|signage|personnel|hygiene",
            "type": "voir taxonomie ci-dessus",
            "description": "fait observable, concret et bref",
            "severity": "low|medium|high|critical",
            "location": "ex : 'gauche', 'fond', 'près du portail'",
            "recommendation": "action corrective pragmatique et faisable"
            }}
        ],
        "security_assets": [
            {{
            "type": "camera|guard|barrier|lighting|fence|signage|fire_extinguisher",
            "condition": "good|degraded|non_functional",
            "coverage": "adequate|partial|insufficient"
            }}
        ],
        "immediate_risks": ["...", "..."],
        "notes": {{
            "uncertainties": ["éléments non visibles ou ambigus"],
            "assumptions": []
        }}
        }}

        RÈGLES STRICTES :
        - Retourne uniquement le JSON, sans texte ni balises.
        - Utilise null si un élément est incertain.
        - Ne fais pas d’hypothèses ni de reformulations.

        ### Exemple attendu (hygiène + périmètre faibles)
        {{
        "schema_version":"1.4",
        "security_level":"high",
        "perimeter_score":4,
        "access_control_score":5,
        "fire_safety_score":6,
        "structural_score":6,
        "hygiene_score":3,
        "vulnerabilities":[
            {{"category":"perimeter","type":"fence_breach","description":"Brèche visible dans la clôture","severity":"high","location":"droite","recommendation":"Réparer la clôture et renforcer l’éclairage"}},
            {{"category":"hygiene","type":"waste_accumulation","description":"Déchets visibles au sol","severity":"medium","location":"zone centrale","recommendation":"Installer bacs fermés et assurer nettoyage quotidien"}}
        ],
        "security_assets":[{{"type":"lighting","condition":"degraded","coverage":"partial"}}],
        "immediate_risks":["Intrusion facilitée","Risque sanitaire lié aux déchets"],
        "notes":{{"uncertainties":["État extincteurs non visible"],"assumptions":[]}}
        }}
        """

        SITE_RISK_CONTEXTS = {
            "datacenter": "Site critique (télécom/IT). Priorités: contrôle d’accès multi-couches, incendie, continuité électrique.",
            "bank": "Site financier. Priorités: anti-intrusion, anti-bélier, séparation flux, angles morts caméras.",
            "embassy": "Site diplomatique. Priorités: périmètre, contrôle foule, blast standoff, évacuation.",
            "industrial": "Site industriel. Priorités: incendie, EPI, circulation engins, stock dangereux, périmètre large.",
            "ngo": "Site ONG. Priorités: sûreté du personnel, visiteurs, périmètre, routines d’urgence.",
            "generic": "Site sensible nécessitant audit pragmatique (sûreté + hygiène minimale)."
        }


        
        return PROMPT_TEMPLATE.format(
            zone_name=zone_name or "Non spécifiée",
            site_type=st,
            site_risk_context=SITE_RISK_CONTEXTS.get(st, SITE_RISK_CONTEXTS["generic"])
        )

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
