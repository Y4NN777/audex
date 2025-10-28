from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.pipelines.models import Observation, RiskBreakdown, RiskScore


@dataclass(slots=True)
class ScoringConfig:
    severity_weights: dict[str, float]
    label_weights: dict[str, float]
    normalization_base: float = 100.0

    @classmethod
    def default(cls) -> "ScoringConfig":
        return cls(
            severity_weights={
                "low": 1.0,
                "medium": 3.0,
                "high": 5.0,
                "critical": 8.0,
            },
            label_weights={
                "incendie": 1.4,
                "malveillance": 1.6,
                "hygiène": 1.2,
                "cyber": 1.5,
                "general": 1.0,
            },
            normalization_base=100.0,
        )


class RiskScorer:
    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig.default()
        self._severity_rank = {name: rank for rank, name in enumerate(["low", "medium", "high", "critical"])}

    def score(self, batch_id: str, observations: Iterable[Observation]) -> RiskScore:
        aggregates: dict[str, dict[str, float | int | str]] = {}
        total_raw = 0.0

        for obs in observations:
            severity = obs.severity.lower()
            label = obs.label.lower()
            severity_weight = self.config.severity_weights.get(severity, 1.0)
            label_weight = self.config.label_weights.get(label, 1.0)
            score_value = severity_weight * label_weight

            if label not in aggregates:
                aggregates[label] = {
                    "count": 0,
                    "score": 0.0,
                    "severity": severity,
                    "rank": self._severity_rank.get(severity, 0),
                }

            aggregates[label]["count"] = int(aggregates[label]["count"]) + 1
            aggregates[label]["score"] = float(aggregates[label]["score"]) + score_value

            current_rank = self._severity_rank.get(severity, 0)
            if current_rank > int(aggregates[label]["rank"]):
                aggregates[label]["severity"] = severity
                aggregates[label]["rank"] = current_rank

            total_raw += score_value

        normalized = (
            min(1.0, total_raw / self.config.normalization_base) if self.config.normalization_base else 0.0
        )

        breakdown = [
            RiskBreakdown(
                label=label,
                severity=str(values["severity"]),
                count=int(values["count"]),
                score=round(float(values["score"]), 2),
            )
            for label, values in aggregates.items()
        ]

        breakdown.sort(key=lambda item: item.score, reverse=True)

        return RiskScore(
            batch_id=batch_id,
            total_score=round(total_raw, 2),
            normalized_score=round(normalized, 3),
            breakdown=breakdown,
        )
