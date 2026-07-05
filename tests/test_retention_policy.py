from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.retention import RetentionTarget, build_retention_plan, run_retention_policy


def _touch_old(path: Path, *, days_old: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("local-private-artifact", encoding="utf-8")
    timestamp = time.time() - (days_old * 86400)
    os.utime(path, (timestamp, timestamp))


def test_retention_plan_is_dry_run_by_default(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    old_file = root / "old.jpg"
    fresh_file = root / "fresh.jpg"
    _touch_old(old_file, days_old=10)
    _touch_old(fresh_file, days_old=0)
    target = RetentionTarget(name="uploads", root=root, max_age_days=7, patterns=("*",))

    plan = build_retention_plan(targets=[target])

    assert plan["apply"] is False
    assert plan["totals"]["scanned_files"] == 2
    assert plan["totals"]["would_delete_files"] == 1
    assert plan["targets"][0]["candidates"][0]["relative_path"] == "old.jpg"
    assert old_file.exists()
    assert fresh_file.exists()


def test_retention_apply_deletes_only_expired_files_inside_target(tmp_path: Path) -> None:
    root = tmp_path / "api_reports"
    old_file = root / "old.json"
    fresh_file = root / "fresh.json"
    _touch_old(old_file, days_old=45)
    _touch_old(fresh_file, days_old=1)
    target = RetentionTarget(name="api_reports", root=root, max_age_days=30, patterns=("*.json",))

    result = run_retention_policy(apply=True, targets=[target])

    assert result["apply"] is True
    assert result["totals"]["deleted_files"] == 1
    assert not old_file.exists()
    assert fresh_file.exists()
    assert result["errors"] == []


def test_retention_api_dry_run_and_apply_confirmation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MINERVA_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MINERVA_API_REPORT_DIR", str(tmp_path / "api_reports"))
    monkeypatch.setenv("MINERVA_C2PA_MANIFEST_DIR", str(tmp_path / "c2pa"))
    monkeypatch.setenv("MINERVA_HTML_REPORT_DIR", str(tmp_path / "html"))
    monkeypatch.setenv("MINERVA_RETENTION_UPLOAD_DAYS", "7")
    _touch_old(tmp_path / "uploads" / "old.png", days_old=10)
    client = TestClient(app)

    dry_run = client.get("/api/v1/admin/retention")
    missing_confirm = client.get("/api/v1/admin/retention?apply=true")

    assert dry_run.status_code == 200
    assert dry_run.json()["schema_version"] == "retention_policy_v1"
    assert dry_run.json()["apply"] is False
    assert dry_run.json()["totals"]["would_delete_files"] >= 1
    assert missing_confirm.status_code == 400
    assert (tmp_path / "uploads" / "old.png").exists()
