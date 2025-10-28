from __future__ import annotations

from app.pipelines.models import Observation
from app.services.scoring import RiskScorer, ScoringConfig


def test_risk_scorer_aggregates_by_label_and_severity() -> None:
    observations = [
        Observation(source_file="a.jpg", label="incendie", confidence=0.9, severity="high"),
        Observation(source_file="b.jpg", label="incendie", confidence=0.6, severity="medium"),
        Observation(source_file="c.jpg", label="cyber", confidence=0.4, severity="low"),
    ]

    scorer = RiskScorer(
        ScoringConfig(
            severity_weights={"low": 1, "medium": 3, "high": 5},
            label_weights={"incendie": 2.0, "cyber": 1.5},
            normalization_base=50,
        )
    )

    result = scorer.score("batch-xyz", observations)

    assert result.batch_id == "batch-xyz"
    assert result.total_score == 5 * 2 + 3 * 2 + 1 * 1.5  # 10 + 6 + 1.5 = 17.5
    assert result.normalized_score == round(result.total_score / 50, 3)
    assert len(result.breakdown) == 2
    incendie = next(item for item in result.breakdown if item.label == "incendie")
    assert incendie.count == 2
    assert incendie.score == 16.0  # (5 + 3) * 2


def test_risk_scorer_defaults_handle_unknown_labels() -> None:
    observations = [
        Observation(source_file="a.jpg", label="unknown", confidence=0.5, severity="critical"),
        Observation(source_file="b.jpg", label="unknown", confidence=0.5, severity="low"),
    ]

    scorer = RiskScorer()
    result = scorer.score("batch-abc", observations)

    assert result.total_score > 0
    assert any(item.label == "unknown" for item in result.breakdown)
