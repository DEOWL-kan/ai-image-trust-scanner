from __future__ import annotations

from typing import Any

from app.policy.evidence_policy import apply_evidence_policy


def detector(
    detector_id: str,
    ai_score: float,
    label: str | None = None,
    *,
    status: str = "ok",
    error: dict[str, Any] | None = None,
    duplicate_of: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "detector_result_v2",
        "detector_id": detector_id,
        "detector_name": detector_id,
        "detector_version": "test",
        "model_version": "test",
        "role": "primary" if detector_id == "smogy" else "secondary",
        "status": status,
        "ai_score": ai_score,
        "real_score": round(1.0 - ai_score, 4),
        "raw_score": ai_score,
        "threshold": 0.5,
        "threshold_profile": "default",
        "predicted_label": label or ("ai" if ai_score >= 0.5 else "real"),
        "confidence": 0.8,
        "latency_ms": 1.0,
        "device": "cpu",
        "input": {"image_hash": None, "width": 1, "height": 1, "format": "jpg", "mode": "RGB"},
        "error": error or {"type": None, "message": None, "recoverable": True},
        "debug": {"raw_output": {}, "notes": []},
        "duplicate_of": duplicate_of,
    }


def provenance_ai() -> dict[str, Any]:
    return {
        "verified": {
            "c2pa_readable": True,
            "c2pa_valid": True,
            "openai_provenance_detected": True,
            "c2pa_generator": "OpenAI gpt-image",
        },
        "diagnostics": {"c2pa_probe_status": "parsed"},
    }


def test_smogy_high_only_can_classify_ai_but_not_high_risk() -> None:
    result = apply_evidence_policy([detector("smogy", 0.92)])

    assert result["final_label"] == "likely_ai"
    assert result["risk_level"] == "medium"
    assert result["recommendation"]["action"] == "manual_review"


def test_ateeqq_high_only_never_ai() -> None:
    result = apply_evidence_policy([detector("ateeqq", 0.94)])

    assert not (result["final_label"] == "likely_ai" and result["risk_level"] == "high")
    assert result["final_label"] in {"uncertain", "needs_review"}


def test_missing_metadata_never_ai() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.1), detector("legacy", 0.12)],
        metadata_result={"missing_exif": True, "missing_xmp": True},
        policy_profile="strict",
    )

    assert result["final_label"] != "likely_ai"
    assert result["final_label"] in {"likely_real", "uncertain"}


def test_smogy_high_plus_metadata_generator_trace() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.93)],
        metadata_result={"software": "Stable Diffusion"},
    )

    assert result["final_label"] == "likely_ai"
    assert result["risk_level"] == "high"


def test_provenance_ai_declared_overrides() -> None:
    result = apply_evidence_policy([detector("smogy", 0.1)], provenance_result=provenance_ai())

    assert result["final_label"] == "likely_ai"
    assert result["risk_level"] == "high"
    assert any(card["type"] == "provenance" and card["status"] == "supports_ai" for card in result["evidence_cards"])


def test_legacy_real_like_does_not_override_smogy_high() -> None:
    result = apply_evidence_policy([detector("smogy", 0.94), detector("legacy", 0.08, "real")])

    assert result["final_label"] == "likely_ai"
    assert result["recommendation"]["action"] == "manual_review"
    assert "Primary detector score" in result["decision_reason"]


def test_adapter_error_to_review() -> None:
    result = apply_evidence_policy(
        [
            detector(
                "smogy",
                0.0,
                "error",
                status="error",
                error={"type": "RuntimeError", "message": "adapter failed", "recoverable": True},
            )
        ],
        policy_profile="strict",
    )

    assert result["final_label"] in {"needs_review", "uncertain"}
    assert any(card["status"] == "error" for card in result["evidence_cards"])


def test_disabled_detector_does_not_force_review() -> None:
    result = apply_evidence_policy(
        [
            detector("smogy", 0.1),
            detector(
                "dima806",
                0.0,
                "disabled",
                status="disabled",
                error={"type": None, "message": None, "recoverable": True},
            ),
        ],
        policy_profile="strict",
    )

    assert result["final_label"] == "likely_real"
    assert result["debug_evidence"]["detector_groups"]["errors"] == []


def test_auxiliary_error_does_not_override_valid_primary_evidence() -> None:
    result = apply_evidence_policy(
        [
            detector("smogy", 0.1, "real"),
            detector(
                "dima806",
                0.0,
                "error",
                status="error",
                error={"type": "RuntimeError", "message": "optional failed", "recoverable": True},
            ),
        ],
        policy_profile="strict",
    )

    assert result["final_label"] == "likely_real"
    assert result["debug_evidence"]["detector_groups"]["auxiliary_errors"] == ["dima806"]


def test_no_active_primary_detector_blocks_low_risk_real() -> None:
    result = apply_evidence_policy([detector("legacy", 0.1, "real")])

    assert result["final_label"] == "needs_review"
    assert result["risk_level"] == "unknown"
    assert result["confidence"] <= 0.3
    assert "Primary AI detector unavailable" in result["decision_reason"]


def test_all_detectors_low_no_ai_trace() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.1), detector("legacy", 0.2), detector("dima806", 0.15)],
        policy_profile="strict",
    )

    assert result["final_label"] == "likely_real"
    assert result["risk_level"] == "low"


def test_legacy_ai_label_does_not_create_policy_conflict() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.12, "real"), detector("ateeqq", 0.01, "real"), detector("legacy", 0.24, "ai")],
        policy_profile="strict_safe_plus",
    )

    assert result["final_label"] == "likely_real"
    assert result["debug_evidence"]["detector_groups"]["conflicts"] == []
    assert "legacy" not in result["debug_evidence"]["detector_groups"]["voting_ai_like"]


def test_high_recall_profile_promotes_review_band_ai_without_changing_strict_default() -> None:
    strict = apply_evidence_policy([detector("smogy", 0.81)], policy_profile="strict_safe_plus")
    high_recall = apply_evidence_policy([detector("smogy", 0.81)], policy_profile="high_recall_review")

    assert strict["final_label"] == "needs_review"
    assert strict["primary_detector_thresholds"]["ai_threshold"] == 0.85
    assert high_recall["final_label"] == "likely_ai"
    assert high_recall["review_status"] == "pending_review"
    assert high_recall["recommendation"]["action"] == "manual_review"
    assert high_recall["primary_detector_thresholds"]["ai_threshold"] == 0.8


def test_mirage_low_fp_profile_routes_primary_secondary_conflict_to_review() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.98, "ai"), detector("ateeqq", 0.01, "real")],
        policy_profile="strict_safe_plus_mirage_low_fp",
    )

    assert result["final_label"] == "needs_review"
    assert result["review_status"] == "pending_review"
    assert result["debug_evidence"]["detector_groups"]["voting_real_like"] == ["ateeqq"]
    assert "Route to review instead of hard AI" in result["decision_reason"]


def test_mirage_low_fp_profile_keeps_dual_high_ai_as_ai() -> None:
    result = apply_evidence_policy(
        [detector("smogy", 0.98, "ai"), detector("ateeqq", 0.97, "ai")],
        policy_profile="strict_safe_plus_mirage_low_fp",
    )

    assert result["final_label"] == "likely_ai"
    assert result["review_status"] == "pending_review"
