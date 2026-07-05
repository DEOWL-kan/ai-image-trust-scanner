from __future__ import annotations

import asyncio
import json
import time
from io import BytesIO

from fastapi import UploadFile
from fastapi.testclient import TestClient

from app import main as api_main
from app.main import app, detect, health
from app.services.detection_service import _api_label_from_policy


def test_health_endpoint_returns_service_status() -> None:
    # health() is async now (so it can't be blocked by a slow scan in the
    # threadpool); drive it through asyncio.run() for the unit test.
    assert asyncio.run(health()) == {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": "0.1.0",
        "api": "ready",
    }


def test_health_route_returns_ready_payload() -> None:
    routes = {route.path: route for route in app.routes}

    assert "/health" in routes
    assert "GET" in routes["/health"].methods


def test_detect_route_exists_and_expects_multipart_file() -> None:
    routes = {route.path: route for route in app.routes}

    assert "/api/v1/detect" in routes
    assert "POST" in routes["/api/v1/detect"].methods


def test_local_frontend_dev_origin_is_allowed_by_cors() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"


def test_error_gallery_legacy_route_redirects_to_static_mount() -> None:
    client = TestClient(app, follow_redirects=False)
    response = client.get("/dashboard/errors")

    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard-ui/errors.html"


def test_policy_profiles_route_exposes_product_default() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/policy/profiles")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "policy_profiles_v1"
    assert payload["product_default_policy_profile"] == "strict_safe_plus"
    profiles = {item["name"]: item for item in payload["profiles"]}
    profile_names = set(profiles)
    assert {"strict_safe_plus", "high_recall_review"}.issubset(profile_names)
    assert profiles["strict_safe_plus"]["thresholds"]["ai_threshold"] == 0.85
    assert profiles["high_recall_review"]["thresholds"]["ai_threshold"] == 0.8
    assert profiles["strict_safe_plus_lora_v2"]["thresholds"]["ai_threshold"] == 0.95
    assert profiles["high_recall_review"]["review_burden"] == "high"


def test_policy_review_label_maps_to_schema_safe_api_label() -> None:
    assert _api_label_from_policy("needs_review") == "uncertain"
    assert _api_label_from_policy("review_needed") == "uncertain"


def test_optional_api_key_auth_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MINERVA_API_KEY", raising=False)
    monkeypatch.delenv("MINERVA_API_KEYS", raising=False)
    client = TestClient(app)

    response = client.get("/api/v1/policy/profiles")

    assert response.status_code == 200


def test_optional_api_key_auth_protects_api_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("MINERVA_API_KEY", "secret-local-key")
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/dashboard-ui/index.html").status_code in {200, 404}
    missing = client.get("/api/v1/policy/profiles")
    wrong = client.get("/api/v1/policy/profiles", headers={"X-API-Key": "wrong"})
    header_ok = client.get("/api/v1/policy/profiles", headers={"X-API-Key": "secret-local-key"})
    query_ok = client.get("/api/v1/policy/profiles?api_key=secret-local-key")

    assert missing.status_code == 401
    assert missing.json()["code"] == "API_KEY_REQUIRED"
    assert wrong.status_code == 401
    assert header_ok.status_code == 200
    assert query_ok.status_code == 200


def test_batch_json_forwards_policy_profile(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_batch_detection(inputs, policy_profile=None):
        captured["policy_profile"] = policy_profile
        captured["input_count"] = len(inputs)
        return {
            "api_version": "v1",
            "mode": "batch",
            "batch_id": "batch_policy_test",
            "created_at": "2026-05-30T00:00:00+08:00",
            "total": len(inputs),
            "succeeded": 0,
            "failed": len(inputs),
            "results": [],
            "errors": [],
        }

    monkeypatch.setattr(api_main, "run_batch_detection", fake_run_batch_detection)
    client = TestClient(app)
    response = client.post(
        "/api/v1/detect/batch?save_history=false",
        json={
            "image_paths": ["missing.jpg"],
            "save_history": False,
            "policy_profile": "high_recall_review",
        },
    )

    assert response.status_code == 200
    assert captured == {"policy_profile": "high_recall_review", "input_count": 1}


def test_batch_job_json_submission_reaches_terminal_state() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/detect/batch/jobs?save_history=false",
        json={"image_paths": ["missing.jpg"], "save_history": False},
    )

    assert response.status_code == 202
    job = response.json()
    assert job["status"] in {"queued", "running", "completed"}
    job_id = job["job_id"]

    deadline = time.time() + 5
    status = job
    while time.time() < deadline:
        status = client.get(f"/api/v1/detect/batch/jobs/{job_id}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert status["status"] == "completed"
    assert status["processed"] == 1
    result = client.get(f"/api/v1/detect/batch/jobs/{job_id}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["mode"] == "batch"
    assert payload["total"] == 1
    assert payload["failed"] == 1


def test_detect_rejects_unsupported_file_type() -> None:
    upload = UploadFile(filename="sample.txt", file=BytesIO(b"not an image"))
    response = asyncio.run(detect(upload))

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "success": False,
        "data": None,
        "error": {
            "code": "INVALID_FILE_TYPE",
            "message": "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
        },
    }


def test_detect_rejects_empty_supported_file() -> None:
    upload = UploadFile(filename="empty.jpg", file=BytesIO(b""))
    response = asyncio.run(detect(upload))

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "success": False,
        "data": None,
        "error": {
            "code": "EMPTY_FILE",
            "message": "Uploaded file is empty.",
        },
    }
