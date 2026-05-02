from __future__ import annotations

from src.api_adapter import build_error_response, build_frontend_response


DAY17_RAW_RESULT = {
    "final_label": "likely_ai",
    "risk_level": "high",
    "confidence": 0.82,
    "decision_reason": ["stable_ai_high_confidence_v21"],
    "recommendation": "Treat this image carefully.",
    "user_facing_summary": "The image has AI-like risk signals.",
    "technical_explanation": "Day17 technical explanation.",
    "debug_evidence": {
        "raw_score": 0.19,
        "threshold_used": 0.15,
        "risk_factors": ["ai_like_score_pattern"],
        "stability_factors": ["multi_resolution_label_consistency"],
        "uncertainty_flags": [],
        "multi_resolution": {
            "score_range": 0.02,
            "resolution_flip_count": 0,
        },
        "format_info": {"format": "png"},
        "exif_info": {"has_exif": False},
    },
}


def test_frontend_response_contains_stable_top_level_fields() -> None:
    response = build_frontend_response(
        DAY17_RAW_RESULT,
        image_meta={
            "filename": "sample.png",
            "width": 1024,
            "height": 768,
            "format": "png",
            "size_bytes": 123,
        },
        request_id="req-1",
    )

    assert set(response.keys()) == {"schema_version", "status", "request_id", "data", "meta"}
    assert response["status"] == "success"
    assert response["request_id"] == "req-1"
    assert set(response["data"].keys()) == {"image", "result"}


def test_enums_are_frontend_contract_values() -> None:
    response = build_frontend_response(DAY17_RAW_RESULT)
    result = response["data"]["result"]

    assert result["final_label"] in {"ai_generated", "real_photo", "uncertain"}
    assert result["risk_level"] in {"low", "medium", "high"}
    assert result["recommendation"]["action"] in {"allow", "review", "warn"}


def test_confidence_is_always_normalized_to_zero_one() -> None:
    response = build_frontend_response({**DAY17_RAW_RESULT, "confidence": 82})

    assert response["data"]["result"]["confidence"] == 0.82
    assert 0.0 <= response["data"]["result"]["confidence"] <= 1.0


def test_include_debug_false_keeps_shape_without_internal_details() -> None:
    response = build_frontend_response(DAY17_RAW_RESULT, include_debug=False)
    debug = response["data"]["result"]["debug_evidence"]

    assert set(debug.keys()) == {
        "enabled",
        "raw_score",
        "feature_summary",
        "consistency_checks",
        "format_evidence",
        "resolution_evidence",
    }
    assert debug["enabled"] is False
    assert debug["raw_score"] is None
    assert debug["feature_summary"] == {}
    assert debug["consistency_checks"] == {}
    assert debug["format_evidence"] == {}
    assert debug["resolution_evidence"] == {}


def test_error_response_shape_is_stable() -> None:
    response = build_error_response(
        "INVALID_IMAGE",
        "Image could not be opened.",
        details={"filename": "broken.jpg"},
        request_id="req-error",
    )

    assert response["status"] == "error"
    assert response["request_id"] == "req-error"
    assert response["data"] is None
    assert response["error"] == {
        "code": "INVALID_IMAGE",
        "message": "Image could not be opened.",
        "details": {"filename": "broken.jpg"},
    }
    assert set(response["meta"].keys()) == {"processed_at", "adapter_version"}


def test_day17_output_keeps_core_information_after_adapter() -> None:
    response = build_frontend_response(DAY17_RAW_RESULT)
    result = response["data"]["result"]

    assert result["final_label"] == "ai_generated"
    assert result["risk_level"] == "high"
    assert result["confidence"] == 0.82
    assert result["decision_reason"][0]["code"] == "stable_ai_high_confidence_v21"
    assert result["recommendation"]["message"] == "Treat this image carefully."
    assert result["user_facing_summary"] == DAY17_RAW_RESULT["user_facing_summary"]
    assert result["technical_explanation"]["score"] == 0.19
    assert result["debug_evidence"]["enabled"] is True


def test_uncertain_is_not_forced_to_binary_label() -> None:
    response = build_frontend_response({**DAY17_RAW_RESULT, "final_label": "uncertain"})

    assert response["data"]["result"]["final_label"] == "uncertain"
    assert response["data"]["result"]["recommendation"]["action"] == "review"
