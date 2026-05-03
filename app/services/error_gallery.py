from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
DAY23_DIR = DATA_ROOT / "benchmark_outputs" / "day23"
BENCHMARK_RESULTS_PATH = DAY23_DIR / "day23_benchmark_results.json"
BENCHMARK_SUMMARY_PATH = DAY23_DIR / "day23_benchmark_summary.json"
REVIEW_NOTES_PATH = PROJECT_ROOT / "reports" / "day24_error_review_notes.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ERROR_TYPES = {"all", "fp", "fn", "uncertain", "tp", "tn"}
SORT_MODES = {"confidence_desc", "confidence_asc", "score_desc", "score_asc", "filename"}
MANUAL_TAGS = {
    "format_bias",
    "resolution_flip",
    "no_exif_jpeg",
    "low_texture",
    "high_compression",
    "realistic_ai",
    "unknown",
}


class ErrorGalleryError(Exception):
    """Base class for error gallery adapter errors."""


class ErrorItemNotFound(ErrorGalleryError):
    """Raised when a gallery item id does not exist."""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_default(value: Any) -> str:
    return str(value)


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _get_nested(source: Any, path: str, default: Any = None) -> Any:
    current = source
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _first_value(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = _get_nested(source, key) if "." in key else source.get(key)
        if value not in (None, ""):
            return value
    return default


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 1.0 < number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 4)


def _normalize_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"ai", "ai_generated", "likely_ai", "generated", "artificial", "synthetic"}:
        return "ai"
    if label in {"real", "real_photo", "likely_real", "photo", "camera", "authentic"}:
        return "real"
    if label in {"uncertain", "unknown", "review", "needs_review", "inconclusive"}:
        return "uncertain"
    return "unknown"


def _is_uncertain_record(record: dict[str, Any], predicted_label: str) -> bool:
    if predicted_label == "uncertain":
        return True
    if bool(record.get("is_uncertain")):
        return True
    risk_or_decision = " ".join(
        str(value or "").lower()
        for value in (
            record.get("risk_level"),
            record.get("decision"),
            record.get("decision_label"),
            record.get("status"),
        )
    )
    return "uncertain" in risk_or_decision or "inconclusive" in risk_or_decision


def classify_error_type(true_label: Any, predicted_label: Any, record: dict[str, Any] | None = None) -> str:
    record = record or {}
    true_norm = _normalize_label(true_label)
    pred_norm = _normalize_label(predicted_label)
    if _is_uncertain_record(record, pred_norm):
        return "UNCERTAIN"
    if true_norm == "real" and pred_norm == "ai":
        return "FP"
    if true_norm == "ai" and pred_norm == "real":
        return "FN"
    if true_norm == "ai" and pred_norm == "ai":
        return "TP"
    if true_norm == "real" and pred_norm == "real":
        return "TN"
    return "UNCERTAIN"


def _resolve_image_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    raw = Path(str(value))
    path = raw if raw.is_absolute() else PROJECT_ROOT / raw
    try:
        resolved = path.resolve()
        resolved.relative_to(DATA_ROOT.resolve())
    except (OSError, ValueError):
        return None
    if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    return resolved


def is_safe_data_image_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved.relative_to(DATA_ROOT.resolve())
    except (OSError, ValueError):
        return False
    return resolved.suffix.lower() in IMAGE_EXTENSIONS


def _image_url(path: Path | None) -> str | None:
    if not path or not is_safe_data_image_path(path):
        return None
    relative = path.resolve().relative_to(DATA_ROOT.resolve()).as_posix()
    return f"/media/{quote(relative)}"


def _relative_source_folder(path: Path | None) -> str:
    if not path:
        return "unknown"
    try:
        return path.parent.resolve().relative_to(DATA_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path.parent.name or "unknown"


def _extract_width_height(record: dict[str, Any]) -> tuple[int | None, int | None]:
    width = _first_value(
        record,
        "width",
        "image_width",
        "image_info.width",
        "debug_evidence.format_info.width",
        "debug_evidence.raw_debug_evidence.format_info.width",
        "debug_evidence.feature_summary.raw_debug_evidence.format_info.width",
        "debug_evidence.raw_result.image_info.width",
        "debug_evidence.feature_summary.raw_debug_evidence.raw_result.image_info.width",
    )
    height = _first_value(
        record,
        "height",
        "image_height",
        "image_info.height",
        "debug_evidence.format_info.height",
        "debug_evidence.raw_debug_evidence.format_info.height",
        "debug_evidence.feature_summary.raw_debug_evidence.format_info.height",
        "debug_evidence.raw_result.image_info.height",
        "debug_evidence.feature_summary.raw_debug_evidence.raw_result.image_info.height",
    )
    try:
        width_int = int(width) if width not in (None, "") else None
    except (TypeError, ValueError):
        width_int = None
    try:
        height_int = int(height) if height not in (None, "") else None
    except (TypeError, ValueError):
        height_int = None
    return width_int, height_int


def _resolution_bucket(width: int | None, height: int | None, scenario: str) -> str:
    scenario_text = scenario.lower()
    for marker in ("long_512", "long_768", "long_1024", "long_edge_512", "long_edge_768", "long_edge_1024", "long_edge_1536"):
        if marker in scenario_text:
            return marker.replace("long_edge_", "long_")
    if not width or not height:
        return "unknown"
    long_edge = max(width, height)
    if long_edge <= 512:
        return "long_512_or_less"
    if long_edge <= 768:
        return "long_768"
    if long_edge <= 1024:
        return "long_1024"
    if long_edge <= 1536:
        return "long_1536"
    return "long_gt_1536"


def _stable_item_id(path_text: str, index: int, benchmark_run_id: str) -> str:
    base = f"{benchmark_run_id}|{path_text}|{index}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _compact_text(value: Any) -> str | list[Any] | dict[str, Any] | None:
    if value in (None, ""):
        return None
    return value


def _normalize_item(record: dict[str, Any], index: int, benchmark_run_id: str) -> tuple[dict[str, Any], set[str]]:
    missing: set[str] = set()
    image_path = _resolve_image_path(_first_value(record, "image_path", "file_path", "path", "source_path"))
    raw_path_text = str(_first_value(record, "image_path", "file_path", "path", "source_path", default=""))
    filename = str(_first_value(record, "filename", "file_name", default=Path(raw_path_text).name or f"sample_{index}"))
    true_label = _normalize_label(_first_value(record, "true_label", "ground_truth", "label", "target_label"))
    predicted_label = _normalize_label(
        _first_value(record, "final_label", "predicted_label", "prediction", "decision", "label_pred")
    )
    error_type = classify_error_type(true_label, predicted_label, record)
    width, height = _extract_width_height(record)
    scenario = str(_first_value(record, "scenario", "scene", "category", default="unknown") or "unknown")
    source_folder = str(_first_value(record, "source_folder", "parent_folder", default=_relative_source_folder(image_path)))
    ext = str(_first_value(record, "file_ext", "ext", default=(image_path.suffix.lower().lstrip(".") if image_path else Path(filename).suffix.lower().lstrip("."))) or "unknown").lower()
    fmt = str(_first_value(record, "format", "format_group", "image_format", default=ext or "unknown") or "unknown").lower()
    score = _safe_float(_first_value(record, "ai_score", "score", "raw_score", "probability", "ai_probability"))
    confidence = _safe_float(_first_value(record, "confidence", "decision_confidence"))

    required_map = {
        "file_path": image_path,
        "true_label": true_label if true_label != "unknown" else None,
        "predicted_label": predicted_label if predicted_label != "unknown" else None,
        "risk_level": _first_value(record, "risk_level", "risk", default=None),
        "confidence": confidence,
        "score": score,
        "scenario": scenario if scenario != "unknown" else None,
        "difficulty": _first_value(record, "difficulty", "difficulty_level", default=None),
        "width": width,
        "height": height,
    }
    missing.update(key for key, value in required_map.items() if value in (None, ""))

    item = {
        "id": str(_first_value(record, "id", "sample_id", default=_stable_item_id(raw_path_text or filename, index, benchmark_run_id))),
        "file_path": str(image_path) if image_path else raw_path_text or None,
        "image_url": _image_url(image_path),
        "filename": filename,
        "true_label": true_label,
        "predicted_label": predicted_label,
        "final_label": predicted_label,
        "error_type": error_type,
        "risk_level": str(_first_value(record, "risk_level", "risk", default="unknown") or "unknown").lower(),
        "confidence": confidence,
        "ai_score": score,
        "score": score,
        "decision_reason": _compact_text(_first_value(record, "decision_reason", "reason", "decision_reasons")),
        "recommendation": _compact_text(_first_value(record, "recommendation", "recommended_action")),
        "technical_explanation": _compact_text(_first_value(record, "technical_explanation", "explanation")),
        "debug_evidence": _first_value(record, "debug_evidence", "debug", default={}) or {},
        "scenario": scenario,
        "source_folder": source_folder.replace("\\", "/"),
        "difficulty": str(_first_value(record, "difficulty", "difficulty_level", default="unknown") or "unknown"),
        "format": fmt,
        "ext": ext or "unknown",
        "width": width,
        "height": height,
        "resolution_bucket": _resolution_bucket(width, height, scenario),
        "created_at": _first_value(record, "created_at", "generated_at"),
        "evaluated_at": _first_value(record, "evaluated_at", "processed_at", "timestamp"),
        "benchmark_run_id": benchmark_run_id,
        "benchmark_index": index,
        "status": str(record.get("status") or "unknown"),
        "source_benchmark_file": str(BENCHMARK_RESULTS_PATH),
    }
    return item, missing


def _latest_benchmark_run_id(summary: dict[str, Any]) -> str:
    return str(
        summary.get("benchmark_run_id")
        or summary.get("run_id")
        or summary.get("generated_at")
        or "day23_benchmark_protocol_v2"
    )


def _paths_mtime() -> tuple[float, float]:
    return (
        BENCHMARK_RESULTS_PATH.stat().st_mtime if BENCHMARK_RESULTS_PATH.exists() else 0.0,
        BENCHMARK_SUMMARY_PATH.stat().st_mtime if BENCHMARK_SUMMARY_PATH.exists() else 0.0,
    )


@lru_cache(maxsize=4)
def _load_gallery_cached(results_mtime: float, summary_mtime: float) -> dict[str, Any]:
    del results_mtime, summary_mtime
    summary = _load_json(BENCHMARK_SUMMARY_PATH, {})
    records = _load_json(BENCHMARK_RESULTS_PATH, [])
    if not isinstance(records, list):
        records = []
    if not isinstance(summary, dict):
        summary = {}

    benchmark_run_id = _latest_benchmark_run_id(summary)
    missing_counter: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            missing_counter["invalid_record"] += 1
            continue
        item, missing = _normalize_item(record, index, benchmark_run_id)
        missing_counter.update(missing)
        items.append(item)

    return {
        "items": items,
        "summary_json": summary,
        "benchmark_files": {
            "results_json": str(BENCHMARK_RESULTS_PATH),
            "summary_json": str(BENCHMARK_SUMMARY_PATH),
        },
        "missing_field_counts": dict(sorted(missing_counter.items())),
        "loaded_at": _now_iso(),
    }


def load_error_gallery() -> dict[str, Any]:
    return _load_gallery_cached(*_paths_mtime())


def _type_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("error_type") or "").upper() for item in items)
    return {
        "fp_count": counts.get("FP", 0),
        "fn_count": counts.get("FN", 0),
        "uncertain_count": counts.get("UNCERTAIN", 0),
        "tp_count": counts.get("TP", 0),
        "tn_count": counts.get("TN", 0),
    }


def _group_counts(items: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get(field) or "unknown")].append(item)
    output: dict[str, dict[str, Any]] = {}
    for key, values in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        counts = _type_counts(values)
        total_errors = counts["fp_count"] + counts["fn_count"] + counts["uncertain_count"]
        output[key] = {
            "total": len(values),
            "total_errors": total_errors,
            "error_rate": round(total_errors / len(values), 4) if values else 0.0,
            **counts,
        }
    return output


def build_error_summary() -> dict[str, Any]:
    gallery = load_error_gallery()
    items = gallery["items"]
    reviews = load_review_notes().get("reviews", {})
    counts = _type_counts(items)
    total = len(items)
    total_errors = counts["fp_count"] + counts["fn_count"] + counts["uncertain_count"]
    reviewed_count = sum(1 for item in items if reviews.get(item["id"], {}).get("reviewed") is True)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "benchmark_files": gallery["benchmark_files"],
        "total_samples": total,
        "total_errors": total_errors,
        "reviewed_count": reviewed_count,
        **counts,
        "error_rate": round(total_errors / total, 4) if total else 0.0,
        "fp_rate": round(counts["fp_count"] / total, 4) if total else 0.0,
        "fn_rate": round(counts["fn_count"] / total, 4) if total else 0.0,
        "uncertain_rate": round(counts["uncertain_count"] / total, 4) if total else 0.0,
        "by_scenario": _group_counts(items, "scenario"),
        "by_format": _group_counts(items, "format"),
        "by_resolution_bucket": _group_counts(items, "resolution_bucket"),
        "by_difficulty": _group_counts(items, "difficulty"),
        "by_source_folder": _group_counts(items, "source_folder"),
        "missing_field_counts": gallery["missing_field_counts"],
    }


def _matches_optional(item: dict[str, Any], field: str, expected: str | None) -> bool:
    return expected in (None, "", "all") or str(item.get(field) or "").lower() == expected.lower()


def list_error_items(
    *,
    item_type: str = "all",
    scenario: str | None = None,
    format: str | None = None,
    difficulty: str | None = None,
    resolution_bucket: str | None = None,
    source_folder: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    sort: str = "confidence_desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    normalized_type = item_type.lower()
    if normalized_type not in ERROR_TYPES:
        raise ValueError("type must be one of: all, fp, fn, uncertain, tp, tn.")
    if sort not in SORT_MODES:
        raise ValueError("sort must be one of: confidence_desc, confidence_asc, score_desc, score_asc, filename.")

    items = list(load_error_gallery()["items"])
    if normalized_type != "all":
        items = [item for item in items if str(item.get("error_type") or "").lower() == normalized_type]
    items = [
        item
        for item in items
        if _matches_optional(item, "scenario", scenario)
        and _matches_optional(item, "format", format)
        and _matches_optional(item, "difficulty", difficulty)
        and _matches_optional(item, "resolution_bucket", resolution_bucket)
        and _matches_optional(item, "source_folder", source_folder)
    ]
    if min_confidence is not None:
        items = [item for item in items if (item.get("confidence") is not None and float(item["confidence"]) >= min_confidence)]
    if max_confidence is not None:
        items = [item for item in items if (item.get("confidence") is not None and float(item["confidence"]) <= max_confidence)]

    reverse = sort.endswith("_desc")
    if sort.startswith("confidence"):
        items.sort(key=lambda item: (item.get("confidence") is None, float(item.get("confidence") or 0.0)), reverse=reverse)
    elif sort.startswith("score"):
        items.sort(key=lambda item: (item.get("score") is None, float(item.get("score") or 0.0)), reverse=reverse)
    else:
        items.sort(key=lambda item: str(item.get("filename") or "").lower())

    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    reviews = load_review_notes()
    paged = [with_review(item, reviews) for item in items[safe_offset : safe_offset + safe_limit]]
    return {
        "items": paged,
        "total": len(items),
        "limit": safe_limit,
        "offset": safe_offset,
        "filters": {
            "type": normalized_type,
            "scenario": scenario,
            "format": format,
            "difficulty": difficulty,
            "resolution_bucket": resolution_bucket,
            "source_folder": source_folder,
            "min_confidence": min_confidence,
            "max_confidence": max_confidence,
            "sort": sort,
        },
    }


def load_review_notes(path: Path | None = None) -> dict[str, Any]:
    review_path = Path(path or REVIEW_NOTES_PATH)
    data = _load_json(review_path, {"reviews": {}})
    if isinstance(data, dict) and isinstance(data.get("reviews"), dict):
        return data
    return {"reviews": {}}


def with_review(item: dict[str, Any], reviews: dict[str, Any] | None = None) -> dict[str, Any]:
    output = dict(item)
    review_data = reviews or load_review_notes()
    output["review"] = review_data.get("reviews", {}).get(
        item["id"],
        {
            "reviewed": False,
            "manual_tag": None,
            "reviewer_note": "",
            "reviewer": None,
            "updated_at": None,
        },
    )
    return output


def get_error_item(item_id: str) -> dict[str, Any]:
    reviews = load_review_notes()
    for item in load_error_gallery()["items"]:
        if str(item.get("id")) == item_id:
            return with_review(item, reviews)
    raise ErrorItemNotFound(f"Error gallery item not found: {item_id}")


def save_review_note(
    item_id: str,
    payload: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    get_error_item(item_id)
    manual_tag = payload.get("manual_tag")
    if manual_tag in ("", None):
        manual_tag = None
    elif manual_tag not in MANUAL_TAGS:
        raise ValueError("manual_tag must be one of: format_bias, resolution_flip, no_exif_jpeg, low_texture, high_compression, realistic_ai, unknown.")

    review = {
        "id": item_id,
        "reviewed": bool(payload.get("reviewed", False)),
        "manual_tag": manual_tag,
        "reviewer_note": str(payload.get("reviewer_note") or ""),
        "reviewer": str(payload.get("reviewer") or "local"),
        "updated_at": _now_iso(),
    }
    review_path = Path(path or REVIEW_NOTES_PATH)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_review_notes(review_path)
    existing.setdefault("schema_version", "day24_error_review_notes_v1")
    existing.setdefault("created_at", _now_iso())
    existing["updated_at"] = review["updated_at"]
    existing.setdefault("reviews", {})[item_id] = review
    review_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return review
