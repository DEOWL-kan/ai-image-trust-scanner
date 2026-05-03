from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from app import main as api_main
from app.services import error_gallery


def _call_errors(**overrides: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "type_": "all",
        "scenario": None,
        "format": None,
        "difficulty": None,
        "resolution_bucket": None,
        "source_folder": None,
        "min_confidence": None,
        "max_confidence": None,
        "sort": "confidence_desc",
        "limit": 50,
        "offset": 0,
    }
    params.update(overrides)
    return api_main.errors(**params)


def test_error_type_classification_rules() -> None:
    assert error_gallery.classify_error_type("real", "ai") == "FP"
    assert error_gallery.classify_error_type("ai", "real") == "FN"
    assert error_gallery.classify_error_type("ai", "uncertain") == "UNCERTAIN"
    assert error_gallery.classify_error_type("ai", "ai") == "TP"
    assert error_gallery.classify_error_type("real", "real") == "TN"
    assert error_gallery.classify_error_type("real", "ai", {"is_uncertain": True}) == "UNCERTAIN"


def test_missing_fields_do_not_crash() -> None:
    item, missing = error_gallery._normalize_item({}, 0, "test_run")

    assert item["filename"] == "sample_0"
    assert item["true_label"] == "unknown"
    assert item["final_label"] == "unknown"
    assert item["error_type"] == "UNCERTAIN"
    assert "file_path" in missing
    assert "confidence" in missing


def test_errors_summary_endpoint_returns_counts() -> None:
    payload = api_main.errors_summary()

    assert payload["status"] == "ok"
    assert payload["total_samples"] > 0
    assert payload["fp_count"] >= 0
    assert "by_scenario" in payload


def test_errors_filter_fp_endpoint() -> None:
    payload = _call_errors(type_="fp", limit=20)

    assert payload["limit"] == 20
    assert payload["filters"]["type"] == "fp"
    assert all(item["error_type"] == "FP" for item in payload["items"])


def test_image_url_points_to_accessible_media() -> None:
    item = _call_errors(limit=1)["items"][0]

    assert item["image_url"].startswith("/media/")
    media_routes = [route for route in api_main.app.routes if getattr(route, "path", None) == "/media"]
    assert media_routes
    relative = unquote(item["image_url"].removeprefix("/media/"))
    media_path = (error_gallery.DATA_ROOT / relative).resolve()
    assert error_gallery.is_safe_data_image_path(media_path)
    assert media_path.exists()


def test_review_note_writes_json(monkeypatch: Any, tmp_path: Path) -> None:
    review_path = tmp_path / "day24_error_review_notes.json"
    monkeypatch.setattr(error_gallery, "REVIEW_NOTES_PATH", review_path)

    item = _call_errors(limit=1)["items"][0]
    review = error_gallery.save_review_note(
        item["id"],
        {
            "reviewed": True,
            "manual_tag": "format_bias",
            "reviewer_note": "Looks tied to JPEG format handling.",
            "reviewer": "local",
        },
    )

    assert review["reviewed"] is True
    assert review_path.exists()
    saved = error_gallery.load_review_notes(review_path)
    assert saved["reviews"][item["id"]]["manual_tag"] == "format_bias"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_get(base_url: str, path: str) -> tuple[int, str, bytes]:
    request = urllib.request.Request(f"{base_url}{path}", headers={"Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        return int(response.status), response.headers.get("content-type", ""), body


def _http_post_json(base_url: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return int(response.status), json.loads(response.read().decode("utf-8"))


def test_day24_http_routes_assets_and_review() -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    reviewed_item_id: str | None = None
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=error_gallery.PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, _ = _http_get(base_url, "/api/v1/errors/summary")
                if status == 200:
                    break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.25)
        else:
            raise AssertionError("uvicorn did not become ready for Day24 HTTP route tests")

        for path in ("/dashboard/errors", "/errors"):
            status, content_type, body = _http_get(base_url, path)
            html = body.decode("utf-8")
            assert status == 200
            assert "text/html" in content_type
            assert "/dashboard-assets/styles.css" in html
            assert "/dashboard-assets/error-gallery.js" in html

        for path in ("/dashboard-assets/styles.css", "/dashboard-assets/error-gallery.js"):
            status, _, body = _http_get(base_url, path)
            assert status == 200
            assert body

        for path in (
            "/api/v1/errors/summary",
            "/api/v1/errors?type=all&limit=24",
            "/api/v1/errors?type=fp&limit=24",
            "/api/v1/errors?type=fn&limit=24",
            "/api/v1/errors?type=uncertain&limit=24",
            "/api/v1/errors?type=fp&limit=20",
        ):
            status, content_type, body = _http_get(base_url, path)
            assert status == 200
            assert "application/json" in content_type
            assert json.loads(body.decode("utf-8"))

        _, _, list_body = _http_get(base_url, "/api/v1/errors?type=all&limit=1")
        item = json.loads(list_body.decode("utf-8"))["items"][0]
        reviewed_item_id = item["id"]
        status, review_body = _http_post_json(
            base_url,
            f"/api/v1/errors/{item['id']}/review",
            {
                "reviewed": True,
                "manual_tag": "unknown",
                "reviewer_note": "HTTP test review.",
                "reviewer": "local",
            },
        )
        assert status == 200
        assert review_body["review"]["reviewed"] is True
        assert error_gallery.REVIEW_NOTES_PATH.exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        if reviewed_item_id and error_gallery.REVIEW_NOTES_PATH.exists():
            notes = error_gallery.load_review_notes(error_gallery.REVIEW_NOTES_PATH)
            if reviewed_item_id in notes.get("reviews", {}):
                notes["reviews"].pop(reviewed_item_id, None)
                error_gallery.REVIEW_NOTES_PATH.write_text(
                    json.dumps(notes, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
