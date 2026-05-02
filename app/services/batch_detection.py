from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.detection_service import detect_image_for_api
from app.services.history_store import API_CONTRACT_VERSION, new_history_id, now_iso


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class BatchDetectionInput:
    index: int
    filename: str
    source: str
    image_path: str | None = None
    error: dict[str, Any] | None = None


def _input_payload(item: BatchDetectionInput) -> dict[str, Any]:
    return {
        "filename": item.filename,
        "source": item.source,
        "index": item.index,
    }


def _failure(item: BatchDetectionInput, exc: Exception | None = None) -> dict[str, Any]:
    if item.error:
        error = item.error
    else:
        error = {
            "type": type(exc).__name__ if exc else "DetectionError",
            "message": str(exc or "Image detection failed."),
            "recoverable": True,
        }
    return {
        "input": _input_payload(item),
        "status": "failed",
        "error": error,
    }


def build_path_inputs(image_paths: list[str]) -> list[BatchDetectionInput]:
    inputs: list[BatchDetectionInput] = []
    for index, raw_path in enumerate(image_paths):
        path_text = str(raw_path or "").strip()
        path = Path(path_text)
        filename = path.name or f"image_{index}"
        error: dict[str, Any] | None = None

        if not path_text:
            error = {
                "type": "ValueError",
                "message": "Image path is empty.",
                "recoverable": True,
            }
        elif path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            error = {
                "type": "ValueError",
                "message": "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
                "recoverable": True,
            }
        elif not path.exists():
            error = {
                "type": "FileNotFoundError",
                "message": f"Image file not found: {path_text}",
                "recoverable": True,
            }

        inputs.append(
            BatchDetectionInput(
                index=index,
                filename=filename,
                source=path_text,
                image_path=path_text if error is None else None,
                error=error,
            )
        )
    return inputs


def run_batch_detection(inputs: list[BatchDetectionInput]) -> dict[str, Any]:
    batch_id = new_history_id("batch")
    created_at = now_iso()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    succeeded = 0

    for item in sorted(inputs, key=lambda value: value.index):
        if item.error:
            failed = _failure(item)
            results.append(failed)
            errors.append(failed)
            continue

        try:
            result = detect_image_for_api(str(item.image_path), filename=item.filename)
            results.append(
                {
                    "input": _input_payload(item),
                    "status": "success",
                    "result": result,
                }
            )
            succeeded += 1
        except Exception as exc:
            failed = _failure(item, exc)
            results.append(failed)
            errors.append(failed)

    total = len(inputs)
    return {
        "api_version": API_CONTRACT_VERSION,
        "mode": "batch",
        "batch_id": batch_id,
        "created_at": created_at,
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "results": results,
        "errors": errors,
    }
