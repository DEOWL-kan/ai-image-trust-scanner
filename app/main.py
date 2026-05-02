from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.schemas import DetectionResponse, HealthResponse
from app.services.detection_service import DetectionServiceError, detect_image_for_api


API_VERSION = "0.1.0"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = PROJECT_ROOT / ".tmp" / "api_uploads"

app = FastAPI(title="AI Image Trust Scanner API", version=API_VERSION)


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_error_payload(code, message))


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "uploaded_image").name
    return name or "uploaded_image"


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": API_VERSION,
    }


@app.post("/api/v1/detect", response_model=DetectionResponse)
async def detect(file: UploadFile = File(...)) -> dict[str, object] | JSONResponse:
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return _json_error(
            400,
            "INVALID_FILE_TYPE",
            "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
        )

    contents = await file.read()
    if not contents:
        return _json_error(400, "EMPTY_FILE", "Uploaded file is empty.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        temp_path.write_bytes(contents)
        data = detect_image_for_api(str(temp_path), filename=filename)
        return {
            "success": True,
            "data": data,
            "error": None,
        }
    except DetectionServiceError as exc:
        return _json_error(500, "DETECTION_FAILED", str(exc))
    except Exception:
        return _json_error(
            500,
            "INTERNAL_ERROR",
            "An unexpected error occurred while processing the image.",
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
