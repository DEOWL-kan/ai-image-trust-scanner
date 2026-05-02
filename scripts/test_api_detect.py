from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1/detect"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def find_default_image() -> Path:
    image_root = PROJECT_ROOT / "data" / "test_images"
    for path in image_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return path
    raise FileNotFoundError("No jpg, jpeg, png, or webp test image found under data/test_images.")


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


def post_image(api_url: str, image_path: Path) -> dict[str, Any]:
    boundary = "----day19-api-test-boundary"
    body, content_type = build_multipart_body(image_path, boundary)
    request = urllib.request.Request(
        api_url,
        data=body,
        headers={"Content-Type": content_type, "Content-Length": str(len(body))},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
    return json.loads(payload)


def validate_response(payload: dict[str, Any]) -> None:
    assert "success" in payload
    assert "data" in payload
    assert "error" in payload
    assert payload["success"] is True, payload
    data = payload["data"]
    assert isinstance(data, dict), payload
    for key in ("final_label", "confidence", "risk_level"):
        assert key in data, f"Missing data.{key}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the Day19 detection API.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--image", type=Path, help="Image to upload. Defaults to first data/test_images image.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = args.image or find_default_image()
    if not image_path.is_absolute():
        image_path = PROJECT_ROOT / image_path

    payload = post_image(args.api_url, image_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    validate_response(payload)
    print("Day19 API smoke test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Day19 API smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
