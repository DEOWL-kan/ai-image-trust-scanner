from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import main as api_main
from app.services import dashboard_summary


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _single_history(
    *,
    created_at: str,
    filename: str,
    final_label: str,
    risk_level: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "history_type": "single",
        "api_version": "v1",
        "created_at": created_at,
        "request": {
            "mode": "single",
            "input_count": 1,
            "inputs": [{"filename": filename, "source": "upload"}],
        },
        "response": {
            "success": True,
            "data": {
                "filename": filename,
                "final_label": final_label,
                "risk_level": risk_level,
                "confidence": confidence,
                "user_facing_summary": f"Summary for {filename}",
                "recommendation": {"message": "Review when needed."},
            },
            "error": None,
        },
    }


def _batch_history() -> dict[str, Any]:
    return {
        "history_type": "batch",
        "api_version": "v1",
        "created_at": "2026-05-02T10:03:00+08:00",
        "request": {
            "mode": "batch",
            "input_count": 3,
            "inputs": [],
        },
        "response": {
            "api_version": "v1",
            "mode": "batch",
            "batch_id": "batch_20260502_100300_mock",
            "created_at": "2026-05-02T10:03:00+08:00",
            "total": 3,
            "succeeded": 2,
            "failed": 1,
            "results": [
                {
                    "input": {"filename": "uncertain.jpg", "source": "upload", "index": 0},
                    "status": "success",
                    "result": {
                        "filename": "uncertain.jpg",
                        "final_label": "uncertain",
                        "risk_level": "medium",
                        "confidence": 0.5,
                        "user_facing_summary": "Needs review.",
                        "recommendation": "Review manually.",
                    },
                },
                {
                    "input": {"filename": "low_conf_ai.jpg", "source": "upload", "index": 1},
                    "status": "success",
                    "result": {
                        "filename": "low_conf_ai.jpg",
                        "final_label": "ai_generated",
                        "risk_level": "high",
                        "confidence": 0.6,
                        "user_facing_summary": "AI-like signals found.",
                        "recommendation": {"message": "Use caution."},
                    },
                },
                {
                    "input": {"filename": "missing.jpg", "source": "upload", "index": 2},
                    "status": "failed",
                    "error": {"type": "FileNotFoundError", "message": "missing"},
                },
            ],
            "errors": [],
        },
    }


def _mock_history_dir(tmp_path: Path) -> Path:
    history_dir = tmp_path / "api_history"
    history_dir.mkdir()
    _write_json(
        history_dir / "single_1.json",
        _single_history(
            created_at="2026-05-02T10:01:00+08:00",
            filename="ai.jpg",
            final_label="ai",
            risk_level="high",
            confidence=0.8,
        ),
    )
    _write_json(
        history_dir / "single_2.json",
        _single_history(
            created_at="2026-05-02T10:02:00+08:00",
            filename="real.jpg",
            final_label="real_photo",
            risk_level="low",
            confidence=0.9,
        ),
    )
    _write_json(history_dir / "batch_1.json", _batch_history())
    return history_dir


def test_dashboard_summary_empty_history_data(monkeypatch: Any, tmp_path: Path) -> None:
    empty_history = tmp_path / "empty_history"
    monkeypatch.setattr(dashboard_summary, "DEFAULT_HISTORY_DIR", empty_history)

    payload = api_main.dashboard_summary(limit_recent=10, include_debug=False)

    assert payload["status"] == "ok"
    assert payload["summary"]["total_detections"] == 0
    assert payload["summary"]["total_images_processed"] == 0
    assert payload["recent_results"] == []


def test_dashboard_summary_mock_history_statistics(tmp_path: Path) -> None:
    payload = dashboard_summary.build_dashboard_payload(
        history_dir=_mock_history_dir(tmp_path),
        limit_recent=2,
        include_debug=True,
    )
    summary = payload["summary"]

    assert summary["total_detections"] == 3
    assert summary["single_detection_count"] == 2
    assert summary["batch_detection_count"] == 1
    assert summary["total_images_processed"] == 4
    assert summary["final_label_distribution"] == {
        "ai_generated": 2,
        "real": 1,
        "uncertain": 1,
    }
    assert summary["risk_level_distribution"] == {
        "low": 1,
        "medium": 1,
        "high": 2,
        "unknown": 0,
    }
    assert summary["decision_quality"]["average_confidence"] == 0.7
    assert len(payload["recent_results"]) == 2
    assert payload["debug"]["result_files_loaded"] == 3


def test_dashboard_recent_results_filters(tmp_path: Path) -> None:
    history_dir = _mock_history_dir(tmp_path)

    uncertain = dashboard_summary.build_recent_results_payload(
        history_dir=history_dir,
        final_label="uncertain",
    )
    high_risk = dashboard_summary.build_recent_results_payload(
        history_dir=history_dir,
        risk_level="high",
    )

    assert uncertain["count"] == 1
    assert uncertain["results"][0]["filename"] == "uncertain.jpg"
    assert high_risk["count"] == 2
    assert all(item["risk_level"] == "high" for item in high_risk["results"])


def test_dashboard_chart_data_contract(tmp_path: Path) -> None:
    payload = dashboard_summary.build_chart_data_payload(history_dir=_mock_history_dir(tmp_path))
    charts = payload["charts"]

    assert payload["status"] == "ok"
    assert "label_distribution" in charts
    assert "risk_distribution" in charts
    assert "confidence_distribution" in charts
    assert "daily_detection_trend" in charts
    assert charts["label_distribution"] == [
        {"label": "AI Generated", "value": 2},
        {"label": "Real", "value": 1},
        {"label": "Uncertain", "value": 1},
    ]
