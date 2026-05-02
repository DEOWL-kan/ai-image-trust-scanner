from __future__ import annotations

from core.decision_policy import make_uncertain_decision_v2, make_uncertain_decision_v21


def test_v21_stable_ai_high_confidence() -> None:
    decision = make_uncertain_decision_v21(
        {
            "original": 0.17,
            "long_edge_1024": 0.19,
            "long_edge_768": 0.20,
            "long_edge_512": 0.19,
        },
        {
            "original": "ai",
            "long_edge_1024": "ai",
            "long_edge_768": "ai",
            "long_edge_512": "ai",
        },
    )

    assert decision["final_label"] == "ai"
    assert decision["decision_reason"] == "stable_ai_high_confidence_v21"


def test_v21_resize_biased_ai_becomes_uncertain() -> None:
    decision = make_uncertain_decision_v21(
        {
            "original": 0.14,
            "long_edge_1024": 0.24,
            "long_edge_768": 0.24,
            "long_edge_512": 0.23,
        },
        {
            "original": "real",
            "long_edge_1024": "ai",
            "long_edge_768": "ai",
            "long_edge_512": "ai",
        },
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "stable_ai_but_resize_biased"


def test_v21_low_original_with_resize_bias_recovers_real() -> None:
    decision = make_uncertain_decision_v21(
        {
            "original": 0.13,
            "long_edge_1024": 0.19,
            "long_edge_768": 0.19,
            "long_edge_512": 0.18,
        },
        {
            "original": "real",
            "long_edge_1024": "ai",
            "long_edge_768": "ai",
            "long_edge_512": "ai",
        },
    )

    assert decision["final_label"] == "real"
    assert decision["decision_reason"] == "stable_real_safe_v21"


def test_v21_large_score_range_is_uncertain() -> None:
    decision = make_uncertain_decision_v21(
        {
            "original": 0.17,
            "long_edge_1024": 0.24,
            "long_edge_768": 0.22,
            "long_edge_512": 0.18,
        },
        {
            "original": "ai",
            "long_edge_1024": "ai",
            "long_edge_768": "ai",
            "long_edge_512": "ai",
        },
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "unstable_score_v21"


def test_v21_weak_vote_majority_is_uncertain() -> None:
    decision = make_uncertain_decision_v21(
        {
            "original": 0.145,
            "long_edge_1024": 0.151,
            "long_edge_768": 0.146,
            "long_edge_512": 0.152,
        },
        {
            "original": "real",
            "long_edge_1024": "ai",
            "long_edge_768": "real",
            "long_edge_512": "ai",
        },
    )

    assert decision["final_label"] == "uncertain"
    assert decision["decision_reason"] == "weak_vote_majority_v21"


def test_v2_still_available() -> None:
    decision = make_uncertain_decision_v2(
        [0.19, 0.20, 0.185, 0.195],
        ["ai", "ai", "ai", "ai"],
    )

    assert decision["final_label"] == "ai"
    assert decision["decision_reason"] == "stable_ai_high_confidence"
