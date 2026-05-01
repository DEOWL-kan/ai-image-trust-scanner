from __future__ import annotations

from scripts.day12_uncertain_decision_report import build_summary, normalize_row


def test_day12_summary_treats_uncertain_as_review_not_error() -> None:
    rows = [
        normalize_row(
            {
                "image_path": "data/test_images/real/real_jpeg.jpg",
                "source_id": "real/real_jpeg",
                "true_label": "real",
                "format_group": "jpeg_q95",
                "raw_score": "0.160000",
                "status": "success",
            },
            "day10_format_control",
        ),
        normalize_row(
            {
                "image_path": "data/test_images/ai/ai_png.png",
                "source_id": "ai/ai_png",
                "true_label": "ai",
                "format_group": "png",
                "raw_score": "0.110000",
                "status": "success",
            },
            "day10_format_control",
        ),
        normalize_row(
            {
                "image_path": "data/day11_resolution_control/ai/long_edge_512/ai_resized.png",
                "source_id": "ai/ai_resized",
                "true_label": "ai",
                "resolution_group": "long_edge_512",
                "raw_score": "0.190000",
                "status": "success",
            },
            "day11_resolution_control",
        ),
    ]

    summary = build_summary(rows, {"missing_inputs": [], "missing_fields": {}})

    assert summary["overall"]["total"] == 3
    assert summary["overall"]["final_uncertain_count"] == 1
    assert summary["overall"]["binary_false_positives"] == 1
    assert summary["overall"]["binary_false_negatives"] == 1
    assert summary["overall"]["binary_error_capture_rate"] == 0.5
    assert summary["overall"]["decided_total"] == 2
    assert summary["overall"]["residual_fn_after_uncertain"] == 1
    assert summary["scenarios"]["converted_samples"]["total"] == 2
    assert summary["scenarios"]["ai_png"]["total"] == 2
    assert summary["scenarios"]["resized_samples"]["total"] == 1
