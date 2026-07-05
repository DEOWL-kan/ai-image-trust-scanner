from __future__ import annotations

import os
import time
from contextlib import contextmanager
from inspect import Parameter, signature
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.adapters.api_adapter import build_frontend_response
from app.detectors.registry import DetectorRegistry
from app.detectors.open_source_adapter import OpenSourceDetectorAdapter, OpenSourceDetectionResult
from app.detectors.registry import build_api_detector_results
from app.policy.evidence_policy import apply_evidence_policy
from app.detectors.c2pa_detector import analyze_c2pa_provenance
from app.pipeline.runner import run_pipeline
from app.services.audit_log import write_audit_event
from app.services import report_store
from app.services.report_store import make_report_record, save_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser() if raw else default


def _nonnegative_int_env(name: str, default: int) -> int:
    try:
        return max(0, int(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


API_REPORT_DIR = _path_env("MINERVA_API_REPORT_DIR", PROJECT_ROOT / ".tmp" / "api_reports")
C2PA_MANIFEST_DIR = _path_env("MINERVA_C2PA_MANIFEST_DIR", PROJECT_ROOT / ".tmp" / "c2pa_manifests")
C2PA_MISSING_NOTE = "No C2PA metadata was found. This does not prove the image is authentic or camera-captured."
C2PA_MISSING_DEBUG = "No readable C2PA metadata was found. Absence of C2PA is not evidence of authenticity."
C2PA_CLAIM_DECODE_NOTE = "C2PA-related data may be present, but the claim could not be decoded by the local c2patool version. This is not verified provenance."
UNVERIFIED_MARKER_DEBUG = "Unverified OpenAI/C2PA binary markers were found, but no readable C2PA manifest could be verified."
OPENAI_C2PA_REASON = "Verified OpenAI-related C2PA provenance metadata was detected."
REVIEW_TRIGGER_CONFIG_PATH = PROJECT_ROOT / "configs" / "review_trigger_config.yaml"
CROP_REVIEW_REASON = "SMOGY crop-level detector disagreement"
CROP_REVIEW_MESSAGE_ZH = "检测视角不一致，建议复核"
CROP_REVIEW_MESSAGE_EN = "Detector views disagree; review recommended."
_OPEN_SOURCE_ADAPTER = OpenSourceDetectorAdapter()
CUDA_EMPTY_CACHE_EVERY = _nonnegative_int_env("DETECTOR_CUDA_EMPTY_CACHE_EVERY", 0)
_CUDA_EMPTY_CACHE_COUNTER = 0


class _StageTimer:
    def __init__(self) -> None:
        self._started = time.perf_counter()
        self.stages: dict[str, int] = {}

    @contextmanager
    def track(self, name: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = self.stages.get(name, 0) + int((time.perf_counter() - started) * 1000)

    def payload(self) -> dict[str, Any]:
        return {
            "total_latency_ms": int((time.perf_counter() - self._started) * 1000),
            "stage_timings": dict(self.stages),
        }


class DetectionServiceError(Exception):
    """Raised when the detector cannot produce a usable API result."""


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


RUNTIME_IMAGE_DIR = _path_env("MINERVA_RUNTIME_IMAGE_DIR", PROJECT_ROOT / ".tmp" / "runtime_images")
RUNTIME_IMAGE_MAX_EDGE = _int_env("DETECTOR_RUNTIME_IMAGE_MAX_EDGE", 1536, minimum=512)
RUNTIME_IMAGE_RESIZE_ABOVE = _int_env("DETECTOR_RUNTIME_IMAGE_RESIZE_ABOVE", 2048, minimum=512)


def _text_value(value: Any, fallback: str = "") -> str:
    if value in (None, ""):
        return fallback
    if isinstance(value, list):
        rendered = "; ".join(_text_value(item, "") for item in value).strip("; ")
        return rendered or fallback
    if isinstance(value, dict):
        for key in ("message", "summary", "explanation", "action", "code"):
            if value.get(key):
                return str(value[key])
        import json

        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


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


def _api_label_from_policy(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label == "likely_ai":
        return "ai"
    if label == "likely_real":
        return "real"
    if label in {"needs_review", "review_needed", "review", "pending_review"}:
        return "uncertain"
    return "uncertain"


def _product_label(value: Any) -> str:
    label = str(value or "").strip().lower().replace("-", "_")
    if label in {"ai", "ai_generated", "likely_ai"}:
        return "ai"
    if label in {"real", "likely_real"}:
        return "real"
    if label in {"review", "needs_review", "review_needed", "pending_review"}:
        return "review_needed"
    return "uncertain"


def _product_risk(value: Any) -> str:
    risk = str(value or "").strip().lower().replace("-", "_")
    if risk in {"low", "medium", "high", "critical", "unknown"}:
        return risk
    return "unknown"


def _product_card_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    return {
        "supports_ai": "support_ai",
        "support_ai": "support_ai",
        "supports_real": "support_real",
        "support_real": "support_real",
        "conflict": "warning",
        "warning": "warning",
        "error": "error",
    }.get(status, "neutral")


def _product_card_severity(value: Any) -> str:
    severity = str(value or "").strip().lower()
    if severity in {"low", "medium", "high"}:
        return severity
    if severity in {"critical", "error"}:
        return "high"
    return "low"


def _product_layer(value: Any) -> str:
    layer = str(value or "").strip().lower()
    return {
        "provenance": "source",
        "detector": "detector",
        "metadata": "metadata",
        "forensic": "forensic",
        "policy": "policy",
    }.get(layer, "policy")


def _load_review_trigger_config() -> dict[str, Any]:
    try:
        with REVIEW_TRIGGER_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
    except OSError:
        config = {}
    config.setdefault("default_enabled", False)
    config.setdefault("default_profile", "strict_safe")
    config.setdefault("profiles", {})
    return config


def _review_trigger_profile(config: dict[str, Any], requested: str | None) -> tuple[str, dict[str, Any]]:
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    name = str(requested or config.get("default_profile") or "strict_safe").strip().lower()
    if name not in profiles and name == "balanced":
        name = "balanced_review" if "balanced_review" in profiles else name
    if name not in profiles:
        name = str(config.get("default_profile") or "strict_safe")
    profile = profiles.get(name) if isinstance(profiles.get(name), dict) else {}
    return name, profile


def review_trigger_default_profile() -> str:
    config = _load_review_trigger_config()
    return str(config.get("default_profile") or "strict_safe_plus")


def _detector_role(value: Any, detector_id: str, status: str, duplicate_of: Any = None) -> str:
    if status == "error":
        return "error"
    if status in {"disabled", "skipped"} or duplicate_of:
        return "disabled"
    role = str(value or "").strip().lower()
    if detector_id == "legacy" or role in {"baseline", "legacy"}:
        return "legacy"
    if role in {"primary", "secondary", "auxiliary", "diagnostic"}:
        return "primary" if role == "primary" else "auxiliary"
    return "auxiliary"


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


def _image_meta(path: Path, image_info: dict[str, Any], image_hash: str | None) -> dict[str, Any]:
    meta = {
        "image_hash": image_hash,
        "width": image_info.get("width") or 0,
        "height": image_info.get("height") or 0,
        "format": image_info.get("format") or path.suffix.lower().lstrip(".") or "unknown",
        "mode": image_info.get("mode") or "unknown",
    }
    try:
        from PIL import Image

        with Image.open(path) as image:
            meta["width"] = image.width
            meta["height"] = image.height
            meta["format"] = (image.format or meta["format"] or "unknown").lower()
            meta["mode"] = image.mode or meta["mode"]
    except Exception:
        pass
    return meta


def image_input_summary(path: Path, filename: str, mime_type: str | None = None) -> dict[str, Any]:
    image_hash = _sha256(path)
    meta = _image_meta(path, {}, image_hash)
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    return {
        "filename": filename,
        "sha256": image_hash,
        "mime_type": mime_type or f"image/{meta.get('format') or path.suffix.lower().lstrip('.') or 'unknown'}",
        "width": int(meta.get("width") or 0),
        "height": int(meta.get("height") or 0),
        "file_size_bytes": int(file_size or 0),
    }


def _prepare_runtime_image(path: Path) -> tuple[Path, dict[str, Any]]:
    """Create a bounded-size RGB runtime copy for detector/forensic work.

    The original file remains the source of truth for hash, file size, metadata,
    and C2PA provenance. This only avoids repeatedly decoding huge camera images
    for model and FFT-style feature extraction.
    """
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            longest = max(width, height)
            if longest <= RUNTIME_IMAGE_RESIZE_ABOVE:
                return path, {"runtime_resized": False, "runtime_image_path": str(path), "original_width": width, "original_height": height}
            if image.mode in {"RGBA", "LA"}:
                alpha = image.getchannel("A")
                rgb = Image.new("RGB", image.size, (255, 255, 255))
                rgb.paste(image.convert("RGB"), mask=alpha)
                image = rgb
            else:
                image = image.convert("RGB")
            image.thumbnail((RUNTIME_IMAGE_MAX_EDGE, RUNTIME_IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
            RUNTIME_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            runtime_path = RUNTIME_IMAGE_DIR / f"{path.stem}_{uuid4().hex[:10]}_runtime.jpg"
            image.save(runtime_path, format="JPEG", quality=92, optimize=True)
            return runtime_path, {
                "runtime_resized": True,
                "runtime_image_path": str(runtime_path),
                "original_width": width,
                "original_height": height,
                "runtime_width": image.width,
                "runtime_height": image.height,
                "runtime_max_edge": RUNTIME_IMAGE_MAX_EDGE,
            }
    except Exception as exc:
        return path, {"runtime_resized": False, "runtime_image_path": str(path), "runtime_resize_error": str(exc)}


def _run_pipeline_for_api(path: Path, runtime_path: Path) -> dict[str, Any]:
    try:
        params = signature(run_pipeline).parameters.values()
        supports_new_api = any(param.kind == Parameter.VAR_KEYWORD for param in params)
        if not supports_new_api:
            param_names = {param.name for param in params}
            supports_new_api = {"write_output", "analysis_image_path"}.issubset(param_names)
    except (TypeError, ValueError):
        supports_new_api = True

    if supports_new_api:
        return run_pipeline(path, output_dir=API_REPORT_DIR, write_output=False, analysis_image_path=runtime_path)
    return run_pipeline(path, output_dir=API_REPORT_DIR)


def _cleanup_runtime_image(runtime_path: Path, original_path: Path) -> None:
    if runtime_path == original_path:
        return
    try:
        runtime_path.unlink(missing_ok=True)
    except OSError:
        pass


def build_product_single_response(
    detection_data: dict[str, Any],
    *,
    input_summary: dict[str, Any] | None = None,
    total_latency_ms: int | None = None,
) -> dict[str, Any]:
    policy_result = detection_data.get("policy_result") if isinstance(detection_data.get("policy_result"), dict) else {}
    detector_results = detection_data.get("detector_results") if isinstance(detection_data.get("detector_results"), list) else []
    detector_summary = detection_data.get("detector_summary") if isinstance(detection_data.get("detector_summary"), dict) else {}
    cards = policy_result.get("evidence_cards") if isinstance(policy_result.get("evidence_cards"), list) else []
    product_cards = []
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        product_cards.append(
            {
                "id": str(card.get("id") or f"evidence_{index + 1}"),
                "layer": _product_layer(card.get("layer") or card.get("type")),
                "title": str(card.get("title") or "Evidence"),
                "status": _product_card_status(card.get("status")),
                "severity": _product_card_severity(card.get("severity")),
                "summary": str(card.get("summary") or ""),
                "details": card.get("details") if isinstance(card.get("details"), dict) else {},
                "weight": _clamp_confidence(card.get("weight")) if card.get("weight") is not None else 0.0,
            }
        )

    detectors = []
    for item in detector_results:
        if not isinstance(item, dict):
            continue
        detector_id = str(item.get("detector_id") or item.get("name") or "unknown")
        status = str(item.get("status") or "").lower()
        error = item.get("error") if isinstance(item.get("error"), dict) else {}
        label = str(item.get("predicted_label") or item.get("label") or "").lower()
        disabled_reason = None
        notes = ((item.get("debug") or {}).get("notes") if isinstance(item.get("debug"), dict) else []) or []
        if item.get("duplicate_of"):
            disabled_reason = str(item.get("reason_disabled") or item.get("duplicate_of"))
        elif status == "disabled":
            disabled_reason = "OPEN_SOURCE_DETECTOR_ENABLED is false" if detector_id == "dima806" else "detector disabled"
        elif status == "skipped":
            disabled_reason = "; ".join(str(note) for note in notes) or "detector skipped"
        if status == "error" or error.get("message"):
            label = "error"
        elif status == "disabled":
            label = "disabled"
        elif status == "skipped":
            label = "uncertain"
        elif label not in {"ai", "real", "uncertain"}:
            label = "ai" if _clamp_confidence(item.get("ai_score")) >= _clamp_confidence(item.get("threshold"),) else "real"
        # P1-c: surface whether a fine-tuned LoRA/PEFT adapter is loaded on top of
        # the base HF weights for this detector. Read from the nested HF-runtime
        # summary the registry stores in debug.raw_output. Default False so older
        # detectors / non-HF paths stay unchanged.
        raw_summary = ((item.get("debug") or {}).get("raw_output") or {}).get("raw_output_summary") if isinstance(item.get("debug"), dict) else None
        fine_tuned = bool(isinstance(raw_summary, dict) and raw_summary.get("peft_loaded"))
        adapter_path = str(raw_summary.get("peft_adapter_path") or "") if isinstance(raw_summary, dict) and raw_summary.get("peft_adapter_path") else ""
        detectors.append(
            {
                "name": detector_id,
                "role": _detector_role(item.get("role"), detector_id, status, item.get("duplicate_of")),
                "ai_score": None if status in {"disabled", "skipped", "error"} else _clamp_confidence(item.get("ai_score")),
                "threshold": _clamp_confidence(item.get("threshold"),),
                "label": label if label in {"ai", "real", "uncertain", "error", "disabled"} else "uncertain",
                "latency_ms": item.get("latency_ms"),
                "error": error.get("message") if status == "error" and error.get("message") else None,
                "version": str(item.get("detector_version") or item.get("model_version") or "unknown"),
                "status": status or None,
                "disabled_reason": disabled_reason,
                "fine_tuned": fine_tuned,
                "adapter_path": adapter_path,
            }
        )

    policy_label = policy_result.get("final_label")
    final_label = _product_label(policy_label if policy_label else detection_data.get("final_label"))
    risk_level = _product_risk(policy_result.get("risk_level") if policy_result.get("risk_level") else detection_data.get("risk_level"))
    review_status = str(detection_data.get("review_status") or policy_result.get("review_status") or "unreviewed")
    review_required = bool(final_label in {"ai", "uncertain", "review_needed"} or risk_level in {"medium", "high", "critical"} or review_status == "pending_review")
    reason = _text_value(policy_result.get("decision_reason") if policy_result.get("decision_reason") else detection_data.get("decision_reason"), "No decision reason was returned.")
    recommendation = _text_value(policy_result.get("recommendation") if policy_result.get("recommendation") else detection_data.get("recommendation"), "")
    review_triggers = detection_data.get("review_triggers")
    if not isinstance(review_triggers, list):
        review_triggers = policy_result.get("review_triggers") if isinstance(policy_result.get("review_triggers"), list) else []
    input_payload = input_summary or {
        "filename": detection_data.get("filename") or "uploaded_image",
        "sha256": detection_data.get("file_sha256"),
        "mime_type": "unknown",
        "width": 0,
        "height": 0,
        "file_size_bytes": 0,
    }
    rules_triggered = []
    if reason:
        rules_triggered.append(reason)
    policy_debug = policy_result.get("debug_evidence") if isinstance(policy_result.get("debug_evidence"), dict) else {}
    detector_groups = policy_debug.get("detector_groups") if isinstance(policy_debug.get("detector_groups"), dict) else {}
    for key in ("ai_like", "real_like", "errors", "primary_errors", "auxiliary_errors", "conflicts"):
        value = detector_groups.get(key)
        if value:
            rules_triggered.append(f"{key}: {value}")
    if "has_active_primary" in detector_groups:
        rules_triggered.append(f"has_active_primary: {detector_groups.get('has_active_primary')}")
    timing_payload = detection_data.get("timing") if isinstance(detection_data.get("timing"), dict) else {}

    return {
        "report_id": detection_data.get("report_id") or detection_data.get("id"),
        "input": input_payload,
        "result": {
            "final_label": final_label,
            "risk_level": risk_level,
            "confidence": _clamp_confidence(policy_result.get("confidence") if policy_result.get("confidence") is not None else detection_data.get("confidence")),
            "decision_reason": reason,
            "recommendation": recommendation,
            "user_facing_summary": str(policy_result.get("user_facing_summary") or detection_data.get("user_facing_summary") or ""),
            "technical_explanation": _text_value(policy_result.get("technical_explanation") if policy_result.get("technical_explanation") else detection_data.get("technical_explanation"), ""),
        },
        "evidence_cards": product_cards,
        "review_triggers": review_triggers,
        "detectors": detectors,
        "policy": {
            "policy_version": str(detection_data.get("policy_version") or policy_result.get("policy_version") or "unknown"),
            "policy_profile": str(detection_data.get("policy_profile") or policy_result.get("policy_profile") or "unknown"),
            "threshold_profile": str(policy_result.get("threshold_profile") or detection_data.get("threshold_profile") or detector_summary.get("threshold_profile") or "unknown"),
            "detector_version": str(detection_data.get("detector_version") or detector_summary.get("registry_version") or report_store.DETECTOR_VERSION),
            "model_version": str(detection_data.get("model_version") or detector_summary.get("model_adapter_version") or report_store.MODEL_VERSION),
            "rules_triggered": rules_triggered,
            "detector_runtime_mode": str(detector_summary.get("detector_runtime_mode") or "unknown"),
            "primary_detector_available": bool(detector_summary.get("active_primary_valid")),
            "primary_detector_thresholds": policy_result.get("primary_detector_thresholds") or detection_data.get("primary_detector_thresholds") or {},
            "review_trigger_profile": str(detection_data.get("review_trigger_profile") or policy_result.get("review_trigger_profile") or review_trigger_default_profile()),
        },
        "review": {
            "review_status": review_status,
            "review_required": review_required,
            "review_reason": next((str(item.get("reason")) for item in review_triggers if isinstance(item, dict) and item.get("triggered")), reason if review_required else ""),
        },
        "timing": {
            "total_latency_ms": int(total_latency_ms if total_latency_ms is not None else 0),
            "stage_timings": timing_payload.get("stage_timings") if isinstance(timing_payload.get("stage_timings"), dict) else {},
        },
        "compat": detection_data,
    }


def build_product_error_response(
    *,
    filename: str,
    message: str,
    code: str = "DETECTION_FAILED",
    input_summary: dict[str, Any] | None = None,
    total_latency_ms: int = 0,
) -> dict[str, Any]:
    return {
        "report_id": None,
        "input": input_summary
        or {
            "filename": filename,
            "sha256": None,
            "mime_type": "unknown",
            "width": 0,
            "height": 0,
            "file_size_bytes": 0,
        },
        "result": {
            "final_label": "review_needed",
            "risk_level": "unknown",
            "confidence": 0.0,
            "decision_reason": message,
            "recommendation": "Retry detection or send the image to manual review.",
            "user_facing_summary": "Detection could not be completed, but the failure is reviewable.",
            "technical_explanation": f"{code}: {message}",
        },
        "evidence_cards": [
            {
                "id": "detector_error",
                "layer": "detector",
                "title": "Detector error",
                "status": "error",
                "severity": "high",
                "summary": message,
                "details": {"code": code},
                "weight": 0.0,
            }
        ],
        "review_triggers": [],
        "detectors": [
            {
                "name": "local_single_detection",
                "role": "error",
                "ai_score": 0.0,
                "threshold": 0.0,
                "label": "error",
                "latency_ms": total_latency_ms,
                "error": message,
                "version": report_store.DETECTOR_VERSION,
            }
        ],
        "policy": {
            "policy_version": "evidence_policy_v1",
            "detector_version": report_store.DETECTOR_VERSION,
            "model_version": report_store.MODEL_VERSION,
            "rules_triggered": ["detector_error_to_review"],
        },
        "review": {
            "review_status": "pending_review",
            "review_required": True,
            "review_reason": message,
        },
        "timing": {
            "total_latency_ms": total_latency_ms,
        },
        "error": {"code": code, "message": message},
    }


def _append_decision_reason(value: Any, message: str) -> Any:
    if isinstance(value, list):
        if any(message in str(item) for item in value):
            return value
        return [
            *value,
            {
                "code": "openai_c2pa_provenance",
                "message": message,
                "severity": "critical",
            },
        ]
    if value in (None, ""):
        return [{"code": "openai_c2pa_provenance", "message": message, "severity": "critical"}]
    if message in str(value):
        return value
    return [value, {"code": "openai_c2pa_provenance", "message": message, "severity": "critical"}]


def _technical_with_provenance_note(value: Any, note: str) -> Any:
    if isinstance(value, dict):
        notes = value.get("provenance_notes")
        if isinstance(notes, list):
            merged = notes if note in notes else [*notes, note]
        elif notes:
            merged = [str(notes), note] if note not in str(notes) else [str(notes)]
        else:
            merged = [note]
        return {**value, "provenance_note": note, "provenance_notes": merged}
    text = str(value or "").strip()
    if note in text:
        return text
    return f"{text}\n{note}".strip()


def _debug_with_provenance(value: Any, provenance: dict[str, Any]) -> dict[str, Any]:
    debug = value if isinstance(value, dict) else {"raw_debug_evidence": value}
    notes = debug.get("provenance_notes")
    if not isinstance(notes, list):
        notes = [str(notes)] if notes else []
    diagnostics = provenance.get("diagnostics") if isinstance(provenance.get("diagnostics"), dict) else {}
    markers = provenance.get("unverified_markers") if isinstance(provenance.get("unverified_markers"), dict) else {}
    status = diagnostics.get("c2pa_probe_status")
    has_unverified_marker = any(
        bool(markers.get(key))
        for key in ("binary_c2pa_marker_found", "binary_openai_marker_found", "binary_gpt_image_marker_found")
    )
    if has_unverified_marker and UNVERIFIED_MARKER_DEBUG not in notes:
        notes.append(UNVERIFIED_MARKER_DEBUG)
    if status == "no_manifest" and C2PA_MISSING_DEBUG not in notes:
        notes.append(C2PA_MISSING_DEBUG)
    if status == "claim_cbor_decode_error" and C2PA_CLAIM_DECODE_NOTE not in notes:
        notes.append(C2PA_CLAIM_DECODE_NOTE)
    return {**debug, "provenance": provenance, "provenance_notes": notes}


def _open_source_evidence(result: OpenSourceDetectionResult) -> dict[str, Any]:
    return {
        "enabled": result.enabled,
        "available": result.available,
        "model_id": result.model_id,
        "label": result.open_source_label,
        "confidence": result.open_source_confidence,
        "threshold": result.open_source_threshold,
        "latency_ms": result.open_source_latency_ms,
        "error": result.open_source_error,
        "raw_labels": result.raw_labels,
    }


def _apply_open_source_signal(data: dict[str, Any], image_path: Path) -> dict[str, Any]:
    try:
        result = _OPEN_SOURCE_ADAPTER.predict(image_path)
    except Exception as exc:
        result = OpenSourceDetectionResult(
            enabled=True,
            available=False,
            model_id=None,
            open_source_score=None,
            open_source_label="error",
            open_source_confidence=None,
            open_source_threshold=0.5,
            open_source_latency_ms=None,
            open_source_error=str(exc),
            raw_labels=[],
        )
    evidence = _open_source_evidence(result)
    debug = data.get("debug_evidence") if isinstance(data.get("debug_evidence"), dict) else {}
    data["open_source_score"] = result.open_source_score
    data["open_source_evidence"] = evidence
    data["debug_evidence"] = {**debug, "open_source_evidence": evidence}
    return data


def _apply_provenance_policy(data: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    data["provenance"] = provenance
    data["debug_evidence"] = _debug_with_provenance(data.get("debug_evidence"), provenance)
    verified = provenance.get("verified") if isinstance(provenance.get("verified"), dict) else {}
    diagnostics = provenance.get("diagnostics") if isinstance(provenance.get("diagnostics"), dict) else {}
    status = diagnostics.get("c2pa_probe_status")

    if status == "no_manifest":
        data["technical_explanation"] = _technical_with_provenance_note(
            data.get("technical_explanation"),
            C2PA_MISSING_NOTE,
        )
    elif status == "claim_cbor_decode_error":
        data["technical_explanation"] = _technical_with_provenance_note(
            data.get("technical_explanation"),
            C2PA_CLAIM_DECODE_NOTE,
        )

    if verified.get("openai_provenance_detected") is True and verified.get("c2pa_readable") is True:
        data["final_label"] = "ai_generated"
        data["risk_level"] = "high"
        data["confidence"] = max(_clamp_confidence(data.get("confidence")), 0.95)
        data["decision_reason"] = _append_decision_reason(data.get("decision_reason"), OPENAI_C2PA_REASON)
        data["technical_explanation"] = _technical_with_provenance_note(
            data.get("technical_explanation"),
            OPENAI_C2PA_REASON,
        )
    return data


def _resize_long_edge(image: Any, long_edge: int = 512) -> Any:
    width, height = image.size
    scale = long_edge / max(width, height, 1)
    if scale <= 0:
        return image
    from PIL import Image

    return image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)


def _center_and_corner_crops(image: Any, size: int = 224) -> list[tuple[str, Any]]:
    image = _resize_long_edge(image, 512)
    width, height = image.size
    if width < size or height < size:
        from PIL import Image

        image = image.resize((max(size, width), max(size, height)), Image.Resampling.LANCZOS)
        width, height = image.size
    left = max(0, (width - size) // 2)
    top = max(0, (height - size) // 2)
    positions = {
        "center": (left, top),
        "top_left": (0, 0),
        "top_right": (max(0, width - size), 0),
        "bottom_left": (0, max(0, height - size)),
        "bottom_right": (max(0, width - size), max(0, height - size)),
    }
    crops = []
    for name, (x, y) in positions.items():
        crops.append((name, image.crop((x, y, x + size, y + size))))
    return crops


def _crop_label(score: float) -> str:
    if score >= 0.05:
        return "ai"
    if score >= 0.02:
        return "review"
    return "real"


def _smogy_crop_disagreement(image_path: Path) -> dict[str, Any]:
    import time
    from PIL import Image

    started = time.perf_counter()
    adapter = DetectorRegistry().adapter_for("smogy")
    crop_scores: dict[str, float] = {}
    crop_labels: dict[str, str] = {}
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        crops = _center_and_corner_crops(image)
        crop_results = adapter.predict_many([crop for _, crop in crops])
        for (crop_name, _crop), detector_result in zip(crops, crop_results):
            result = detector_result.to_dict()
            if result.get("status") != "ok":
                error = result.get("error") if isinstance(result.get("error"), dict) else {}
                raise DetectionServiceError(str(error.get("message") or f"SMOGY crop {crop_name} returned {result.get('status')}"))
            raw = ((result.get("debug") or {}).get("raw_output") or {}) if isinstance(result.get("debug"), dict) else {}
            summary = raw.get("raw_output_summary") if isinstance(raw.get("raw_output_summary"), dict) else {}
            score = summary.get("ai_score_full_precision")
            if score is None:
                score = result.get("ai_score")
            score_f = float(score or 0.0)
            crop_scores[crop_name] = score_f
            crop_labels[crop_name] = _crop_label(score_f)
    values = list(crop_scores.values())
    max_score = max(values) if values else 0.0
    min_score = min(values) if values else 0.0
    return {
        "crop_scores": crop_scores,
        "crop_labels": crop_labels,
        "max_crop_score": max_score,
        "min_crop_score": min_score,
        "disagreement_score": max_score - min_score,
        "crop_labels_disagree": len(set(crop_labels.values())) > 1,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _should_run_crop_review(policy_result: dict[str, Any], profile: dict[str, Any]) -> bool:
    if not bool(profile.get("enabled", True)):
        return False
    final_label = _api_label_from_policy(policy_result.get("final_label"))
    if final_label != str(profile.get("require_original_final_label") or "real"):
        return False
    confidence = _clamp_confidence(policy_result.get("confidence"))
    max_confidence = _clamp_confidence(profile.get("max_original_confidence") if profile.get("max_original_confidence") is not None else 0.70)
    risk = str(policy_result.get("risk_level") or "unknown").lower()
    return confidence <= max_confidence or (bool(profile.get("allow_non_low_risk", True)) and risk != "low")


def _crop_review_fast_skip_details(policy_result: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any] | None:
    """Skip expensive crop review only for clearly low-risk real outputs."""

    try:
        score_floor = float(profile.get("min_primary_score_for_crop_review") or 0.0)
    except (TypeError, ValueError):
        score_floor = 0.0
    if score_floor <= 0.0:
        return None

    debug = policy_result.get("debug_evidence") if isinstance(policy_result.get("debug_evidence"), dict) else {}
    groups = debug.get("detector_groups") if isinstance(debug.get("detector_groups"), dict) else {}
    try:
        primary_score = float(groups.get("primary_detector_score"))
    except (TypeError, ValueError):
        return None

    risk = str(policy_result.get("risk_level") or "unknown").lower()
    voting_ai_like = groups.get("voting_ai_like") if isinstance(groups.get("voting_ai_like"), list) else []
    conflicts = groups.get("conflicts") if isinstance(groups.get("conflicts"), list) else []
    if primary_score < score_floor and risk == "low" and not voting_ai_like and not conflicts:
        return {
            "profile": str(profile.get("name") or ""),
            "skip_reason": "primary_score_below_crop_review_floor",
            "primary_detector_score": round(primary_score, 6),
            "min_primary_score_for_crop_review": score_floor,
            "risk_level": risk,
        }
    return None


def _review_trigger_payload(triggered: bool, details: dict[str, Any], enabled: bool = True, error: str | None = None) -> dict[str, Any]:
    return {
        "id": "smogy_crop_disagreement_review",
        "enabled": enabled,
        "triggered": bool(triggered),
        "severity": "medium" if triggered else "low",
        "reason": CROP_REVIEW_REASON,
        "user_message_zh": CROP_REVIEW_MESSAGE_ZH,
        "user_message_en": CROP_REVIEW_MESSAGE_EN,
        "details": details,
        "error": error,
    }


def _apply_safe_review_routing(data: dict[str, Any], image_path: Path, requested_profile: str | None) -> dict[str, Any]:
    policy_result = data.get("policy_result") if isinstance(data.get("policy_result"), dict) else {}
    config = _load_review_trigger_config()
    trigger_profile_name, trigger_profile = _review_trigger_profile(config, requested_profile)
    enabled = bool(config.get("default_enabled", False)) and bool(trigger_profile.get("enabled", False))
    data["review_trigger_profile"] = trigger_profile_name
    data.setdefault("review_triggers", [])
    if not enabled:
        data["review_triggers"].append(_review_trigger_payload(False, {"profile": trigger_profile_name, "skip_reason": "review_trigger_disabled"}, enabled=False))
        return data
    if not _should_run_crop_review(policy_result, trigger_profile):
        data["review_triggers"].append(_review_trigger_payload(False, {"profile": trigger_profile_name, "skip_reason": "not_eligible_for_crop_review"}, enabled=True))
        return data
    fast_skip = _crop_review_fast_skip_details(policy_result, {**trigger_profile, "name": trigger_profile_name})
    if fast_skip:
        data["review_triggers"].append(_review_trigger_payload(False, fast_skip, enabled=True))
        return data

    try:
        details = _smogy_crop_disagreement(image_path)
    except Exception as exc:
        warning = _review_trigger_payload(False, {"profile": trigger_profile_name}, enabled=True, error=str(exc))
        data["review_triggers"].append(warning)
        cards = policy_result.get("evidence_cards") if isinstance(policy_result.get("evidence_cards"), list) else []
        cards.append(
            {
                "id": "review_trigger_smogy_crop_error",
                "type": "policy",
                "title": "Crop disagreement review trigger unavailable",
                "status": "conflict",
                "severity": "low",
                "summary": "Crop-level review routing could not run; primary detection result is unchanged.",
                "details": {"error": str(exc), "profile": trigger_profile_name},
            }
        )
        policy_result["evidence_cards"] = cards
        return data

    disagreement_threshold = float(trigger_profile.get("disagreement_threshold") or 0.15)
    max_score_threshold = float(trigger_profile.get("max_crop_score_threshold") or 0.05)
    triggered = bool(
        details["disagreement_score"] >= disagreement_threshold
        or (bool(trigger_profile.get("use_max_score", False)) and details["max_crop_score"] >= max_score_threshold)
        or (bool(trigger_profile.get("crop_label_disagree", True)) and details["crop_labels_disagree"] and details["max_crop_score"] >= max_score_threshold)
    )
    details = {**details, "profile": trigger_profile_name, "disagreement_threshold": disagreement_threshold, "max_crop_score_threshold": max_score_threshold}
    data["review_triggers"].append(_review_trigger_payload(triggered, details, enabled=True))
    if not triggered:
        return data

    cards = policy_result.get("evidence_cards") if isinstance(policy_result.get("evidence_cards"), list) else []
    cards.append(
        {
            "id": "review_trigger_smogy_crop_disagreement",
            "type": "policy",
            "layer": "policy",
            "title": "检测视角不一致",
            "status": "warning",
            "severity": "medium",
            "summary": "建议复核，不作为 AI 直接判定。",
            "details": {
                "reason": CROP_REVIEW_REASON,
                "user_message_zh": CROP_REVIEW_MESSAGE_ZH,
                "user_message_en": CROP_REVIEW_MESSAGE_EN,
                **details,
            },
        }
    )
    original = {
        "final_label": policy_result.get("final_label"),
        "risk_level": policy_result.get("risk_level"),
        "confidence": policy_result.get("confidence"),
        "review_status": policy_result.get("review_status"),
        "decision_reason": policy_result.get("decision_reason"),
    }
    policy_result["original_before_review_trigger"] = original
    policy_result["final_label"] = "needs_review"
    policy_result["risk_level"] = "medium"
    policy_result["confidence"] = min(_clamp_confidence(policy_result.get("confidence") if policy_result.get("confidence") is not None else 0.45), 0.7)
    policy_result["review_status"] = "pending_review"
    policy_result["decision_reason"] = f"{policy_result.get('decision_reason') or ''}; {CROP_REVIEW_REASON}".strip("; ")
    policy_result["user_facing_summary"] = CROP_REVIEW_MESSAGE_ZH
    policy_result["technical_explanation"] = f"{policy_result.get('technical_explanation') or ''} {CROP_REVIEW_REASON}; this routes to review and does not classify AI.".strip()
    policy_result["recommendation"] = {
        "action": "manual_review",
        "message": "建议人工复核或结合来源证明；该触发器不作为 AI 直接判定。",
    }
    policy_result["evidence_cards"] = cards
    policy_result["review_triggers"] = data["review_triggers"]
    data["policy_result"] = policy_result
    return data


def _detect_image_for_api_with_runtime(
    *,
    path: Path,
    runtime_path: Path,
    runtime_info: dict[str, Any],
    timer: _StageTimer,
    filename: str,
    source_type: str,
    policy_profile: str | None = None,
) -> dict[str, Any]:
    with timer.track("legacy_pipeline"):
        report = _run_pipeline_for_api(path, runtime_path)
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
        "image_path": str(path),
        "final_label": final_label,
        "risk_level": risk_level,
        "confidence": _clamp_confidence(result.get("confidence")),
        "decision_reason": result.get("decision_reason") or [],
        "recommendation": result.get("recommendation") or {},
        "user_facing_summary": str(result.get("user_facing_summary") or ""),
        "technical_explanation": result.get("technical_explanation") or {},
        "debug_evidence": result.get("debug_evidence") or {},
    }
    data["runtime_image"] = runtime_info
    data["analysis_image_path"] = str(runtime_path)
    data["detector_image_path"] = str(path)
    image_hash = _sha256(path)
    with timer.track("c2pa"):
        provenance = analyze_c2pa_provenance(
            path,
            timeout=_int_env("C2PA_PROVENANCE_TIMEOUT_SECONDS", 2),
            manifest_dir=C2PA_MANIFEST_DIR,
        )
    data = _apply_provenance_policy(data, provenance)
    with timer.track("open_source_adapter"):
        data = _apply_open_source_signal(data, path)
    with timer.track("detector_registry"):
        detector_results, detector_summary = build_api_detector_results(
            api_data=data,
            image_hash=image_hash,
            image_meta=_image_meta(path, image_info, image_hash),
        )
    data["detector_results"] = detector_results
    data["detector_summary"] = detector_summary
    data["detector_result_schema_version"] = detector_summary["schema_version"]
    data["detector_registry_version"] = detector_summary["registry_version"]
    data["threshold_profile"] = detector_summary["threshold_profile"]
    data["model_adapter_version"] = detector_summary["model_adapter_version"]
    with timer.track("evidence_policy"):
        policy_result = apply_evidence_policy(
            detector_results,
            metadata_result=report.get("metadata_result") if isinstance(report.get("metadata_result"), dict) else {},
            provenance_result=provenance,
            forensic_result=report.get("forensic_result") if isinstance(report.get("forensic_result"), dict) else {},
            context={
                "filename": filename,
                "source_type": source_type,
                "detector_summary": detector_summary,
                "policy_profile": policy_profile,
            },
            policy_profile=policy_profile,
        )
    data["policy_result"] = policy_result
    with timer.track("review_routing"):
        data = _apply_safe_review_routing(data, path, policy_profile)
    policy_result = data["policy_result"]
    data["policy_version"] = policy_result["policy_version"]
    data["policy_profile"] = policy_result.get("policy_profile")
    data["threshold_profile"] = policy_result.get("threshold_profile") or data.get("threshold_profile")
    data["primary_detector_thresholds"] = policy_result.get("primary_detector_thresholds")
    data["policy_snapshot"] = policy_result["policy_snapshot"]
    policy_final_label = _api_label_from_policy(policy_result.get("final_label"))
    policy_risk = str(policy_result.get("risk_level") or "unknown").lower()
    data["policy_output"] = {
        "final_label": policy_final_label,
        "risk_level": policy_risk if policy_risk in {"low", "medium", "high"} else "medium",
        "confidence": _clamp_confidence(policy_result.get("confidence")),
        "decision_reason": policy_result.get("decision_reason") or data.get("decision_reason"),
        "recommendation": policy_result.get("recommendation") or data.get("recommendation"),
        "user_facing_summary": policy_result.get("user_facing_summary") or data.get("user_facing_summary"),
        "technical_explanation": policy_result.get("technical_explanation") or data.get("technical_explanation"),
    }
    data.update(data["policy_output"])
    data["review_status"] = policy_result.get("review_status") or data.get("review_status")
    report_detection_data = {
        **data,
        **data["policy_output"],
    }
    with timer.track("report_save"):
        record = make_report_record(
            detection_data=report_detection_data,
            source_type=source_type,
            image_path=str(path),
            file_sha256=image_hash,
            report_payload={
                "frontend_response": frontend_response,
                "api_data": data,
                "raw_report": report,
            },
            export_payload=report_detection_data,
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
    # Optional GPU cache hygiene. Keep it off by default for API latency.
    # Enable periodic cleanup only when a long-running service shows allocator pressure.
    global _CUDA_EMPTY_CACHE_COUNTER
    with timer.track("cuda_cache_cleanup"):
        if CUDA_EMPTY_CACHE_EVERY > 0:
            _CUDA_EMPTY_CACHE_COUNTER += 1
            if _CUDA_EMPTY_CACHE_COUNTER % CUDA_EMPTY_CACHE_EVERY == 0:
                try:  # noqa: SIM105
                    import torch  # type: ignore

                    if torch.cuda.is_available():  # type: ignore[attr-defined]
                        torch.cuda.empty_cache()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    pass
    data["timing"] = timer.payload()
    return data


def detect_image_for_api(
    image_path: str,
    filename: str,
    source_type: str = "single",
    policy_profile: str | None = None,
) -> dict[str, Any]:
    """Run the existing detector and return the Day19 API data payload.

    The detection path intentionally reuses the Day18 frontend adapter, then
    maps its result into the compact HTTP envelope requested for Day19.
    """
    path = Path(image_path)
    timer = _StageTimer()
    with timer.track("prepare_runtime_image"):
        runtime_path, runtime_info = _prepare_runtime_image(path)
    try:
        return _detect_image_for_api_with_runtime(
            path=path,
            runtime_path=runtime_path,
            runtime_info=runtime_info,
            timer=timer,
            filename=filename,
            source_type=source_type,
            policy_profile=policy_profile,
        )
    finally:
        _cleanup_runtime_image(runtime_path, path)
