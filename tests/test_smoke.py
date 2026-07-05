from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def test_app_imports_and_health_endpoint() -> None:
    from app import main as api_main

    assert api_main.app.title == "AI Image Trust Scanner API"
    assert asyncio.run(api_main.health()) == {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": "0.1.0",
        "api": "ready",
    }


def test_dashboard_static_files_are_served() -> None:
    from app.main import app

    client = TestClient(app)
    response = client.get("/dashboard-ui/index.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "app.js" in response.text


def test_lightweight_single_image_scan_uses_stub_default(monkeypatch: Any, tmp_path: Path) -> None:
    from app.main import app
    from app.services import report_store
    from PIL import Image

    monkeypatch.delenv("DETECTOR_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("DETECTOR_WARMUP_ON_STARTUP", "false")
    monkeypatch.setattr(report_store, "REPORT_DB_PATH", tmp_path / "reports.sqlite3")
    monkeypatch.setattr(report_store, "HTML_REPORT_DIR", tmp_path / "html_reports")
    report_store.init_db(report_store.REPORT_DB_PATH)
    image_path = tmp_path / "smoke.png"
    Image.new("RGB", (8, 8), color=(128, 128, 128)).save(image_path, format="PNG")

    client = TestClient(app)
    with image_path.open("rb") as handle:
        response = client.post(
            "/api/v1/detect?save_history=false",
            files={"file": ("example_real_fp.png", handle, "image/png")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["final_label"] in {"ai", "real", "uncertain", "needs_review"}
    assert payload["data"]["detector_summary"]["detector_runtime_mode"] == "stub"


def test_report_store_initializes_sqlite(tmp_path: Path) -> None:
    from app.services import report_store

    db_path = tmp_path / "reports.sqlite3"
    report_store.init_db(db_path)

    assert db_path.exists()
    assert report_store.list_reports(db_path=db_path) == []
