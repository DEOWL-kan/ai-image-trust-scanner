from __future__ import annotations

from scripts.day9_weight_ablation import concept_signals, profile_score


def sample_report() -> dict[str, object]:
    return {
        "image_info": {"format": "PNG"},
        "metadata_result": {"checked": True, "has_exif": False, "software": None},
        "forensic_result": {
            "edge_density": 0.02,
            "laplacian_variance": 120.0,
            "noise_estimate": 2.0,
            "color_channel_std": {"red": 50.0, "green": 48.0, "blue": 49.0},
        },
        "frequency_result": {"frequency_score": 0.33},
        "final_result": {
            "final_score": 0.14,
            "component_scores": {
                "metadata_score": 0.05,
                "forensic_score": 0.0,
                "frequency_score": 0.33,
                "model_score": 0.0,
            },
        },
    }


def test_baseline_profile_score_uses_existing_day8_score() -> None:
    assert profile_score(sample_report(), "baseline", {}) == 0.14


def test_concept_signals_include_required_weight_keys() -> None:
    signals = concept_signals(sample_report())

    for key in (
        "texture_weight",
        "edge_weight",
        "noise_weight",
        "compression_weight",
        "metadata_weight",
        "color_weight",
        "blur_penalty_weight",
        "frequency_weight",
    ):
        assert key in signals
        assert 0.0 <= signals[key] <= 1.0
