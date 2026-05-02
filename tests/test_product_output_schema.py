from __future__ import annotations

from src.product_output_schema import build_product_output


CORE_FIELDS = {
    "final_label",
    "risk_level",
    "confidence",
    "decision_reason",
    "recommendation",
    "user_facing_summary",
    "technical_explanation",
    "debug_evidence",
}


def test_product_output_contains_core_fields() -> None:
    output = build_product_output(
        {
            "final_label_v21": "ai",
            "original_score": 0.19,
            "raw_label_at_0_15": "ai",
            "resolution_flip_count": 0,
            "score_range": 0.02,
        },
        image_path="sample.jpg",
    )

    assert CORE_FIELDS.issubset(output.keys())


def test_product_label_and_risk_level_are_limited() -> None:
    output = build_product_output({"final_label_v21": "real", "original_score": 0.08})

    assert output["final_label"] in {"likely_ai", "likely_real", "uncertain"}
    assert output["risk_level"] in {"high", "medium", "low"}


def test_confidence_is_between_zero_and_one() -> None:
    output = build_product_output({"final_label_v21": "uncertain", "original_score": 0.151})

    assert 0.0 <= output["confidence"] <= 1.0


def test_missing_raw_fields_do_not_crash() -> None:
    output = build_product_output({})

    assert output["final_label"] == "uncertain"
    assert output["risk_level"] == "medium"
    assert isinstance(output["debug_evidence"], dict)


def test_uncertain_recommendation_asks_for_more_evidence() -> None:
    output = build_product_output({"final_label_v21": "uncertain"})
    recommendation = output["recommendation"]

    assert any(
        keyword in recommendation
        for keyword in ("上传原始", "人工复核", "更多证据")
    )


def test_debug_evidence_is_dict() -> None:
    output = build_product_output({"final_label_v21": "ai"})

    assert isinstance(output["debug_evidence"], dict)
