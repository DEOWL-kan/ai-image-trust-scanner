from __future__ import annotations

from pathlib import Path
from typing import Any

from app import main as api_main
from app.services import report_center, report_store


def _use_temp_store(monkeypatch: Any, tmp_path: Path) -> Path:
    db_path = tmp_path / "data" / "reports.sqlite3"
    monkeypatch.setattr(report_store, "REPORT_DB_PATH", db_path)
    monkeypatch.setattr(report_store, "HTML_REPORT_DIR", tmp_path / "html_reports")
    report_store.init_db(db_path)
    return db_path


def _save_sample_report(filename: str = "ai_sample.jpg", risk_level: str = "high") -> dict[str, Any]:
    record = report_store.make_report_record(
        detection_data={
            "filename": filename,
            "final_label": "ai",
            "risk_level": risk_level,
            "confidence": 0.82,
            "decision_reason": [{"code": "synthetic_texture", "message": "Synthetic texture signals"}],
            "recommendation": {"message": "人工复核后再使用。"},
            "user_facing_summary": "检测到较强 AI 生成风险。",
            "technical_explanation": {"score": 0.82, "threshold_used": 0.7},
            "debug_evidence": {"feature_summary": {"risk_factors": ["synthetic_texture"]}},
        },
        source_type="single",
        file_sha256="abc123",
        report_payload={"full": "payload", "filename": filename},
        export_payload={"filename": filename},
    )
    return report_store.save_report(record)


def test_report_record_create_list_search_filter_sort_and_versions(monkeypatch: Any, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    saved = _save_sample_report()
    _save_sample_report(filename="real_sample.jpg", risk_level="low")

    listed = api_main.reports_list(limit=10, q=None, risk_level=None, final_label=None, review_status=None, source_type=None, date_from=None, date_to=None, sort=None, sort_by="created_at", sort_order="desc", offset=0)
    searched = api_main.reports_list(limit=10, q="synthetic", risk_level=None, final_label=None, review_status=None, source_type=None, date_from=None, date_to=None, sort=None, sort_by="created_at", sort_order="desc", offset=0)
    high_risk = api_main.reports_list(limit=10, q=None, risk_level="high", final_label=None, review_status=None, source_type=None, date_from=None, date_to=None, sort=None, sort_by="created_at", sort_order="desc", offset=0)
    pending = api_main.reports_list(limit=10, q=None, risk_level=None, final_label=None, review_status="pending_review", source_type=None, date_from=None, date_to=None, sort=None, sort_by="created_at", sort_order="desc", offset=0)

    assert listed["total"] == 2
    assert searched["filtered_total"] >= 1
    assert high_risk["items"][0]["risk_level"] == "high"
    assert pending["items"][0]["review_status"] == "pending_review"
    assert saved["report_schema_version"] == "v1"
    assert saved["detector_version"] == "detector.day29"
    assert saved["model_version"] == "lightweight-baseline.no-pretrained"
    assert saved["html_report_available"] is True


def test_report_detail_review_update_and_sqlite_persistence(monkeypatch: Any, tmp_path: Path) -> None:
    db_path = _use_temp_store(monkeypatch, tmp_path)
    saved = _save_sample_report()

    detail = api_main.reports_detail(saved["report_id"])
    assert detail["report_id"] == saved["report_id"]
    assert detail["report_payload_json"]["full"] == "payload"

    updated = report_center.update_review(
        saved["report_id"],
        {
            "review_status": "confirmed_ai",
            "review_note": "人工确认风险成立。",
            "reviewed_by": "local_user",
        },
    )
    assert updated["review_status"] == "confirmed_ai"
    assert updated["review_note"] == "人工确认风险成立。"

    report_store.init_db(db_path)
    persisted = report_store.get_report(saved["report_id"])
    assert persisted is not None
    assert persisted["review_status"] == "confirmed_ai"
    assert persisted["report_schema_version"]
    assert persisted["detector_version"]
    assert persisted["model_version"]


def test_report_export_and_html_path(monkeypatch: Any, tmp_path: Path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    saved = _save_sample_report()

    html_path = report_center.get_html_report_path(saved["report_id"])
    assert html_path.exists()

    payload = report_center.search_reports(q="ai_sample", limit=10)
    csv_text = report_center.export_csv(payload["items"])
    assert "report_schema_version" in csv_text
    assert "detector.day29" in csv_text
