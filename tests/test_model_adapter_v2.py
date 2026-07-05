from __future__ import annotations

from app.detectors.model_adapter_v2 import DetectorAdapter, image_input_from_payload


def test_model_adapter_v2_normalizes_scores_and_derives_real_score() -> None:
    adapter = DetectorAdapter(
        detector_id="ateeqq",
        detector_name="Ateeqq AI vs Human Image Detector",
        role="secondary",
        threshold=0.6,
        predictor=lambda _: {"ai_score": 0.2, "raw_score": 0.2},
    )

    result = adapter.predict("sample.jpg", context={"input": image_input_from_payload(width=10, height=8)}).to_dict()

    assert result["ai_score"] == 0.2
    assert result["real_score"] == 0.8
    assert result["predicted_label"] == "real"
    assert result["threshold"] == 0.6
    assert result["latency_ms"] >= 0
    assert "real_score_derived_from_ai_score" in result["debug"]["notes"]


def test_model_adapter_v2_captures_predict_exceptions_without_raising() -> None:
    def boom(_: object) -> dict:
        raise RuntimeError("mock detector failed")

    adapter = DetectorAdapter(
        detector_id="dima806",
        detector_name="dima806 AI vs Real Image Detection",
        role="diagnostic",
        predictor=boom,
    )

    result = adapter.predict("sample.jpg", context={"input": image_input_from_payload()}).to_dict()

    assert result["status"] == "error"
    assert result["predicted_label"] == "error"
    assert result["error"]["type"] == "RuntimeError"
    assert "mock detector failed" in result["error"]["message"]


def test_disabled_adapter_returns_disabled_contract() -> None:
    adapter = DetectorAdapter(
        detector_id="capcheck",
        detector_name="capcheck AI Image Detection",
        role="disabled",
        enabled=False,
        duplicate_of="dima806-ai-vs-real-image-detection",
        reason_disabled="duplicate_disabled",
    )

    result = adapter.predict("sample.jpg", context={"input": image_input_from_payload()}).to_dict()

    assert result["status"] == "disabled"
    assert result["predicted_label"] == "skipped"
    assert result["role"] == "disabled"
    assert "duplicate_disabled" in result["debug"]["notes"]
