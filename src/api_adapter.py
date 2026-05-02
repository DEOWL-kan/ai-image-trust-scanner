from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.product_output_schema import build_product_output


SCHEMA_VERSION = "1.0.0"
ADAPTER_VERSION = "day18_api_adapter_v1"
MODEL_FAMILY = "handcrafted_detector"

FINAL_LABELS = {"ai_generated", "real_photo", "uncertain"}
RISK_LEVELS = {"low", "medium", "high"}
RECOMMENDATION_ACTIONS = {"allow", "review", "warn"}
ERROR_CODES = {
    "INVALID_IMAGE",
    "DETECTION_FAILED",
    "UNSUPPORTED_FORMAT",
    "INTERNAL_ERROR",
}

DAY17_FIELDS = {
    "final_label",
    "risk_level",
    "confidence",
    "decision_reason",
    "recommendation",
    "user_facing_summary",
    "technical_explanation",
    "debug_evidence",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_request_id() -> str:
    return str(uuid.uuid4())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _first_float(*values: Any) -> float | None:
    for value in values:
        number = _safe_float(value)
        if number is not None:
            return number
    return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _slug(value: Any, fallback: str = "decision_reason") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or fallback


def _get_nested(source: dict[str, Any], *keys: str) -> Any:
    candidates = [
        source,
        _as_dict(source.get("final_result")),
        _as_dict(source.get("fusion")),
        _as_dict(source.get("risk")),
        _as_dict(source.get("image_info")),
        _as_dict(source.get("debug_evidence")),
        _as_dict(source.get("technical_explanation")),
    ]
    for key in keys:
        for candidate in candidates:
            if key in candidate:
                return candidate.get(key)
    return None


def _looks_like_day17(source: dict[str, Any]) -> bool:
    return DAY17_FIELDS.issubset(source.keys())


def _product_result(raw_result: Any, image_meta: dict[str, Any]) -> dict[str, Any]:
    source = _as_dict(raw_result)
    if _looks_like_day17(source):
        return source
    image_path = image_meta.get("image_path") or image_meta.get("path") or source.get("image_path")
    return build_product_output(source, image_path=str(image_path) if image_path else None, debug=True)


def _map_final_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"ai_generated", "likely_ai", "ai", "generated", "artificial"}:
        return "ai_generated"
    if label in {"real_photo", "likely_real", "real", "photo", "camera", "authentic"}:
        return "real_photo"
    return "uncertain"


def _map_risk_level(value: Any, final_label: str) -> str:
    risk = str(value or "").strip().lower()
    if risk in RISK_LEVELS:
        return risk
    if risk in {"very_high", "critical"}:
        return "high"
    if final_label == "ai_generated":
        return "high"
    if final_label == "real_photo":
        return "low"
    return "medium"


def _normalize_confidence(value: Any) -> float:
    number = _safe_float(value)
    if number is None:
        return 0.0
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(_clamp(number), 4)


def _severity(final_label: str, risk_level: str) -> str:
    if risk_level == "high" or final_label == "ai_generated":
        return "critical"
    if final_label == "uncertain" or risk_level == "medium":
        return "warning"
    return "info"


def _decision_reasons(product: dict[str, Any], final_label: str, risk_level: str) -> list[dict[str, str]]:
    raw_reasons = _as_list(product.get("decision_reason"))
    severity = _severity(final_label, risk_level)
    reasons: list[dict[str, str]] = []
    for index, item in enumerate(raw_reasons):
        if isinstance(item, dict):
            code = _slug(item.get("code"), f"reason_{index + 1}")
            message = str(item.get("message") or item.get("text") or code)
            item_severity = str(item.get("severity") or severity).lower()
        else:
            message = str(item)
            code = _slug(item, f"reason_{index + 1}")
            item_severity = severity
        if item_severity not in {"info", "warning", "critical"}:
            item_severity = severity
        reasons.append({"code": code, "message": message, "severity": item_severity})

    if not reasons:
        reasons.append(
            {
                "code": "no_decision_reason_available",
                "message": "No detector decision reason was available.",
                "severity": severity,
            }
        )
    return reasons


def _recommendation(product: dict[str, Any], final_label: str) -> dict[str, str]:
    raw = product.get("recommendation")
    default_action = {
        "ai_generated": "warn",
        "real_photo": "allow",
        "uncertain": "review",
    }[final_label]
    if isinstance(raw, dict):
        action = str(raw.get("action") or default_action).lower()
        message = str(raw.get("message") or "")
    else:
        action = default_action
        message = str(raw or "")
    if action not in RECOMMENDATION_ACTIONS:
        action = default_action
    if not message:
        message = {
            "warn": "Treat this image as high risk and request stronger provenance before use.",
            "allow": "No strong AI-generation warning was found, but use source context for high-risk scenarios.",
            "review": "Review the image manually or request the original file and additional provenance.",
        }[action]
    return {"action": action, "message": message}


def _image_contract(image_meta: dict[str, Any], raw_result: dict[str, Any]) -> dict[str, Any]:
    meta = dict(image_meta)
    path_value = meta.get("image_path") or meta.get("path") or raw_result.get("image_path")
    filename = meta.get("filename")
    if not filename and path_value:
        filename = Path(str(path_value)).name

    return {
        "filename": str(filename) if filename else None,
        "width": _safe_int_or_none(meta.get("width") or _get_nested(raw_result, "width", "original_width")),
        "height": _safe_int_or_none(meta.get("height") or _get_nested(raw_result, "height", "original_height")),
        "format": (
            str(meta.get("format") or _get_nested(raw_result, "format", "extension") or "").lower()
            or None
        ),
        "size_bytes": _safe_int_or_none(meta.get("size_bytes") or meta.get("file_size")),
    }


def _raw_score(product: dict[str, Any]) -> float | None:
    debug = _as_dict(product.get("debug_evidence"))
    return _first_float(
        debug.get("raw_score"),
        _get_nested(product, "score", "final_score", "original_score", "mean_score", "raw_score"),
    )


def _threshold(product: dict[str, Any]) -> float | None:
    debug = _as_dict(product.get("debug_evidence"))
    return _first_float(
        debug.get("threshold_used"),
        _get_nested(product, "threshold_used", "threshold", "baseline_threshold"),
    )


def _main_signals(product: dict[str, Any], reasons: list[dict[str, str]]) -> list[str]:
    debug = _as_dict(product.get("debug_evidence"))
    signals: list[str] = []
    for key in ("risk_factors", "stability_factors", "uncertainty_flags"):
        signals.extend(str(item) for item in _as_list(debug.get(key)) if item not in (None, ""))
    signals.extend(reason["code"] for reason in reasons[:3])
    deduped = list(dict.fromkeys(signals))
    return deduped


def _technical_explanation(product: dict[str, Any], reasons: list[dict[str, str]]) -> dict[str, Any]:
    raw_technical = product.get("technical_explanation")
    debug = _as_dict(product.get("debug_evidence"))
    if isinstance(raw_technical, dict):
        source = raw_technical
        score = _safe_float(source.get("score"))
        threshold_used = _safe_float(source.get("threshold_used"))
        decision_layer = str(source.get("decision_layer") or "day17_product_output_schema")
        main_signals = [str(item) for item in _as_list(source.get("main_signals"))]
    else:
        score = _raw_score(product)
        threshold_used = _threshold(product)
        decision_layer = str(debug.get("decision_layer") or "day17_product_output_schema")
        main_signals = _main_signals(product, reasons)

    return {
        "score": score,
        "threshold_used": threshold_used,
        "decision_layer": decision_layer,
        "main_signals": main_signals,
    }


def _debug_evidence(product: dict[str, Any], include_debug: bool) -> dict[str, Any]:
    if not include_debug:
        return {
            "enabled": False,
            "raw_score": None,
            "feature_summary": {},
            "consistency_checks": {},
            "format_evidence": {},
            "resolution_evidence": {},
        }

    debug = _as_dict(product.get("debug_evidence"))
    multi_resolution = _as_dict(debug.get("multi_resolution"))
    return {
        "enabled": True,
        "raw_score": _raw_score(product),
        "feature_summary": _json_safe(
            {
                "component_scores": _get_nested(product, "component_scores") or {},
                "risk_factors": _as_list(debug.get("risk_factors")),
                "stability_factors": _as_list(debug.get("stability_factors")),
                "raw_debug_evidence": debug,
            }
        ),
        "consistency_checks": _json_safe(
            {
                "uncertainty_flags": _as_list(debug.get("uncertainty_flags")),
                "multi_resolution": multi_resolution,
            }
        ),
        "format_evidence": _json_safe(
            {
                "format_info": _as_dict(debug.get("format_info")),
                "exif_info": _as_dict(debug.get("exif_info")),
            }
        ),
        "resolution_evidence": _json_safe(multi_resolution),
    }


def build_frontend_response(
    raw_result: Any,
    image_meta: dict[str, Any] | None = None,
    request_id: str | None = None,
    include_debug: bool = True,
) -> dict[str, Any]:
    """Convert detector or Day17 output into a stable frontend JSON contract."""
    image_meta = _as_dict(image_meta)
    raw_source = _as_dict(raw_result)
    product = _product_result(raw_result, image_meta)
    final_label = _map_final_label(product.get("final_label"))
    risk_level = _map_risk_level(product.get("risk_level"), final_label)
    confidence = _normalize_confidence(product.get("confidence"))
    reasons = _decision_reasons(product, final_label, risk_level)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "request_id": str(request_id or _new_request_id()),
        "data": {
            "image": _image_contract(image_meta, raw_source),
            "result": {
                "final_label": final_label,
                "risk_level": risk_level,
                "confidence": confidence,
                "decision_reason": reasons,
                "recommendation": _recommendation(product, final_label),
                "user_facing_summary": str(product.get("user_facing_summary") or ""),
                "technical_explanation": _technical_explanation(product, reasons),
                "debug_evidence": _debug_evidence(product, include_debug),
            },
        },
        "meta": {
            "processed_at": _now_iso(),
            "adapter_version": ADAPTER_VERSION,
            "model_family": MODEL_FAMILY,
            "notes": [],
        },
    }


def build_error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a stable frontend error JSON contract."""
    error_code = str(code or "INTERNAL_ERROR").upper()
    if error_code not in ERROR_CODES:
        error_code = "INTERNAL_ERROR"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "request_id": str(request_id or _new_request_id()),
        "error": {
            "code": error_code,
            "message": str(message or ""),
            "details": _json_safe(details or {}),
        },
        "data": None,
        "meta": {
            "processed_at": _now_iso(),
            "adapter_version": ADAPTER_VERSION,
        },
    }
