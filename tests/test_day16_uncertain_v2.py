from __future__ import annotations

from core.decision_policy import make_uncertain_decision_v2


def test_day16_stable_ai_high_confidence() -> None:
    decision = make_uncertain_decision_v2(
        [0.19, 0.20, 0.185, 0.195],
        ["ai", "ai", "ai", "ai"],
    )

    assert decision["final_label"] == "ai"
    assert decision["decision_reason"] == "stable_ai_high_confidence"
    assert decision["resolution_flip_count"] == 0


def test_day16_near_threshold_band_is_uncertain() -> None:
    decision = make_uncertain_decision_v2(
        [0.14, 0.16, 0.15, 0.155],
        ["real", "ai", "ai", "ai"],
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "near_threshold_band"


def test_day16_resolution_flip_with_large_range_is_uncertain() -> None:
    decision = make_uncertain_decision_v2(
        [0.10, 0.19, 0.20, 0.18],
        ["real", "ai", "ai", "ai"],
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "resolution_flip"
    assert decision["resolution_flip_count"] == 1


def test_day16_weak_vote_majority_is_uncertain() -> None:
    decision = make_uncertain_decision_v2(
        [0.145, 0.151, 0.146, 0.152],
        ["real", "ai", "real", "ai"],
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "weak_vote_majority"
