from __future__ import annotations

import json

from core.decision_policy import (
    BASELINE_THRESHOLD,
    FINAL_AI_THRESHOLD,
    FINAL_REAL_THRESHOLD,
    binary_label_at_threshold,
    decide_final_label,
    get_final_label,
)
from core.score_fusion import DEFAULT_FUSION_WEIGHTS, fuse_scores, load_detector_weight_config


def test_final_label_boundaries() -> None:
    cases = [
        (0.11, "real"),
        (0.12, "real"),
        (0.13, "uncertain"),
        (0.15, "uncertain"),
        (0.17, "uncertain"),
        (0.18, "ai"),
        (0.19, "ai"),
    ]

    for score, expected in cases:
        assert get_final_label(score) == expected


def test_baseline_binary_threshold_is_unchanged() -> None:
    assert BASELINE_THRESHOLD == 0.15
    assert binary_label_at_threshold(0.15, BASELINE_THRESHOLD) == "ai"
    assert binary_label_at_threshold(0.149999, BASELINE_THRESHOLD) == "real"

    decision = decide_final_label(0.15)

    assert "binary_label_at_threshold" in decision
    assert decision["binary_label_at_threshold"] == "ai"
    assert decision["final_label"] == "uncertain"
    assert decision["baseline_threshold"] == 0.15
    assert decision["final_real_threshold"] == 0.12
    assert decision["final_ai_threshold"] == 0.18


def test_final_label_does_not_change_score_or_binary_label() -> None:
    score = 0.17
    decision = decide_final_label(score)

    assert decision["raw_score"] == score
    assert decision["binary_label_at_threshold"] == "ai"
    assert decision["final_label"] == "uncertain"


def test_fuse_score_still_uses_baseline_weights_and_score_math() -> None:
    result = fuse_scores(
        metadata_result={"checked": True, "has_exif": False, "software": None},
        forensic_result={
            "checked": True,
            "edge_density": 0.1,
            "laplacian_variance": 100,
            "noise_estimate": 3.0,
            "brightness_std": 20.0,
        },
        frequency_result={"checked": True, "frequency_score": 0.2},
        model_result={"checked": True, "ai_probability": 0.99, "model_status": "placeholder"},
    )

    assert result["final_score"] == 0.084375
    assert result["raw_score"] == 0.084375
    assert result["binary_label_at_threshold"] == "real"
    assert result["final_label"] == "real"
    assert result["component_weights"] == DEFAULT_FUSION_WEIGHTS


def test_balanced_v2_candidate_is_diagnostic_only_and_weights_unchanged() -> None:
    config = load_detector_weight_config()

    assert config["default_profile"] == "baseline"
    assert "balanced_v2_candidate" in config["profiles"]
    assert config["profiles"]["baseline"]["fusion_weights"] == {
        "metadata": 0.15,
        "forensic": 0.35,
        "frequency": 0.30,
        "model": 0.0,
    }
    assert DEFAULT_FUSION_WEIGHTS == {
        "metadata": 0.15,
        "forensic": 0.35,
        "frequency": 0.30,
        "model": 0.0,
    }
    assert config["decision_policy"]["baseline_threshold"] == BASELINE_THRESHOLD
    assert config["decision_policy"]["final_real_threshold"] == FINAL_REAL_THRESHOLD
    assert config["decision_policy"]["final_ai_threshold"] == FINAL_AI_THRESHOLD

    # Guard against accidental profile promotion through JSON rewrite quirks.
    assert json.dumps(config).count("balanced_v2_candidate") == 1
