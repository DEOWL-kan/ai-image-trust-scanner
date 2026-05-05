from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import main as api_main
from app.services.error_taxonomy import (
    Day25InputError,
    analyze_records,
    analyze_records_calibrated,
    build_analysis,
    build_calibrated_analysis,
)
from tools.day25_error_taxonomy import write_calibrated_outputs, write_outputs


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mock_project(tmp_path: Path) -> Path:
    project_root = tmp_path
    (project_root / "reports").mkdir()
    (project_root / "reports" / "day24_error_gallery_report.md").write_text("# Day24\n", encoding="utf-8")
    _write_json(project_root / "reports" / "day24_error_review_notes.json", {"reviews": {}})
    records = [
        {
            "image_path": "data/real/no_exif_wall.jpg",
            "filename": "no_exif_wall.jpg",
            "ground_truth": "real",
            "final_label": "ai",
            "risk_level": "high",
            "confidence": 0.91,
            "scenario": "plain_wall",
            "format_group": "jpg",
            "debug_evidence": {
                "feature_summary": {
                    "risk_factors": ["missing_exif", "jpeg_container_or_compression"],
                    "raw_debug_evidence": {"exif_info": {"has_exif": False}},
                }
            },
        },
        {
            "image_path": "data/ai/photorealistic_phone.png",
            "filename": "photorealistic_phone.png",
            "ground_truth": "ai",
            "final_label": "uncertain",
            "risk_level": "medium",
            "confidence": 0.5,
            "raw_score": 0.16,
            "scenario": "smartphone realistic",
            "format_group": "png",
            "debug_evidence": {"uncertainty_flags": ["score_inside_uncertain_band"]},
        },
        {
            "image_path": "data/ai/clean.png",
            "filename": "clean.png",
            "ground_truth": "ai",
            "final_label": "ai",
            "risk_level": "low",
            "confidence": 0.88,
            "scenario": "object_closeup",
            "format_group": "png",
        },
    ]
    _write_json(project_root / "data" / "benchmark_outputs" / "day23" / "day23_benchmark_results.json", records)
    return project_root


def test_missing_day24_files_raise_clear_error(tmp_path: Path) -> None:
    with pytest.raises(Day25InputError, match="Day24 evidence"):
        build_analysis(tmp_path)


def test_partial_fields_continue_and_score_contract(tmp_path: Path) -> None:
    records = [{"filename": "partial.jpg"}]
    samples = analyze_records(records, tmp_path / "partial_results.json")

    assert samples
    assert isinstance(samples[0]["root_cause_tags"], list)
    assert 0 <= samples[0]["fix_priority_score"] <= 100


def test_day25_outputs_are_generated(tmp_path: Path) -> None:
    project_root = _mock_project(tmp_path)
    analysis = build_analysis(project_root)
    outputs = write_outputs(analysis, project_root / "reports")

    assert outputs["report_md"].exists()
    assert outputs["samples_json"].exists()
    assert outputs["summary_csv"].exists()
    assert outputs["ranking_csv"].exists()
    assert "# Day25 Error Taxonomy Report" in outputs["report_md"].read_text(encoding="utf-8")
    assert all(isinstance(sample["root_cause_tags"], list) for sample in analysis["samples"])
    assert all(0 <= sample["fix_priority_score"] <= 100 for sample in analysis["samples"])


def test_error_taxonomy_endpoint_contract() -> None:
    payload = api_main.error_taxonomy()

    assert payload["status"] == "ok"
    assert "taxonomy_summary" in payload
    assert "root_cause_distribution" in payload
    assert "fix_priority_ranking" in payload
    assert "representative_samples" in payload
    assert "model_change_required_count" in payload
    assert "day26_recommendation" in payload


def test_error_taxonomy_calibrated_endpoint_contract() -> None:
    payload = api_main.error_taxonomy(version="calibrated")

    assert payload["status"] == "ok"
    assert payload["version"] == "day25_1_calibrated"
    assert "taxonomy_summary" in payload
    assert "folder_bias_analysis" in payload
    assert "format_bias_analysis" in payload


def test_calibrated_format_bias_is_weak_for_format_only(tmp_path: Path) -> None:
    samples, _ = analyze_records_calibrated(
        [
            {
                "filename": "plain.jpg",
                "ground_truth": "real",
                "final_label": "real",
                "format_group": "jpg",
            }
        ],
        tmp_path / "results.json",
    )

    evidence = samples[0]["root_cause_evidence"]["format_bias"]
    assert evidence["strength"] == "weak"
    assert samples[0]["primary_root_cause"] != "format_bias"


def test_calibrated_missing_exif_alone_is_not_strong_metadata(tmp_path: Path) -> None:
    samples, _ = analyze_records_calibrated(
        [
            {
                "filename": "missing_exif.png",
                "ground_truth": "real",
                "final_label": "uncertain",
                "format_group": "png",
                "debug_evidence": {"feature_summary": {"risk_factors": ["missing_exif"], "component_scores": {"visual": 0.3}}},
            }
        ],
        tmp_path / "results.json",
    )

    metadata = samples[0]["root_cause_evidence"]["metadata_dependency"]
    assert metadata["strength"] in {"weak", "medium"}
    assert metadata["strength"] != "strong"


def test_calibrated_no_exif_jpeg_fp_is_strong(tmp_path: Path) -> None:
    samples, _ = analyze_records_calibrated(
        [
            {
                "filename": "phone_real.jpg",
                "ground_truth": "real",
                "final_label": "ai",
                "format_group": "jpg",
                "risk_level": "high",
                "confidence": 0.82,
                "debug_evidence": {"feature_summary": {"risk_factors": ["missing_exif"], "component_scores": {}}},
            }
        ],
        tmp_path / "results.json",
    )

    assert samples[0]["root_cause_evidence"]["no_exif_jpeg"]["strength"] == "strong"
    assert samples[0]["primary_root_cause"] == "no_exif_jpeg"


def test_calibrated_source_folder_bias_requires_lift(tmp_path: Path) -> None:
    records = []
    for index in range(12):
        records.append(
            {
                "image_path": f"data/day14/source_a/real_{index}.jpg",
                "ground_truth": "real",
                "final_label": "ai" if index < 10 else "real",
                "format_group": "jpg",
                "source_folder": "data/day14/source_a",
            }
        )
    for index in range(12):
        records.append(
            {
                "image_path": f"data/day14/source_b/real_{index}.jpg",
                "ground_truth": "real",
                "final_label": "real",
                "format_group": "jpg",
                "source_folder": "data/day14/source_b",
            }
        )
    samples, _ = analyze_records_calibrated(records, tmp_path / "results.json")

    source_a = [sample for sample in samples if sample["source_folder"] == "data/day14/source_a"][0]
    source_b = [sample for sample in samples if sample["source_folder"] == "data/day14/source_b"][0]
    assert source_a["root_cause_evidence"]["source_folder_bias"]["strength"] == "strong"
    assert source_b["root_cause_evidence"]["source_folder_bias"]["strength"] == "weak"


def test_calibrated_uncertain_close_to_threshold_is_strong(tmp_path: Path) -> None:
    samples, _ = analyze_records_calibrated(
        [
            {
                "filename": "boundary.jpg",
                "ground_truth": "ai",
                "final_label": "uncertain",
                "confidence": 0.5,
                "raw_score": 0.151,
                "format_group": "jpg",
                "debug_evidence": {
                    "feature_summary": {
                        "raw_debug_evidence": {
                            "threshold_used": 0.15,
                            "score_margin": 0.001,
                            "uncertainty_flags": ["score_inside_uncertain_band"],
                        }
                    }
                },
            }
        ],
        tmp_path / "results.json",
    )

    assert samples[0]["root_cause_evidence"]["score_overlap"]["strength"] == "strong"
    assert samples[0]["root_cause_evidence"]["uncertain_boundary"]["strength"] == "strong"
    assert samples[0]["primary_root_cause"] in {"score_overlap", "uncertain_boundary"}


def test_calibrated_realistic_ai_fn_is_strong_and_primary(tmp_path: Path) -> None:
    samples, _ = analyze_records_calibrated(
        [
            {
                "filename": "photorealistic_smartphone_scene.png",
                "ground_truth": "ai",
                "final_label": "real",
                "scenario": "photorealistic smartphone ordinary photo",
                "format_group": "png",
            }
        ],
        tmp_path / "results.json",
    )

    assert samples[0]["root_cause_evidence"]["realistic_ai"]["strength"] == "strong"
    assert samples[0]["primary_root_cause"] == "realistic_ai"


def test_calibrated_outputs_are_generated(tmp_path: Path) -> None:
    project_root = _mock_project(tmp_path)
    analysis = build_calibrated_analysis(project_root)
    outputs = write_calibrated_outputs(analysis, project_root / "reports")

    assert outputs["calibrated_report_md"].exists()
    assert outputs["calibrated_samples_json"].exists()
    assert outputs["calibrated_summary_csv"].exists()
    assert outputs["calibrated_ranking_csv"].exists()
    assert "# Day25.1 Error Taxonomy Calibrated Report" in outputs["calibrated_report_md"].read_text(encoding="utf-8")
    assert all(isinstance(sample["root_cause_tags"], list) for sample in analysis["samples"])
    assert all("root_cause_evidence" in sample for sample in analysis["samples"])
    assert all(0 <= sample["fix_priority_score"] <= 100 for sample in analysis["samples"])
