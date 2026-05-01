from __future__ import annotations

from scripts.day9_error_analysis import (
    AnalyzedSample,
    attribution_bucket,
    classify_scene_tag,
    classify_scenario,
    component_contributions,
    dominant_component,
    scene_strategy_label,
)


def test_component_contributions_match_existing_fusion_math() -> None:
    scores = {"metadata": 0.05, "forensic": 0.0, "frequency": 0.531598, "model": 0.0}
    weights = {"metadata": 0.15, "forensic": 0.35, "frequency": 0.30, "model": 0.0}

    contributions = component_contributions(scores, weights)

    assert contributions["metadata"] == 0.009375
    assert contributions["frequency"] == 0.199349
    assert round(sum(contributions.values()), 6) == 0.208724
    assert dominant_component(contributions) == "frequency"


def test_classify_scenario_web_jpeg_without_exif() -> None:
    report = {
        "image_info": {"format": "JPEG"},
        "metadata_result": {"has_exif": False, "camera_model": None, "software": None},
    }

    assert classify_scenario(report) == "web_or_social_jpeg_no_exif"


def test_false_positive_frequency_bucket() -> None:
    sample = AnalyzedSample(
        filename="real_001.jpg",
        class_label="real",
        ground_truth="Real",
        ai_score=0.208724,
        report={
            "image_info": {"format": "JPEG"},
            "metadata_result": {"has_exif": False},
        },
        component_scores={"metadata": 0.05, "forensic": 0.0, "frequency": 0.531598, "model": 0.0},
        component_weights={"metadata": 0.15, "forensic": 0.35, "frequency": 0.30, "model": 0.0},
        contributions={"metadata": 0.009375, "forensic": 0.0, "frequency": 0.199349, "model": 0.0},
        scenario="web_or_social_jpeg_no_exif",
        scene_tag="road",
    )

    assert attribution_bucket(sample, 0.15) == "frequency_dominated_real_image"


def test_scene_tag_low_light_from_brightness() -> None:
    report = {
        "image_info": {"format": "JPEG", "width": 1200, "height": 900},
        "metadata_result": {"has_exif": False},
        "forensic_result": {
            "brightness_mean": 58,
            "brightness_std": 22,
            "edge_density": 0.08,
            "laplacian_variance": 300,
            "noise_estimate": 2.5,
        },
    }

    assert classify_scene_tag("real_001.jpg", report) == "low_light"


def test_scene_strategy_keeps_binary_but_adds_uncertain_near_threshold() -> None:
    sample = AnalyzedSample(
        filename="ai_005.png",
        class_label="ai",
        ground_truth="AI-generated",
        ai_score=0.144,
        report={
            "image_info": {"format": "PNG", "file_size_kb": 2300},
            "metadata_result": {"has_exif": False},
            "forensic_result": {
                "brightness_mean": 140,
                "edge_density": 0.03,
                "laplacian_variance": 160,
                "noise_estimate": 2.4,
                "brightness_std": 60,
            },
            "frequency_result": {"frequency_score": 0.35},
        },
        component_scores={"metadata": 0.05, "forensic": 0.0, "frequency": 0.35, "model": 0.0},
        component_weights={"metadata": 0.15, "forensic": 0.35, "frequency": 0.30, "model": 0.0},
        contributions={"metadata": 0.009375, "forensic": 0.0, "frequency": 0.13125, "model": 0.0},
        scenario="png_export_no_exif",
        scene_tag="closeup_object",
    )

    strategy = scene_strategy_label(sample, threshold=0.15, margin=0.03)

    assert strategy["final_label"] == "uncertain"
    assert strategy["confidence_level"] == "low"
