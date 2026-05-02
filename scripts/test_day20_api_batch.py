from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
HISTORY_DIR = PROJECT_ROOT / "outputs" / "api_history"


def find_test_images(count: int = 3) -> list[Path]:
    image_root = PROJECT_ROOT / "data" / "test_images"
    images = [
        path
        for path in image_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if len(images) < count:
        raise FileNotFoundError(f"Need at least {count} test images under data/test_images.")
    return images[:count]


def request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}


def build_multipart_body(image_path: Path, boundary: str) -> tuple[bytes, str]:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    file_bytes = image_path.read_bytes()
    chunks = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            'Content-Disposition: form-data; name="file"; '
            f'filename="{image_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def post_single_image(base_url: str, image_path: Path) -> dict[str, Any]:
    boundary = "----day20-single-boundary"
    body, content_type = build_multipart_body(image_path, boundary)
    request = urllib.request.Request(
        f"{base_url}/api/v1/detect",
        data=body,
        headers={"Content-Type": content_type, "Content-Length": str(len(body))},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def latest_batch_history_files() -> set[str]:
    if not HISTORY_DIR.exists():
        return set()
    return {path.name for path in HISTORY_DIR.glob("batch_*.json")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test Day20 batch detection API and history endpoints. Start FastAPI first."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    images = find_test_images(3)
    invalid_path = PROJECT_ROOT / "data" / "test_images" / "missing_day20_image.jpg"

    status, health = request_json(f"{base_url}/health")
    assert status == 200 and health["status"] == "ok", health
    print("Health OK.")

    single = post_single_image(base_url, images[0])
    assert single["success"] is True, single
    assert single["data"]["final_label"] in {"ai", "real", "uncertain"}, single
    print("Single detection OK.")

    before = latest_batch_history_files()
    batch_payload = {
        "image_paths": [str(path) for path in images] + [str(invalid_path)],
        "save_history": True,
    }
    status, batch = request_json(f"{base_url}/detect/batch", method="POST", payload=batch_payload)
    assert status == 200, batch
    assert batch["mode"] == "batch", batch
    assert batch["total"] == 4, batch
    assert batch["succeeded"] == 3, batch
    assert batch["failed"] == 1, batch
    assert [item["input"]["index"] for item in batch["results"]] == [0, 1, 2, 3], batch
    assert batch["results"][3]["status"] == "failed", batch
    print("Batch detection with isolated failure OK.")

    time.sleep(0.1)
    after = latest_batch_history_files()
    created = sorted(after - before)
    history_filename = batch.get("history", {}).get("filename") or (created[-1] if created else None)
    assert history_filename, "No batch history JSON was created."
    print(f"Batch history created: {history_filename}")

    status, history_list = request_json(f"{base_url}/history?limit=20&history_type=all")
    assert status == 200, history_list
    assert any(item["filename"] == history_filename for item in history_list["items"]), history_list
    print("History list OK.")

    quoted_filename = urllib.parse.quote(history_filename)
    status, detail = request_json(f"{base_url}/history/{quoted_filename}")
    assert status == 200, detail
    assert detail["history_type"] == "batch", detail
    assert detail["response"]["batch_id"] == batch["batch_id"], detail
    print("History detail OK.")

    status, traversal = request_json(f"{base_url}/history/%2E%2E%2Frequirements.txt")
    assert status in {400, 404}, traversal
    print("Path traversal rejected.")

    print("Day20 API batch/history smoke test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Day20 API batch/history smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
