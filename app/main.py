from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    DashboardChartDataResponse,
    DashboardRecentResultsResponse,
    DashboardSummaryResponse,
    DetectionResponse,
    HealthResponse,
)
from app.services.batch_detection import (
    BatchDetectionInput,
    build_path_inputs,
    run_batch_detection,
)
from app.services.detection_service import DetectionServiceError, detect_image_for_api
from app.services.dashboard_summary import (
    build_chart_data_payload,
    build_dashboard_payload,
    build_recent_results_payload,
)
from app.services.error_gallery import (
    DATA_ROOT,
    ErrorItemNotFound,
    build_error_summary,
    get_error_item,
    list_error_items,
    save_review_note,
)
from app.services.error_taxonomy import (
    Day25InputError,
    api_payload as build_error_taxonomy_payload,
    calibrated_api_payload as build_calibrated_error_taxonomy_payload,
)
from app.services.history_store import (
    CorruptHistoryError,
    HistoryNotFoundError,
    InvalidHistoryFilenameError,
    duration_ms,
    list_history,
    new_history_id,
    read_history,
    save_history as write_history,
    started_timer,
)


API_VERSION = "0.1.0"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = PROJECT_ROOT / ".tmp" / "api_uploads"
FRONTEND_DASHBOARD_DIR = PROJECT_ROOT / "frontend" / "dashboard"
ERROR_GALLERY_PAGE = FRONTEND_DASHBOARD_DIR / "errors.html"
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Image Trust Scanner API", version=API_VERSION)
if DATA_ROOT.exists():
    app.mount(
        "/media",
        StaticFiles(directory=DATA_ROOT, html=False, follow_symlink=False),
        name="media",
    )
if FRONTEND_DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard-assets",
        StaticFiles(directory=FRONTEND_DASHBOARD_DIR, html=False),
        name="dashboard-assets",
    )
    app.mount(
        "/dashboard-ui",
        StaticFiles(directory=FRONTEND_DASHBOARD_DIR, html=True),
        name="dashboard-ui",
    )

DASHBOARD_FINAL_LABEL_FILTERS = {"ai_generated", "real", "uncertain"}
DASHBOARD_RISK_LEVEL_FILTERS = {"low", "medium", "high", "unknown"}


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


def _parse_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _single_request(filename: str, source: str) -> dict[str, Any]:
    return {
        "mode": "single",
        "input_count": 1,
        "inputs": [
            {
                "filename": filename,
                "source": source,
            }
        ],
    }


def _history_request_from_batch(inputs: list[BatchDetectionInput]) -> dict[str, Any]:
    return {
        "mode": "batch",
        "input_count": len(inputs),
        "inputs": [
            {
                "filename": item.filename,
                "source": item.source,
                "index": item.index,
            }
            for item in sorted(inputs, key=lambda value: value.index)
        ],
    }


def _save_history_safely(
    *,
    history_type: str,
    response_payload: dict[str, Any],
    request_payload: dict[str, Any],
    started_at: float,
    history_id: str | None = None,
    created_at: str | None = None,
    attach_to_response: bool = True,
) -> None:
    try:
        saved = write_history(
            history_type=history_type,
            response={key: value for key, value in response_payload.items() if key != "history"},
            request=request_payload,
            duration_ms_value=duration_ms(started_at),
            history_id=history_id,
            created_at=created_at,
        )
        if attach_to_response:
            response_payload["history"] = {"saved": True, **saved}
    except Exception as exc:
        logger.warning("Failed to save API history JSON: %s", exc)
        if attach_to_response:
            response_payload["history"] = {
                "saved": False,
                "warning": "Detection succeeded, but history JSON could not be saved.",
            }


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": API_VERSION,
    }


@app.post("/api/v1/detect", response_model=DetectionResponse)
async def detect(
    file: UploadFile = File(...),
    save_history: bool = Query(True),
) -> dict[str, object] | JSONResponse:
    started_at = started_timer()
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        payload = _error_payload(
            "INVALID_FILE_TYPE",
            "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
        )
        if save_history:
            _save_history_safely(
                history_type="single",
                response_payload=payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
                attach_to_response=False,
            )
        return JSONResponse(status_code=400, content=payload)

    contents = await file.read()
    if not contents:
        payload = _error_payload("EMPTY_FILE", "Uploaded file is empty.")
        if save_history:
            _save_history_safely(
                history_type="single",
                response_payload=payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
                attach_to_response=False,
            )
        return JSONResponse(status_code=400, content=payload)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        temp_path.write_bytes(contents)
        data = detect_image_for_api(str(temp_path), filename=filename)
        payload: dict[str, Any] = {
            "success": True,
            "data": data,
            "error": None,
        }
        if save_history:
            _save_history_safely(
                history_type="single",
                response_payload=payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
            )
        return payload
    except DetectionServiceError as exc:
        payload = _error_payload("DETECTION_FAILED", str(exc))
        if save_history:
            _save_history_safely(
                history_type="single",
                response_payload=payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
                attach_to_response=False,
            )
        return JSONResponse(status_code=500, content=payload)
    except Exception:
        payload = _error_payload(
            "INTERNAL_ERROR",
            "An unexpected error occurred while processing the image.",
        )
        if save_history:
            _save_history_safely(
                history_type="single",
                response_payload=payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
                attach_to_response=False,
            )
        return JSONResponse(status_code=500, content=payload)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


async def _batch_inputs_from_multipart(
    request: Request,
    default_save_history: bool,
) -> tuple[list[BatchDetectionInput], bool]:
    form = await request.form()
    save_history = _parse_bool(form.get("save_history"), default_save_history)
    upload_items = []
    for field_name in ("files", "file"):
        upload_items.extend(form.getlist(field_name))

    inputs: list[BatchDetectionInput] = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(upload_items):
        filename = _safe_filename(getattr(item, "filename", None))
        suffix = Path(filename).suffix.lower()
        error: dict[str, Any] | None = None
        temp_path: Path | None = None

        if suffix not in SUPPORTED_EXTENSIONS:
            error = {
                "type": "ValueError",
                "message": "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
                "recoverable": True,
            }
        else:
            contents = await item.read()
            if not contents:
                error = {
                    "type": "ValueError",
                    "message": "Uploaded file is empty.",
                    "recoverable": True,
                }
            else:
                temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
                temp_path.write_bytes(contents)

        inputs.append(
            BatchDetectionInput(
                index=index,
                filename=filename,
                source="upload",
                image_path=str(temp_path) if temp_path else None,
                error=error,
            )
        )
    return inputs, save_history


async def _batch_inputs_from_json(
    request: Request,
    default_save_history: bool,
) -> tuple[list[BatchDetectionInput], bool]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be JSON or multipart/form-data.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    image_paths = payload.get("image_paths")
    if not isinstance(image_paths, list):
        raise HTTPException(status_code=400, detail="JSON body must include image_paths as a list.")
    return build_path_inputs([str(item) for item in image_paths]), _parse_bool(
        payload.get("save_history"),
        default_save_history,
    )


@app.post("/detect/batch")
@app.post("/api/v1/detect/batch")
async def detect_batch(
    request: Request,
    save_history: bool = Query(True),
) -> dict[str, Any]:
    started_at = started_timer()
    content_type = request.headers.get("content-type", "").lower()
    temp_paths: list[Path] = []

    try:
        if content_type.startswith("multipart/form-data"):
            inputs, body_save_history = await _batch_inputs_from_multipart(request, save_history)
            save_history = body_save_history
            temp_paths = [Path(item.image_path) for item in inputs if item.source == "upload" and item.image_path]
        else:
            inputs, body_save_history = await _batch_inputs_from_json(request, save_history)
            save_history = body_save_history

        if not inputs:
            raise HTTPException(status_code=400, detail="Batch request must include at least one image.")

        payload = run_batch_detection(inputs)
        if save_history:
            _save_history_safely(
                history_type="batch",
                response_payload=payload,
                request_payload=_history_request_from_batch(inputs),
                started_at=started_at,
                history_id=str(payload["batch_id"]),
                created_at=str(payload["created_at"]),
            )
        return payload
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


@app.get("/history")
@app.get("/api/v1/history")
def history(
    limit: int = Query(20, ge=1, le=100),
    history_type: str = Query("all"),
) -> dict[str, Any]:
    try:
        return list_history(limit=limit, history_type=history_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/history/{filename}")
@app.get("/api/v1/history/{filename}")
def history_detail(filename: str) -> dict[str, Any]:
    try:
        return read_history(filename)
    except InvalidHistoryFilenameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CorruptHistoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    limit_recent: int = Query(10, ge=1, le=100),
    include_debug: bool = Query(False),
) -> dict[str, Any]:
    return build_dashboard_payload(
        limit_recent=limit_recent,
        include_debug=include_debug,
    )


@app.get("/dashboard/recent-results", response_model=DashboardRecentResultsResponse)
def dashboard_recent_results(
    limit: int = Query(20, ge=1, le=100),
    final_label: str | None = Query(None),
    risk_level: str | None = Query(None),
) -> dict[str, Any]:
    if final_label is not None and final_label not in DASHBOARD_FINAL_LABEL_FILTERS:
        raise HTTPException(
            status_code=400,
            detail="final_label must be one of: ai_generated, real, uncertain.",
        )
    if risk_level is not None and risk_level not in DASHBOARD_RISK_LEVEL_FILTERS:
        raise HTTPException(
            status_code=400,
            detail="risk_level must be one of: low, medium, high, unknown.",
        )
    return build_recent_results_payload(
        limit=limit,
        final_label=final_label,
        risk_level=risk_level,
    )


@app.get("/dashboard/chart-data", response_model=DashboardChartDataResponse)
def dashboard_chart_data() -> dict[str, Any]:
    return build_chart_data_payload()


@app.get("/errors")
@app.get("/dashboard/errors")
def error_gallery_page() -> FileResponse:
    if not ERROR_GALLERY_PAGE.exists():
        raise HTTPException(status_code=404, detail="Error Gallery page is not available.")
    return FileResponse(ERROR_GALLERY_PAGE)


@app.get("/api/v1/errors/summary")
def errors_summary() -> dict[str, Any]:
    return build_error_summary()


@app.get("/api/v1/errors")
def errors(
    type_: str = Query("all", alias="type"),
    scenario: str | None = Query(None),
    format: str | None = Query(None),
    difficulty: str | None = Query(None),
    resolution_bucket: str | None = Query(None),
    source_folder: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(None, ge=0.0, le=1.0),
    sort: str = Query("confidence_desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        return list_error_items(
            item_type=type_,
            scenario=scenario,
            format=format,
            difficulty=difficulty,
            resolution_bucket=resolution_bucket,
            source_folder=source_folder,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/errors/{item_id}")
def error_detail(item_id: str) -> dict[str, Any]:
    try:
        return get_error_item(item_id)
    except ErrorItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/errors/{item_id}/review")
async def error_review(item_id: str, request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")
    try:
        review = save_review_note(item_id, payload)
    except ErrorItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "ok",
        "review": review,
    }


@app.get("/dashboard/error-taxonomy")
@app.get("/api/v1/error-taxonomy")
def error_taxonomy(version: str = Query("day25")) -> dict[str, Any]:
    try:
        version_text = version.lower() if isinstance(version, str) else "day25"
        if version_text in {"calibrated", "day25_1", "day25.1"}:
            return build_calibrated_error_taxonomy_payload()
        return build_error_taxonomy_payload()
    except Day25InputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
