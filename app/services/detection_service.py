from __future__ import annotations

from pathlib import Path
from typing import Any

from main import run_pipeline
from src.api_adapter import build_frontend_response
from app.services.audit_log import write_audit_event
from app.services.report_store import make_report_record, save_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_REPORT_DIR = PROJECT_ROOT / ".tmp" / "api_reports"


class DetectionServiceError(Exception):
    """Raised when the detector cannot produce a usable API result."""


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return round(max(0.0, min(1.0, confidence)), 4)


def _api_label(frontend_label: Any) -> str:
    label = str(frontend_label or "").strip().lower()
    if label in {"ai_generated", "likely_ai", "ai"}:
        return "ai"
    if label in {"real_photo", "likely_real", "real"}:
        return "real"
    return "uncertain"


def _api_risk_level(value: Any, final_label: str) -> str:
    risk = str(value or "").strip().lower()
    if risk in {"low", "medium", "high"}:
        return risk
    if final_label == "ai":
        return "high"
    if final_label == "real":
        return "low"
    return "medium"


def _sha256(path: Path) -> str | None:
    try:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def detect_image_for_api(image_path: str, filename: str, source_type: str = "single") -> dict[str, Any]:
    """Run the existing detector and return the Day19 API data payload.

    The detection path intentionally reuses the Day18 frontend adapter, then
    maps its result into the compact HTTP envelope requested for Day19.
    """
    path = Path(image_path)
    report = run_pipeline(path, output_dir=API_REPORT_DIR)
    if not report.get("ok"):
        message = (
            report.get("image_info", {}).get("error")
            or "The detector could not process the uploaded image."
        )
        raise DetectionServiceError(str(message))

    image_info = report.get("image_info", {})
    frontend_response = build_frontend_response(
        report,
        image_meta={
            "filename": filename,
            "image_path": str(path),
            "width": image_info.get("width"),
            "height": image_info.get("height"),
            "format": image_info.get("format") or path.suffix.lower().lstrip("."),
            "size_bytes": image_info.get("file_size_bytes"),
        },
        include_debug=True,
    )
    result = frontend_response.get("data", {}).get("result", {})
    image = frontend_response.get("data", {}).get("image", {})

    final_label = _api_label(result.get("final_label"))
    risk_level = _api_risk_level(result.get("risk_level"), final_label)

    data = {
        "filename": str(image.get("filename") or filename),
        "final_label": final_label,
        "risk_level": risk_level,
        "confidence": _clamp_confidence(result.get("confidence")),
        "decision_reason": result.get("decision_reason") or [],
        "recommendation": result.get("recommendation") or {},
        "user_facing_summary": str(result.get("user_facing_summary") or ""),
        "technical_explanation": result.get("technical_explanation") or {},
        "debug_evidence": result.get("debug_evidence") or {},
    }
    record = make_report_record(
        detection_data=data,
        source_type=source_type,
        image_path=str(path),
        file_sha256=_sha256(path),
        report_payload={
            "frontend_response": frontend_response,
            "api_data": data,
            "raw_report": report,
        },
        export_payload=data,
    )
    saved = save_report(record)
    write_audit_event("create_report", report_id=saved.get("report_id"), action_status="ok")
    data.update(
        {
            "report_id": saved["report_id"],
            "id": saved["report_id"],
            "review_status": saved["review_status"],
            "report_schema_version": saved["report_schema_version"],
            "detector_version": saved["detector_version"],
            "model_version": saved["model_version"],
            "html_report_available": saved["html_report_available"],
        }
    )
    return data
