from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.detectors.model_adapter_v2 import DetectorAdapter, image_input_from_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _assert_schema_shape(payload: dict[str, Any]) -> None:
    schema = json.loads((PROJECT_ROOT / "schemas" / "detector_result_schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert required.issubset(payload.keys())
    assert payload["schema_version"] == "detector_result_v2"
    assert 0.0 <= payload["ai_score"] <= 1.0
    assert 0.0 <= payload["real_score"] <= 1.0
    assert 0.0 <= payload["raw_score"] <= 1.0
    assert 0.0 <= payload["threshold"] <= 1.0
    assert payload["predicted_label"] in {"ai", "real", "uncertain", "error", "skipped"}
    assert payload["status"] in {"ok", "skipped", "error", "disabled"}
    assert payload["latency_ms"] >= 0
    assert set(payload["input"].keys()) == {"image_hash", "width", "height", "format", "mode"}
    assert set(payload["error"].keys()) == {"type", "message", "recoverable"}
    assert set(payload["debug"].keys()) == {"raw_output", "notes"}


def test_detector_result_schema_file_covers_required_contract() -> None:
    schema = json.loads((PROJECT_ROOT / "schemas" / "detector_result_schema.json").read_text(encoding="utf-8"))

    assert schema["properties"]["ai_score"]["maximum"] == 1
    assert schema["properties"]["threshold"]["minimum"] == 0
    assert "latency_ms" in schema["required"]
    assert "threshold" in schema["required"]


def test_detector_adapter_output_matches_detector_result_schema() -> None:
    adapter = DetectorAdapter(
        detector_id="smogy",
        detector_name="SMOGY AI Images Detector",
        role="primary",
        threshold=0.5,
        predictor=lambda _: {"ai_score": 0.82, "raw_score": 0.82, "predicted_label": "ai"},
    )

    result = adapter.predict("sample.jpg", context={"input": image_input_from_payload(image_hash="sha256")}).to_dict()

    _assert_schema_shape(result)
    assert result["detector_id"] == "smogy"
    assert result["confidence"] != result["ai_score"]
    assert "confidence_derived_from_threshold_distance" in result["debug"]["notes"]
