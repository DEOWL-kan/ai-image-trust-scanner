from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from uuid import uuid4


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

class SmokeFailure(Exception):
    pass


def step(name: str) -> None:
    print(f"[Day30] {name} ...", flush=True)


def request_json(path: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Accept": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {path} failed: HTTP {exc.code} {detail}") from exc
    except Exception as exc:
        raise SmokeFailure(f"{method} {path} failed: {exc}") from exc


def request_text(path: str) -> str:
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"GET {path} failed: HTTP {exc.code} {detail}") from exc
    except Exception as exc:
        raise SmokeFailure(f"GET {path} failed: {exc}") from exc


def multipart_upload(path: Path) -> dict:
    boundary = f"----day30-{uuid4().hex}"
    file_bytes = path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return request_json(
        "/api/v1/detect",
        method="POST",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    width = height = 2
    raw_rows = b"".join([b"\x00" + b"\xff\xff\xff" * width for _ in range(height)])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw_rows)) + chunk(b"IEND", b"")


def make_sample_image() -> Path:
    sample_candidates = [
        Path("backend/samples/sample.png"),
        Path("examples/sample.png"),
        Path("data/sample.png"),
    ]
    for candidate in sample_candidates:
        if candidate.exists():
            return candidate
    tmp_dir = Path(tempfile.gettempdir()) / "ai_image_trust_scanner_day30"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / "day30_smoke_sample.png"
    path.write_bytes(tiny_png())
    return path


def main() -> int:
    try:
        step("health endpoint")
        health = request_json("/api/health")
        assert_true(health.get("api_status") == "ok", f"Unexpected health payload: {health}")

        step("single image detection")
        detect_payload = multipart_upload(make_sample_image())
        assert_true(detect_payload.get("success") is True, f"Detection did not succeed: {detect_payload}")
        data = detect_payload.get("data") or {}
        report_id = data.get("report_id")
        assert_true(bool(report_id), f"Missing report_id in detection response: {detect_payload}")

        step("reports list contains report_id")
        reports = request_json("/api/v1/reports?limit=100")
        items = reports.get("items") or []
        assert_true(any(item.get("report_id") == report_id or item.get("id") == report_id for item in items), f"Report {report_id} not found in list")

        step("report detail and version fields")
        detail = request_json(f"/api/v1/reports/{urllib.parse.quote(str(report_id))}")
        for field in ("report_schema_version", "detector_version", "model_version"):
            assert_true(bool(detail.get(field)), f"Missing {field} in detail payload")

        step("review_status PATCH persists")
        patch_payload = json.dumps(
            {
                "review_status": "confirmed_ai",
                "review_note": "day30 smoke test",
                "reviewed_by": "day30_smoke_test",
            }
        ).encode("utf-8")
        request_json(
            f"/api/v1/reports/{urllib.parse.quote(str(report_id))}/review",
            method="PATCH",
            body=patch_payload,
            headers={"Content-Type": "application/json"},
        )
        detail_after_patch = request_json(f"/api/v1/reports/{urllib.parse.quote(str(report_id))}")
        assert_true(detail_after_patch.get("review_status") == "confirmed_ai", "review_status was not persisted")

        step("HTML report endpoint")
        html = request_text(f"/api/v1/reports/{urllib.parse.quote(str(report_id))}/html")
        assert_true("<html" in html.lower() and "</html>" in html.lower(), "HTML report does not contain a basic HTML document")

        step("export endpoint")
        export = request_json("/api/v1/reports/export?format=json&limit=100")
        assert_true(isinstance(export.get("items"), list), "Export JSON did not return items")

        print("[Day30] PASS")
        return 0
    except SmokeFailure as exc:
        print(f"[Day30] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
