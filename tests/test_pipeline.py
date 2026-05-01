from __future__ import annotations

from pathlib import Path

from core.forensic_analyzer import analyze_forensics
from core.frequency_analyzer import analyze_frequency
from core.image_loader import load_image
from core.metadata_analyzer import analyze_metadata
from core.model_detector import detect_with_model
from core.report_generator import build_report
from core.score_fusion import fuse_scores, get_fusion_weights, load_detector_weight_config
from main import run_pipeline


def test_modules_importable() -> None:
    assert callable(load_image)
    assert callable(analyze_metadata)
    assert callable(analyze_forensics)
    assert callable(analyze_frequency)
    assert callable(detect_with_model)
    assert callable(fuse_scores)
    assert callable(build_report)


def test_missing_image_has_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jpg"
    result = load_image(missing)

    assert result["ok"] is False
    assert "does not exist" in result["error"]


def test_main_pipeline_callable_for_missing_image(tmp_path: Path) -> None:
    report = run_pipeline(tmp_path / "missing.jpg", output_dir=tmp_path / "reports")

    assert report["ok"] is False
    assert report["image_info"]["ok"] is False
    assert report["final_result"]["risk_level"] in {"low", "medium", "high", "very_high"}
    assert Path(report["report_paths"]["json_report"]).exists()
    assert Path(report["report_paths"]["markdown_report"]).exists()


def test_placeholder_model_is_not_weighted_as_trained_evidence() -> None:
    result = fuse_scores(
        metadata_result={"checked": True, "has_exif": False, "software": None},
        forensic_result={"checked": True, "edge_density": 0.1, "laplacian_variance": 100},
        frequency_result={"checked": True, "frequency_score": 0.2},
        model_result={
            "checked": True,
            "ai_probability": 0.99,
            "model_status": "placeholder",
        },
    )

    assert result["component_weights"]["model"] == 0.0
    assert result["component_scores"]["model_score"] == 0.0
    assert (
        "Deep model detector is placeholder and is not used as trained evidence."
        in result["evidence_summary"]
    )


def test_detector_weights_config_exposes_day9_concepts() -> None:
    config = load_detector_weight_config()
    baseline = config["profiles"]["baseline"]
    experiment_weights = baseline["experiment_weights"]

    for key in (
        "texture_weight",
        "edge_weight",
        "noise_weight",
        "compression_weight",
        "metadata_weight",
        "color_weight",
        "blur_penalty_weight",
        "low_confidence_margin",
    ):
        assert key in experiment_weights

    assert get_fusion_weights()["metadata"] == 0.15
    assert get_fusion_weights()["frequency"] == 0.30
