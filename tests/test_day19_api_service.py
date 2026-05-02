from __future__ import annotations

import asyncio
import json
from io import BytesIO

from fastapi import UploadFile

from app.main import detect, health


def test_health_endpoint_returns_service_status() -> None:
    assert health() == {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": "0.1.0",
    }


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
