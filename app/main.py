from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


# ---- Minimal .env loader (no python-dotenv dependency) ---------------------
# Read once at import time, BEFORE any other module reads os.environ. Existing
# environment values are NEVER overwritten so shell exports still win. Lines
# starting with # are comments; empty lines ignored; values can be quoted.
def _load_dotenv_once() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:  # noqa: BLE001 — never let env loading break startup
        pass


_load_dotenv_once()
# ----------------------------------------------------------------------------

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

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
from app.detectors.registry import build_model_status
from app.policy.evidence_policy import load_policy_config
from app.services.detection_service import (
    DetectionServiceError,
    build_product_error_response,
    build_product_single_response,
    detect_image_for_api,
    image_input_summary,
)
from app.services.dashboard_summary import (
    build_chart_data_payload,
    build_dashboard_payload,
    build_recent_results_payload,
)
from app.services.evidence_replay import (
    build_review_manifest,
    read_policy_replay_export,
    read_review_manifest_export,
    replay_policy_profiles,
)
from app.services.review_calibration import (
    SCHEMA_VERSION as REVIEW_CALIBRATION_SCHEMA_VERSION,
    build_manifest as build_review_calibration_manifest,
    build_summary as build_review_calibration_summary,
    read_outputs as read_review_calibration_outputs,
)
from app.services.scenario_stress_pack import (
    build_scenario_stress_pack,
    read_scenario_stress_pack_export,
)
from app.services.training_readiness import (
    build_label_queue_payload as build_training_label_queue_payload,
    build_payload as build_training_readiness_payload,
    read_outputs as read_training_readiness_outputs,
    write_outputs as write_training_readiness_outputs,
)
from app.services.retention import run_retention_policy
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
    now_iso,
    read_history,
    save_history as write_history,
    started_timer,
)
from app.services.audit_log import write_audit_event
from app.services.report_center import (
    ReportRecordNotFound,
    export_csv,
    get_html_report_path,
    get_report_detail,
    search_reports,
    review_queue,
    update_review,
)
from app.services import report_store
from app.services.report_center import bootstrap_sqlite_from_history


API_VERSION = "0.1.0"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(os.getenv("MINERVA_UPLOAD_DIR", str(PROJECT_ROOT / ".tmp" / "api_uploads"))).expanduser()
FRONTEND_DASHBOARD_DIR = PROJECT_ROOT / "frontend" / "dashboard"
ERROR_GALLERY_PAGE = FRONTEND_DASHBOARD_DIR / "errors.html"
logger = logging.getLogger("uvicorn.error")
PRODUCT_DEFAULT_POLICY_PROFILE = "strict_safe_plus"

app = FastAPI(title="AI Image Trust Scanner API", version=API_VERSION)


def _configured_api_keys() -> list[str]:
    raw_values = [
        os.getenv("MINERVA_API_KEY", ""),
        os.getenv("MINERVA_API_KEYS", ""),
    ]
    keys: list[str] = []
    for raw in raw_values:
        for item in str(raw or "").split(","):
            key = item.strip()
            if key:
                keys.append(key)
    return keys


def _public_without_api_key(path: str) -> bool:
    if path in {"/health", "/api/health", "/openapi.json", "/docs", "/redoc", "/favicon.ico"}:
        return True
    return path.startswith(("/dashboard-ui", "/dashboard-assets", "/media"))


def _request_api_key(request: Request) -> str:
    return str(
        request.headers.get("X-API-Key")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or request.query_params.get("api_key")
        or request.query_params.get("apiKey")
        or ""
    ).strip()


@app.middleware("http")
async def _optional_api_key_auth(request: Request, call_next):
    keys = _configured_api_keys()
    if not keys or request.method == "OPTIONS" or _public_without_api_key(request.url.path):
        return await call_next(request)
    supplied = _request_api_key(request)
    if supplied and any(secrets.compare_digest(supplied, expected) for expected in keys):
        return await call_next(request)
    return JSONResponse(
        status_code=401,
        content={
            "detail": "API key required.",
            "code": "API_KEY_REQUIRED",
        },
        headers={"WWW-Authenticate": "ApiKey"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8033",
        "http://localhost:8033",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "null",
    ],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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


@app.on_event("startup")
def _startup_reports_store() -> None:
    try:
        bootstrap_sqlite_from_history()
    except Exception as exc:
        logger.warning("Report SQLite bootstrap skipped: %s", exc)


# Warmup completion gate. Detection requests block on this until the deep
# warmup (legacy CLIP + open-source + CUDA kernels) has finished, so the very
# first user scan can never race the cold-load and show "backend lost".
import threading as _threading

_WARMUP_DONE = _threading.Event()


def _positive_float_env(name: str, default: float, minimum: float = 1.0) -> float:
    try:
        return max(minimum, float(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


_WARMUP_MAX_WAIT_SECONDS = _positive_float_env("DETECTOR_WARMUP_MAX_WAIT_SECONDS", 120.0)
_SINGLE_DETECTION_TIMEOUT_SECONDS = _positive_float_env("SINGLE_DETECTION_TIMEOUT_SECONDS", 240.0)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


_BATCH_JOB_EXECUTOR = ThreadPoolExecutor(
    max_workers=_positive_int_env("BATCH_JOB_MAX_WORKERS", 1),
    thread_name_prefix="batch-detect",
)
_BATCH_JOB_MAX_RECORDS = _positive_int_env("BATCH_JOB_MAX_RECORDS", 200)
_BATCH_JOB_TTL_SECONDS = _positive_int_env("BATCH_JOB_TTL_SECONDS", 6 * 60 * 60)
_BATCH_JOBS: dict[str, dict[str, Any]] = {}
_BATCH_JOBS_LOCK = _threading.Lock()


@app.on_event("startup")
async def _startup_lift_threadpool_limit() -> None:
    """Bump the anyio threadpool from default 40 → 64 so that occasional slow
    forensic paths can't starve other endpoints. Cheap insurance for a
    multi-user demo (judges clicking around)."""
    try:
        import anyio
        anyio.to_thread.current_default_thread_limiter().total_tokens = 64
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not raise anyio threadpool limit: %s", exc)


@app.on_event("startup")
def _startup_warmup_hf_detectors() -> None:
    """Preload the HF detectors (Smogy + Ateeqq) in a background daemon thread so
    requests never pay a cold-load penalty (P0 latency stays intact). Disable
    with DETECTOR_WARMUP_ON_STARTUP=false. Until warmup finishes, requests fall
    back to the legacy baseline exactly as before."""
    import os
    import threading

    if str(os.getenv("DETECTOR_WARMUP_ON_STARTUP", "false")).strip().lower() not in {"1", "true", "yes", "on"}:
        _WARMUP_DONE.set()  # warmup disabled → don't block requests forever
        return

    def _warmup() -> None:
        # Step 1: load HF runtimes (Smogy + Ateeqq) weights into the cached
        # runtime. Fast — these are ~80MB each.
        try:
            from app.detectors.registry import warmup_local_hf_detectors

            result = warmup_local_hf_detectors()
            logger.info("HF detector warmup: %s", result)
        except Exception as exc:  # never crash startup
            logger.warning("HF detector warmup skipped: %s", exc)
            _WARMUP_DONE.set()
            return

        # Step 2: fire one full detect pass on a tiny dummy image so the slow
        # legacy CLIP-ViT-L detector + open-source adapter + dima806 also load,
        # AND CUDA kernels are JIT-compiled. Without this the FIRST real user
        # scan pays a 30–70s cold tax (we measured 74s), which the frontend's
        # 120s timeout survives but a concurrent 2nd scan does not — that's
        # what makes the dashboard show "backend connection failed" on rapid
        # successive scans. Tiny 32×32 PNG keeps the warmup fast (~5–10s).
        try:
            import io
            import tempfile
            from app.services.detection_service import detect_image_for_api

            # Build a minimal 32×32 PNG without pulling in heavy imports.
            try:
                from PIL import Image as _Image  # transformers already brought this in
                buf = io.BytesIO()
                _Image.new("RGB", (32, 32), color=(127, 127, 127)).save(buf, format="PNG")
                png_bytes = buf.getvalue()
            except Exception:
                # 67-byte minimal-PNG fallback (white 1×1) if PIL is unavailable.
                png_bytes = bytes.fromhex(
                    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
                    "8900000000017352474200AECE1CE90000000D49444154789C636200000000020001"
                    "1502A50000000049454E44AE426082"
                )

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(png_bytes)
                tmp_path = tmp.name
            try:
                detect_image_for_api(tmp_path, filename="_warmup.png")
                logger.info("Deep warmup OK — legacy CLIP + open-source + dima806 + CUDA kernels primed.")
            finally:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass
        except Exception as exc:  # never crash startup
            logger.warning("Deep warmup skipped (first scan may pay cold tax): %s", exc)
        finally:
            # Always release the gate, even on failure — better to let a request
            # try and pay cold tax once than to deadlock forever on a warmup bug.
            _WARMUP_DONE.set()

    threading.Thread(target=_warmup, name="hf-detector-warmup", daemon=True).start()


async def _wait_for_warmup() -> None:
    """Block the request until warmup completes. Without this gate,
    a scan that arrives during the 30–60s warmup window races the cold-load
    and the frontend shows 'detection failed' on the very first image."""
    if _WARMUP_DONE.is_set():
        return
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    completed = await loop.run_in_executor(None, _WARMUP_DONE.wait, _WARMUP_MAX_WAIT_SECONDS)
    if not completed:
        logger.warning("HF detector warmup wait exceeded %.0fs; releasing request gate.", _WARMUP_MAX_WAIT_SECONDS)
        _WARMUP_DONE.set()


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


def _batch_request_payload(inputs: list[BatchDetectionInput], policy_profile: str | None) -> dict[str, Any]:
    payload = _history_request_from_batch(inputs)
    if policy_profile:
        payload["policy_profile"] = policy_profile
    return payload


def _clean_policy_profile(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("-", "_")
    return text or None


def _public_policy_profile(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    thresholds = {
        "real_threshold": payload.get("real_threshold"),
        "gray_threshold": payload.get("gray_threshold"),
        "ai_threshold": payload.get("ai_threshold"),
    }
    review_burden = "high" if name == "high_recall_review" else "lower_fp" if "low_fp" in name else "standard"
    return {
        "name": name,
        "threshold_profile": str(payload.get("threshold_profile") or name),
        "thresholds": thresholds,
        "ai_risk_level": str(payload.get("ai_risk_level") or "medium"),
        "ai_review_required": bool(payload.get("ai_review_required", True)),
        "review_band_risk_level": str(payload.get("review_band_risk_level") or "medium"),
        "review_burden": review_burden,
        "primary_conflict_review": bool(payload.get("primary_conflict_review", False)),
        "recommended_for": (
            "maximum AI recall with more human review"
            if review_burden == "high"
            else "Mirage-heavy reviews where lower real-image false positives matter"
            if review_burden == "lower_fp"
            else "standard local product decisions"
        ),
    }


@app.get("/api/v1/policy/profiles")
def policy_profiles() -> dict[str, Any]:
    try:
        config = load_policy_config()
    except Exception as exc:
        logger.exception("Policy profile config failed: %s", exc)
        raise HTTPException(status_code=500, detail="Policy profile config failed.") from exc
    profiles = config.get("policy_profiles") if isinstance(config.get("policy_profiles"), dict) else {}
    public_profiles = [
        _public_policy_profile(str(name), payload if isinstance(payload, dict) else {})
        for name, payload in profiles.items()
    ]
    return {
        "schema_version": "policy_profiles_v1",
        "policy_version": str(config.get("policy_version") or "evidence_policy_v1"),
        "default_policy_profile": str(config.get("default_policy_profile") or ""),
        "product_default_policy_profile": PRODUCT_DEFAULT_POLICY_PROFILE,
        "profiles": public_profiles,
    }


@app.get("/api/v1/admin/retention")
def admin_retention_policy(
    apply_changes: bool = Query(False, alias="apply"),
    confirm: str = Query(""),
    include_candidates: bool = Query(False),
) -> dict[str, Any]:
    if apply_changes and confirm != "delete-local-files":
        raise HTTPException(status_code=400, detail="Applying retention requires confirm=delete-local-files.")
    try:
        return run_retention_policy(apply=apply_changes, include_candidates=include_candidates)
    except Exception as exc:
        logger.exception("Retention policy failed: %s", exc)
        raise HTTPException(status_code=500, detail="Retention policy failed.") from exc


def _batch_job_processed(job: dict[str, Any]) -> int:
    succeeded = job.get("succeeded")
    failed = job.get("failed")
    return int(succeeded or 0) + int(failed or 0)


def _batch_job_public(job: dict[str, Any], *, include_result: bool = False) -> dict[str, Any]:
    payload = {
        "job_id": job["job_id"],
        "status": job["status"],
        "submitted_at": job["submitted_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "total": job.get("total", 0),
        "processed": _batch_job_processed(job),
        "succeeded": job.get("succeeded"),
        "failed": job.get("failed"),
        "error": job.get("error"),
        "status_url": f"/api/v1/detect/batch/jobs/{job['job_id']}",
        "result_url": f"/api/v1/detect/batch/jobs/{job['job_id']}/result",
    }
    if include_result and "result" in job:
        payload["result"] = job["result"]
    return payload


def _prune_batch_jobs_locked(now_monotonic: float | None = None) -> None:
    now = now_monotonic or time.monotonic()
    terminal_statuses = {"completed", "failed"}
    stale_job_ids = [
        job_id
        for job_id, job in _BATCH_JOBS.items()
        if job.get("status") in terminal_statuses
        and now - float(job.get("_updated_monotonic", now)) > _BATCH_JOB_TTL_SECONDS
    ]
    for job_id in stale_job_ids:
        _BATCH_JOBS.pop(job_id, None)

    if len(_BATCH_JOBS) <= _BATCH_JOB_MAX_RECORDS:
        return

    oldest_terminal_jobs = sorted(
        (
            (job_id, job)
            for job_id, job in _BATCH_JOBS.items()
            if job.get("status") in terminal_statuses
        ),
        key=lambda item: float(item[1].get("_updated_monotonic", 0.0)),
    )
    for job_id, _job in oldest_terminal_jobs:
        if len(_BATCH_JOBS) <= _BATCH_JOB_MAX_RECORDS:
            break
        _BATCH_JOBS.pop(job_id, None)


def _get_batch_job(job_id: str) -> dict[str, Any]:
    with _BATCH_JOBS_LOCK:
        _prune_batch_jobs_locked()
        job = _BATCH_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Batch job not found: {job_id}")
        return dict(job)


def _update_batch_job(job_id: str, **fields: Any) -> None:
    with _BATCH_JOBS_LOCK:
        if job_id in _BATCH_JOBS:
            fields["_updated_monotonic"] = time.monotonic()
            _BATCH_JOBS[job_id].update(fields)


def _run_batch_job(
    *,
    job_id: str,
    inputs: list[BatchDetectionInput],
    policy_profile: str | None,
    save_history: bool,
    request_payload: dict[str, Any],
    temp_paths: list[Path],
) -> None:
    started_at = started_timer()
    _update_batch_job(job_id, status="running", started_at=now_iso())
    try:
        payload = run_batch_detection(inputs, policy_profile=policy_profile)
        if save_history:
            _save_history_safely(
                history_type="batch",
                response_payload=payload,
                request_payload=request_payload,
                started_at=started_at,
                history_id=str(payload["batch_id"]),
                created_at=str(payload["created_at"]),
            )
        _update_batch_job(
            job_id,
            status="completed",
            completed_at=now_iso(),
            succeeded=payload.get("succeeded"),
            failed=payload.get("failed"),
            result=payload,
        )
    except Exception as exc:
        logger.exception("Batch job failed: %s", job_id)
        _update_batch_job(
            job_id,
            status="failed",
            completed_at=now_iso(),
            error={
                "type": type(exc).__name__,
                "message": str(exc),
                "recoverable": True,
            },
        )
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


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


# NOTE: health/model-status are async def on purpose. As sync def they would
# enter starlette's threadpool and queue behind any slow detection request,
# making the frontend report "backend connection lost" while a single image
# was still inferring. As async def they run on the event loop and stay
# responsive no matter what the detection pipeline is doing.
@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ai-image-trust-scanner",
        "version": API_VERSION,
        "api": "ready",
    }


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    db_path = report_store.REPORT_DB_PATH
    database_status = "ok" if db_path.exists() or db_path.parent.exists() else "uninitialized"
    reports_api_status = "ok" if database_status in {"ok", "uninitialized"} else "error"
    return {
        "api_status": "ok",
        "reports_api_status": reports_api_status,
        "database_status": database_status,
        "persistence_enabled": database_status in {"ok", "uninitialized"},
        "report_count": None,
        "report_schema_version": report_store.REPORT_SCHEMA_VERSION,
        "detector_version": report_store.DETECTOR_VERSION,
        "model_version": report_store.MODEL_VERSION,
        "storage_backend": "sqlite",
        "html_report_enabled": True,
        "export_enabled": True,
        "warmup_ready": _WARMUP_DONE.is_set(),
    }


@app.get("/api/model-status")
async def api_model_status() -> dict[str, Any]:
    return build_model_status()


@app.post("/api/v1/detect", response_model=DetectionResponse)
async def detect(
    file: UploadFile = File(...),
    save_history: bool = Query(True),
) -> dict[str, object] | JSONResponse:
    started_at = started_timer()
    filename = _safe_filename(file.filename)
    logger.info("Single detect request received: filename=%s content_type=%s", filename, file.content_type)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        logger.info("Single detect rejected at validation: filename=%s suffix=%s", filename, suffix)
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
        logger.info("Single detect rejected at read_file: filename=%s empty upload", filename)
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
        logger.info("Single detect file read: filename=%s bytes=%s temp_path=%s", filename, len(contents), temp_path)
        logger.info("Single detect starting detector: filename=%s", filename)
        data = await run_in_threadpool(detect_image_for_api, str(temp_path), filename=filename)
        logger.info("Single detect completed: filename=%s duration_ms=%s", filename, duration_ms(started_at))
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
        logger.exception("Detection service failed at detect stage for uploaded image %s", filename)
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
        logger.exception("Unexpected detection failure for uploaded image %s", filename)
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


@app.post("/api/detect/single", response_model=None)
async def detect_single_product(
    file: UploadFile = File(...),
    save_history: bool = Query(True),
    policy_profile: str | None = Query(None),
) -> Any:
    started_at = started_timer()
    filename = _safe_filename(file.filename)
    logger.info("Day41 product single detect request received: filename=%s content_type=%s", filename, file.content_type)
    suffix = Path(filename).suffix.lower()
    base_input = {
        "filename": filename,
        "sha256": None,
        "mime_type": file.content_type or "unknown",
        "width": 0,
        "height": 0,
        "file_size_bytes": 0,
    }
    if suffix not in SUPPORTED_EXTENSIONS:
        payload = build_product_error_response(
            filename=filename,
            message="Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
            code="INVALID_FILE_TYPE",
            input_summary=base_input,
            total_latency_ms=duration_ms(started_at),
        )
        return JSONResponse(status_code=400, content=payload)

    contents = await file.read()
    if not contents:
        payload = build_product_error_response(
            filename=filename,
            message="Uploaded file is empty.",
            code="EMPTY_FILE",
            input_summary=base_input,
            total_latency_ms=duration_ms(started_at),
        )
        return JSONResponse(status_code=400, content=payload)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        temp_path.write_bytes(contents)
        input_summary = image_input_summary(temp_path, filename, file.content_type)
        # Wait for deep warmup so the first scan never races the cold-load.
        await _wait_for_warmup()
        # Hard ceiling on a single detection. Without this, a single
        # pathological image that wedges the forensic path holds a threadpool
        # slot indefinitely. The default is intentionally higher than the old
        # 90s ceiling because the first real image can still pay CUDA/kernel
        # warmup costs even after model weights have loaded.
        import asyncio as _asyncio
        try:
            data = await _asyncio.wait_for(
                run_in_threadpool(
                    detect_image_for_api,
                    str(temp_path),
                    filename=filename,
                    policy_profile=policy_profile,
                ),
                timeout=_SINGLE_DETECTION_TIMEOUT_SECONDS,
            )
        except _asyncio.TimeoutError:
            timeout_seconds = int(round(_SINGLE_DETECTION_TIMEOUT_SECONDS))
            logger.error("Day41 product single detect timed out after %ss: filename=%s", timeout_seconds, filename)
            payload = build_product_error_response(
                filename=filename,
                message=f"Detection exceeded the {timeout_seconds}s ceiling — please retry or try a smaller image.",
                code="DETECTION_TIMEOUT",
                input_summary=base_input,
                total_latency_ms=duration_ms(started_at),
            )
            return JSONResponse(status_code=504, content=payload)
        payload = build_product_single_response(
            data,
            input_summary=input_summary,
            total_latency_ms=duration_ms(started_at),
        )
        if save_history:
            history_payload: dict[str, Any] = {
                "success": True,
                "data": data,
                "product_response": payload,
                "error": None,
            }
            _save_history_safely(
                history_type="single",
                response_payload=history_payload,
                request_payload=_single_request(filename, "upload"),
                started_at=started_at,
                history_id=new_history_id("single"),
                attach_to_response=False,
            )
        return payload
    except DetectionServiceError as exc:
        logger.exception("Day41 product detection service failed for uploaded image %s", filename)
        payload = build_product_error_response(
            filename=filename,
            message=str(exc),
            code="DETECTION_FAILED",
            input_summary=base_input,
            total_latency_ms=duration_ms(started_at),
        )
        return JSONResponse(status_code=500, content=payload)
    except Exception as exc:
        logger.exception("Unexpected Day41 product detection failure for uploaded image %s", filename)
        payload = build_product_error_response(
            filename=filename,
            message="An unexpected error occurred while processing the image.",
            code="INTERNAL_ERROR",
            input_summary=base_input,
            total_latency_ms=duration_ms(started_at),
        )
        payload["error"]["detail"] = str(exc)
        return JSONResponse(status_code=500, content=payload)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


async def _batch_inputs_from_multipart(
    request: Request,
    default_save_history: bool,
) -> tuple[list[BatchDetectionInput], bool, str | None]:
    form = await request.form()
    save_history = _parse_bool(form.get("save_history"), default_save_history)
    policy_profile = _clean_policy_profile(form.get("policy_profile"))
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
    return inputs, save_history, policy_profile


async def _batch_inputs_from_json(
    request: Request,
    default_save_history: bool,
) -> tuple[list[BatchDetectionInput], bool, str | None]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be JSON or multipart/form-data.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    image_paths = payload.get("image_paths")
    if not isinstance(image_paths, list):
        raise HTTPException(status_code=400, detail="JSON body must include image_paths as a list.")
    return (
        build_path_inputs([str(item) for item in image_paths]),
        _parse_bool(payload.get("save_history"), default_save_history),
        _clean_policy_profile(payload.get("policy_profile")),
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
            inputs, body_save_history, policy_profile = await _batch_inputs_from_multipart(request, save_history)
            save_history = body_save_history
            temp_paths = [Path(item.image_path) for item in inputs if item.source == "upload" and item.image_path]
        else:
            inputs, body_save_history, policy_profile = await _batch_inputs_from_json(request, save_history)
            save_history = body_save_history

        if not inputs:
            raise HTTPException(status_code=400, detail="Batch request must include at least one image.")

        payload = await run_in_threadpool(run_batch_detection, inputs, policy_profile)
        if save_history:
            _save_history_safely(
                history_type="batch",
                response_payload=payload,
                request_payload=_batch_request_payload(inputs, policy_profile),
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


@app.post("/api/v1/detect/batch/jobs")
async def create_batch_job(
    request: Request,
    save_history: bool = Query(True),
) -> JSONResponse:
    content_type = request.headers.get("content-type", "").lower()
    temp_paths: list[Path] = []
    if content_type.startswith("multipart/form-data"):
        inputs, body_save_history, policy_profile = await _batch_inputs_from_multipart(request, save_history)
        save_history = body_save_history
        temp_paths = [Path(item.image_path) for item in inputs if item.source == "upload" and item.image_path]
    else:
        inputs, body_save_history, policy_profile = await _batch_inputs_from_json(request, save_history)
        save_history = body_save_history

    if not inputs:
        raise HTTPException(status_code=400, detail="Batch request must include at least one image.")

    job_id = new_history_id("batchjob")
    job = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": now_iso(),
        "started_at": None,
        "completed_at": None,
        "total": len(inputs),
        "succeeded": None,
        "failed": None,
        "error": None,
        "_updated_monotonic": time.monotonic(),
    }
    with _BATCH_JOBS_LOCK:
        _prune_batch_jobs_locked()
        _BATCH_JOBS[job_id] = job

    _BATCH_JOB_EXECUTOR.submit(
        _run_batch_job,
        job_id=job_id,
        inputs=inputs,
        policy_profile=policy_profile,
        save_history=save_history,
        request_payload=_batch_request_payload(inputs, policy_profile),
        temp_paths=temp_paths,
    )
    return JSONResponse(status_code=202, content={"mode": "batch_job", **_batch_job_public(job)})


@app.get("/api/v1/detect/batch/jobs/{job_id}")
async def batch_job_status(job_id: str) -> dict[str, Any]:
    return {"mode": "batch_job", **_batch_job_public(_get_batch_job(job_id))}


@app.get("/api/v1/detect/batch/jobs/{job_id}/result", response_model=None)
async def batch_job_result(job_id: str) -> dict[str, Any] | JSONResponse:
    job = _get_batch_job(job_id)
    if job["status"] != "completed":
        return JSONResponse(status_code=202, content={"mode": "batch_job", **_batch_job_public(job)})
    return job["result"]


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


@app.get("/api/v1/reports")
def reports_list(
    q: str | None = Query(None),
    risk_level: str | None = Query(None),
    final_label: str | None = Query(None),
    review_status: str | None = Query(None),
    source_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        return search_reports(
            q=q,
            risk_level=risk_level,
            final_label=final_label,
            review_status=review_status,
            source_type=source_type,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            sort_by=None if sort else sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        logger.exception("Reports list failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reports list failed unexpectedly: %s", exc)
        raise HTTPException(status_code=500, detail="Reports API failed.") from exc


@app.get("/api/v1/reports/search")
def reports_search(
    q: str | None = Query(None),
    risk_level: str | None = Query(None),
    final_label: str | None = Query(None),
    review_status: str | None = Query(None),
    source_type: str | None = Query(None),
    date_range: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    confidence_range: str | None = Query(None),
    sort: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        return search_reports(
            q=q,
            risk_level=risk_level,
            final_label=final_label,
            review_status=review_status,
            source_type=source_type,
            date_range=date_range,
            date_from=date_from,
            date_to=date_to,
            confidence_range=confidence_range,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        logger.exception("Reports search failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reports search failed unexpectedly: %s", exc)
        raise HTTPException(status_code=500, detail="Reports API failed.") from exc


@app.get("/api/v1/reports/queue")
def reports_queue(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    try:
        return review_queue(limit=limit)
    except Exception as exc:
        logger.exception("Review queue failed: %s", exc)
        raise HTTPException(status_code=500, detail="Review queue failed.") from exc


@app.get("/api/v1/reports/review-manifest")
def reports_review_manifest(
    include_unreviewed: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    try:
        if not refresh and include_unreviewed:
            cached = read_review_manifest_export(limit=limit)
            if cached:
                return cached
        return build_review_manifest(
            include_unreviewed=include_unreviewed,
            include_private_paths=False,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Review manifest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Review manifest failed.") from exc


@app.get("/api/v1/reports/policy-replay")
def reports_policy_replay(
    profiles: str = Query("strict_safe_plus,high_recall_review"),
    include_unlabeled: bool = Query(True),
    include_rows: bool = Query(False),
    row_limit: int = Query(500, ge=1, le=5000),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    try:
        profile_names = [item.strip() for item in profiles.split(",") if item.strip()]
        cached = None if refresh else read_policy_replay_export(include_rows=include_rows, row_limit=row_limit)
        if cached and cached.get("profiles") == profile_names and bool(cached.get("include_unlabeled")) == include_unlabeled:
            return cached
        payload = replay_policy_profiles(profiles=profile_names, include_unlabeled=include_unlabeled)
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        payload["row_count"] = len(rows)
        payload["row_limit"] = row_limit if include_rows else 0
        payload["rows"] = rows[:row_limit] if include_rows else []
        return payload
    except Exception as exc:
        logger.exception("Policy replay failed: %s", exc)
        raise HTTPException(status_code=500, detail="Policy replay failed.") from exc


@app.get("/api/v1/reports/review-calibration")
def reports_review_calibration(
    limit: int = Query(200, ge=1, le=1000),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    try:
        if not refresh:
            cached = read_review_calibration_outputs(limit=limit)
            if cached:
                return cached
        items = build_review_calibration_manifest()
        summary = build_review_calibration_summary(items)
        return {
            "schema_version": REVIEW_CALIBRATION_SCHEMA_VERSION,
            "summary": summary,
            "total": len(items),
            "items": items[:limit],
            "limit": limit,
        }
    except Exception as exc:
        logger.exception("Review calibration failed: %s", exc)
        raise HTTPException(status_code=500, detail="Review calibration failed.") from exc


@app.get("/api/v1/reports/scenario-stress-pack")
def reports_scenario_stress_pack(
    limit: int = Query(200, ge=1, le=1000),
    max_sources: int = Query(50, ge=1, le=500),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    try:
        if not refresh:
            cached = read_scenario_stress_pack_export(limit=limit, include_private_paths=False)
            if cached:
                return cached
        pack = build_scenario_stress_pack(
            max_sources=max_sources,
            write_images=False,
            include_private_paths=False,
        )
        pack["items"] = pack.get("items", [])[:limit]
        pack["limit"] = limit
        pack["cached"] = False
        return pack
    except Exception as exc:
        logger.exception("Scenario stress pack failed: %s", exc)
        raise HTTPException(status_code=500, detail="Scenario stress pack failed.") from exc


@app.get("/api/v1/reports/training-readiness")
def reports_training_readiness(
    limit: int = Query(200, ge=1, le=1000),
    include_stress_pack: bool = Query(True),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    try:
        if not refresh and include_stress_pack:
            cached = read_training_readiness_outputs(limit=limit, include_private_paths=False)
            if cached:
                return cached
        return build_training_readiness_payload(
            include_stress_pack=include_stress_pack,
            include_private_paths=False,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Training readiness failed: %s", exc)
        raise HTTPException(status_code=500, detail="Training readiness failed.") from exc


@app.post("/api/v1/reports/training-readiness/rebuild")
def reports_training_readiness_rebuild(include_stress_pack: bool = Query(True)) -> dict[str, Any]:
    try:
        output = write_training_readiness_outputs(include_stress_pack=include_stress_pack)
        return {
            "schema_version": "training_readiness_rebuild_v1",
            "output_dir": output.get("output_dir"),
            "manifest_csv": output.get("manifest_csv"),
            "manifest_jsonl": output.get("manifest_jsonl"),
            "summary_json": output.get("summary_json"),
            "summary_md": output.get("summary_md"),
            "total": output.get("total"),
            "summary": output.get("summary"),
        }
    except Exception as exc:
        logger.exception("Training readiness rebuild failed: %s", exc)
        raise HTTPException(status_code=500, detail="Training readiness rebuild failed.") from exc


@app.get("/api/v1/reports/training-label-queue")
def reports_training_label_queue(limit: int = Query(20, ge=1, le=200)) -> dict[str, Any]:
    try:
        return build_training_label_queue_payload(limit=limit, include_private_paths=False)
    except Exception as exc:
        logger.exception("Training label queue failed: %s", exc)
        raise HTTPException(status_code=500, detail="Training label queue failed.") from exc


@app.patch("/api/v1/reports/{record_id}/review")
async def reports_review(record_id: str, request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")
    old_status = None
    try:
        old_status = get_report_detail(record_id).get("review_status")
    except ReportRecordNotFound:
        old_status = None
    try:
        record = update_review(record_id, payload)
    except ReportRecordNotFound as exc:
        logger.exception("Review status update failed; report not found: %s", record_id)
        write_audit_event("update_review_status", report_id=record_id, action_status="error", error_message=str(exc), old_review_status=old_status, new_review_status=payload.get("review_status"))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        logger.exception("Review status update rejected for %s: %s", record_id, exc)
        write_audit_event("update_review_status", report_id=record_id, action_status="error", error_message=str(exc), old_review_status=old_status, new_review_status=payload.get("review_status"))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Review status update failed unexpectedly for %s: %s", record_id, exc)
        write_audit_event("update_review_status", report_id=record_id, action_status="error", error_message=str(exc), old_review_status=old_status, new_review_status=payload.get("review_status"))
        raise HTTPException(status_code=500, detail="Review status save failed.") from exc
    write_audit_event("update_review_status", report_id=record_id, action_status="ok", old_review_status=old_status, new_review_status=record.get("review_status"))
    return {
        "status": "ok",
        "record": record,
    }


@app.get("/api/v1/reports/export", response_model=None)
def reports_export(
    format: str = Query("json"),
    q: str | None = Query(None),
    risk_level: str | None = Query(None),
    final_label: str | None = Query(None),
    review_status: str | None = Query(None),
    source_type: str | None = Query(None),
    date_range: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    confidence_range: str | None = Query(None),
    sort: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_order: str | None = Query(None),
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    export_format = str(format or "json").lower()
    try:
        payload = search_reports(
            q=q,
            risk_level=risk_level,
            final_label=final_label,
            review_status=review_status,
            source_type=source_type,
            date_range=date_range,
            date_from=date_from,
            date_to=date_to,
            confidence_range=confidence_range,
            sort=sort,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        if export_format == "json":
            write_audit_event("export_reports", action_status="ok", extra={"format": "json", "count": len(payload.get("items", []))})
            return JSONResponse(content=payload)
        if export_format == "csv":
            write_audit_event("export_reports", action_status="ok", extra={"format": "csv", "count": len(payload.get("items", []))})
            return PlainTextResponse(export_csv(payload["items"]), media_type="text/csv; charset=utf-8")
        raise HTTPException(status_code=400, detail="format must be json or csv.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Report export failed: %s", exc)
        write_audit_event("export_reports", action_status="error", error_message=str(exc), extra={"format": export_format})
        raise HTTPException(status_code=500, detail="Report export failed.") from exc


@app.get("/api/v1/reports/{report_id}")
def reports_detail(report_id: str) -> dict[str, Any]:
    try:
        return get_report_detail(report_id)
    except ReportRecordNotFound as exc:
        logger.exception("Report detail not found: %s", report_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Report detail failed for %s: %s", report_id, exc)
        raise HTTPException(status_code=500, detail="Report detail failed.") from exc


@app.get("/api/v1/reports/{report_id}/html")
def reports_html(report_id: str) -> FileResponse:
    try:
        response = FileResponse(get_html_report_path(report_id), media_type="text/html; charset=utf-8")
        write_audit_event("view_html_report", report_id=report_id, action_status="ok")
        return response
    except ReportRecordNotFound as exc:
        logger.exception("HTML report not found: %s", report_id)
        write_audit_event("view_html_report", report_id=report_id, action_status="error", error_message=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("HTML report failed for %s: %s", report_id, exc)
        write_audit_event("view_html_report", report_id=report_id, action_status="error", error_message=str(exc))
        raise HTTPException(status_code=500, detail="HTML report failed.") from exc


@app.get("/errors")
@app.get("/dashboard/errors")
def error_gallery_page() -> RedirectResponse:
    if not ERROR_GALLERY_PAGE.exists():
        raise HTTPException(status_code=404, detail="Error Gallery page is not available.")
    return RedirectResponse(url="/dashboard-ui/errors.html", status_code=307)


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
