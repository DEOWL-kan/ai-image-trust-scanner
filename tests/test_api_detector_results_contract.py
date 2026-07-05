from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services import detection_service, report_center, report_store
from app.services.batch_detection import build_path_inputs, run_batch_detection


def _provenance() -> dict[str, Any]:
    return {
        "verified": {
            "c2pa_present": False,
            "c2pa_readable": False,
            "c2pa_valid": None,
            "c2pa_issuer": None,
            "c2pa_generator": None,
            "openai_provenance_detected": False,
            "confidence": "unknown",
        },
        "unverified_markers": {
            "binary_c2pa_marker_found": False,
            "binary_openai_marker_found": False,
            "binary_gpt_image_marker_found": False,
            "marker_confidence": "none",
            "used_for_final_decision": False,
        },
        "diagnostics": {"c2pa_probe_status": "no_manifest"},
        "user_note": "No C2PA metadata was found.",
    }


def _patch_successful_detector(monkeypatch: Any) -> None:
    monkeypatch.setattr(detection_service, "run_pipeline", lambda path, output_dir: {"ok": True, "image_info": {"width": 8, "height": 8, "format": "jpg"}})
    monkeypatch.setattr(
        detection_service,
        "build_frontend_response",
        lambda report, image_meta, include_debug: {
            "data": {
                "image": {"filename": image_meta["filename"]},
                "result": {
                    "final_label": "real_photo",
                    "risk_level": "low",
                    "confidence": 0.91,
                    "decision_reason": [{"code": "baseline", "message": "baseline"}],
                    "recommendation": {"action": "allow", "message": "ok"},
                    "user_facing_summary": "Looks real.",
                    "technical_explanation": {"score": 0.1, "threshold_used": 0.5},
                    "debug_evidence": {"enabled": True, "latency_ms": 1.2},
                },
            }
        },
    )
    monkeypatch.setattr(detection_service, "analyze_c2pa_provenance", lambda *args, **kwargs: _provenance())
    monkeypatch.setattr(
        detection_service,
        "save_report",
        lambda record: {
            **record,
            "report_id": "r_day38",
            "review_status": "unreviewed",
            "report_schema_version": "v1",
            "detector_version": "detector.test",
            "model_version": "model.test",
            "html_report_available": True,
        },
    )
    monkeypatch.setattr(detection_service, "write_audit_event", lambda *args, **kwargs: None)


def test_single_api_returns_detector_results_contract(monkeypatch: Any, tmp_path: Path) -> None:
    _patch_successful_detector(monkeypatch)
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"fake-bytes")

    data = detection_service.detect_image_for_api(str(image_path), filename="sample.jpg")

    assert data["detector_result_schema_version"] == "detector_result_v2"
    assert isinstance(data["detector_results"], list)
    assert data["detector_summary"]["schema_version"] == "detector_result_v2"
    assert data["detector_summary"]["enabled_count"] >= 4
    assert "capcheck" not in {item["detector_id"] for item in data["detector_results"]}
    for item in data["detector_results"]:
        assert "latency_ms" in item
        assert "threshold" in item
    assert "stage_timings" in data["timing"]
    assert "legacy_pipeline" in data["timing"]["stage_timings"]


def test_batch_api_preserves_detector_summary(monkeypatch: Any, tmp_path: Path) -> None:
    _patch_successful_detector(monkeypatch)
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"fake-bytes")

    payload = run_batch_detection(build_path_inputs([str(image_path)]))

    assert payload["succeeded"] == 1
    result = payload["results"][0]["result"]
    assert result["detector_summary"]["schema_version"] == "detector_result_v2"


def test_report_center_reads_legacy_report_without_detector_results(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    legacy = {
        "history_type": "single",
        "created_at": "2026-05-15T00:00:00+00:00",
        "response": {
            "success": True,
            "data": {
                "id": "legacy_1",
                "filename": "old.jpg",
                "final_label": "real",
                "risk_level": "low",
                "confidence": 0.8,
                "decision_reason": [],
                "recommendation": {},
                "user_facing_summary": "old report",
                "technical_explanation": {},
                "debug_evidence": {},
            },
        },
    }
    (history_dir / "legacy.json").write_text(__import__("json").dumps(legacy), encoding="utf-8")

    records = report_center.load_report_records_from_history(history_dir)

    assert records[0]["detector_result_schema_version"] == "legacy_unavailable"
    assert records[0]["detector_results"] == []
    assert records[0]["detector_summary"]["schema_version"] == "legacy_unavailable"


def test_new_report_persistence_keeps_detector_fields(monkeypatch: Any, tmp_path: Path) -> None:
    db_path = tmp_path / "reports.sqlite3"
    monkeypatch.setattr(report_store, "REPORT_DB_PATH", db_path)
    monkeypatch.setattr(report_store, "HTML_REPORT_DIR", tmp_path / "html")
    record = report_store.make_report_record(
        detection_data={
            "filename": "sample.jpg",
            "final_label": "real",
            "risk_level": "low",
            "confidence": 0.8,
            "decision_reason": [],
            "recommendation": {},
            "user_facing_summary": "ok",
            "technical_explanation": {},
            "debug_evidence": {},
            "detector_result_schema_version": "detector_result_v2",
            "detector_results": [{"schema_version": "detector_result_v2", "detector_id": "legacy"}],
            "detector_summary": {"schema_version": "detector_result_v2", "enabled_count": 1},
            "detector_registry_version": "day38_detector_registry_v1",
            "threshold_profile": "default",
            "model_adapter_version": "model_adapter_v2",
        },
        source_type="single",
    )

    saved = report_store.save_report(record)

    assert saved["detector_result_schema_version"] == "detector_result_v2"
    assert saved["detector_results"][0]["detector_id"] == "legacy"
    assert saved["detector_registry_version"] == "day38_detector_registry_v1"
