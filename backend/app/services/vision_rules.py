"""Règles métiers pour la vision AUDEX (MVP)."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

try:  # pragma: no cover - OpenCV optionnel dans l'environnement de tests.
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None

from app.pipelines.models import Observation

# Mapping YOLO → (catégorie QHSE, sévérité par défaut)
CLASS_CATEGORY_MAP: Mapping[str, tuple[str, str]] = {
    # === INCENDIE ===
    "fire hydrant": ("incendie", "high"),
    "fire extinguisher": ("incendie", "high"),
    # === HYGIÈNE ===
    "bottle": ("hygiene", "low"),
    "cup": ("hygiene", "low"),
    "wine glass": ("hygiene", "medium"),
    "bowl": ("hygiene", "low"),
    "fork": ("hygiene", "low"),
    "knife": ("hygiene", "medium"),
    "spoon": ("hygiene", "low"),
    "scissors": ("hygiene", "low"),
    "toilet": ("hygiene", "medium"),
    # === CONTRÔLE D'ACCÈS (observation factuelle) ===
    "person": ("access_control", "low"),
    "backpack": ("access_control", "low"),
    "handbag": ("access_control", "low"),
    "suitcase": ("access_control", "medium"),
    # === VÉHICULES ===
    "car": ("access_control", "negligible"),
    "truck": ("access_control", "low"),
    "motorcycle": ("access_control", "negligible"),
    "bicycle": ("access_control", "negligible"),
}

# Objets autorisés selon la zone (aucune observation générée)
ZONE_WHITELIST: Mapping[str, Sequence[str]] = {
    "kitchen": ("knife", "fork", "spoon", "scissors", "bottle", "cup", "bowl"),
    "cafeteria": ("cup", "bottle", "fork", "spoon", "bowl"),
    "parking": ("car", "truck", "motorcycle", "bicycle"),
    "bathroom": ("toilet", "bottle"),
    "reception": ("person", "backpack", "suitcase", "handbag"),
    "office": ("person", "cup", "bottle", "backpack", "handbag"),
}


def _normalize_zone(zone: str | None) -> str | None:
    if not zone:
        return None
    zone_norm = zone.strip().lower()
    return zone_norm or None


def map_class(class_name: str, confidence: float, zone: str | None = None) -> tuple[str, str] | None:
    """Associe une classe YOLO à une catégorie AUDEX en tenant compte du contexte."""
    key = class_name.lower()
    zone_norm = _normalize_zone(zone)

    if zone_norm:
        allowed = ZONE_WHITELIST.get(zone_norm, ())
        if key in allowed:
            return None

    mapping = CLASS_CATEGORY_MAP.get(key)
    if mapping is None:
        return None

    category, severity = mapping

    if confidence >= 0.85 and severity == "low":
        severity = "medium"
    elif confidence >= 0.85 and severity == "medium":
        severity = "high"
    elif confidence <= 0.4:
        severity = "negligible"

    return category, severity


def apply_quality_checks(image_path: Path, zone: str | None = None) -> list[Observation]:
    """Détecte les problèmes de luminosité ou de flou."""
    observations: list[Observation] = []

    if cv2 is None or np is None:
        return observations

    image = cv2.imread(str(image_path))
    if image is None:
        return observations

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    zone_norm = _normalize_zone(zone)

    if mean_brightness < 55.0:
        observations.append(
            Observation(
                source_file=image_path.name,
                label="cleanliness_issue",
                confidence=0.4,
                severity="medium",
                extra={
                    "source": "quality",
                    "issue": "low_light",
                    "mean_brightness": round(mean_brightness, 2),
                    "zone": zone_norm,
                },
            )
        )

    if laplacian_var < 35.0:
        observations.append(
            Observation(
                source_file=image_path.name,
                label="cleanliness_issue",
                confidence=0.4,
                severity="medium",
                extra={
                    "source": "quality",
                    "issue": "blur",
                    "laplacian_variance": round(laplacian_var, 2),
                    "zone": zone_norm,
                },
            )
        )

    return observations
