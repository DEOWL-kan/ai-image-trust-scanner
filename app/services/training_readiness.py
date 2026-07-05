from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from app.services import report_store
from app.services.history_store import now_iso
from app.services.scenario_stress_pack import DEFAULT_OUTPUT_DIR as STRESS_PACK_OUTPUT_DIR
from app.services.scenario_stress_pack import read_scenario_stress_pack_export


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "training_readiness_manifest_v1"
QUEUE_SCHEMA_VERSION = "training_label_queue_v1"
DEFAULT_OUTPUT_DIR = Path(
    os.getenv("MINERVA_TRAINING_READINESS_DIR", str(PROJECT_ROOT / ".tmp" / "training_readiness"))
).expanduser()
TARGET_SUPERVISED_PER_CLASS = 10
SUPERVISED_LABEL_STATUSES = {
    "confirmed_ai": "ai",
    "false_negative": "ai",
    "confirmed_real": "real",
    "false_positive": "real",
}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _text(value: Any, fallback: str = "") -> str:
    if value in (None, ""):
        return fallback
    return str(value)


def _normalize_label(value: Any) -> str:
    label = _text(value).strip().lower().replace("-", "_").replace(" ", "_")
    if label in {"ai", "ai_generated", "likely_ai", "generated", "synthetic", "artificial"}:
        return "ai"
    if label in {"real", "real_photo", "likely_real", "authentic", "photo", "camera"}:
        return "real"
    if label in {"uncertain", "review", "needs_review", "review_needed", "unknown", "undetermined"}:
        return "uncertain"
    return "unknown"


def _review_status(value: Any) -> str:
    return _text(value, "unreviewed").strip().lower().replace("-", "_").replace(" ", "_")


def _supervised_label(status: Any) -> str | None:
    return SUPERVISED_LABEL_STATUSES.get(_review_status(status))


def _hash(*parts: Any) -> str:
    text = "|".join(_text(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _split(sample_hash: str) -> str:
    bucket = int(hashlib.sha256(sample_hash.encode("utf-8")).hexdigest(), 16) % 10
    if bucket < 7:
        return "train"
    if bucket < 8:
        return "val"
    return "test"


def _path_from_record(record: dict[str, Any]) -> Path | None:
    raw = _text(record.get("image_path")).strip()
    if not raw or raw == "[redacted]":
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS else None


def _public_path(path: Path | None, include_private_paths: bool) -> str:
    if not path:
        return ""
    return str(path) if include_private_paths else ""


def _record_item(record: dict[str, Any], *, include_private_paths: bool) -> dict[str, Any] | None:
    status = _review_status(record.get("review_status"))
    supervised = _supervised_label(status)
    predicted = _normalize_label(record.get("final_label"))
    label = supervised or predicted
    if label not in {"ai", "real"}:
        return None
    path = _path_from_record(record)
    file_available = bool(path and path.exists() and path.is_file())
    sample_hash = _hash(record.get("report_id") or record.get("id"), record.get("file_sha256"), path)
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_id": f"report_{sample_hash}",
        "source_kind": "reviewed_report" if supervised else "weak_report_candidate",
        "report_id": _text(record.get("report_id") or record.get("id")),
        "filename": _text(record.get("image_name") or record.get("filename")),
        "file_path": _public_path(path, include_private_paths),
        "file_available": file_available,
        "label": label,
        "label_source": "human_review" if supervised else "model_prediction",
        "predicted_label": predicted,
        "review_status": status,
        "risk_level": _text(record.get("risk_level") or "unknown"),
        "confidence": record.get("confidence"),
        "scenario": "original",
        "transform": "none",
        "split": _split(sample_hash),
        "sample_hash": sample_hash,
        "detector_registry_version": _text(record.get("detector_registry_version")),
        "threshold_profile": _text(record.get("threshold_profile") or "default"),
        "model_adapter_version": _text(record.get("model_adapter_version")),
    }


def _stress_item(row: dict[str, Any], *, output_dir: Path, include_private_paths: bool) -> dict[str, Any] | None:
    if _text(row.get("status")) != "ready":
        return None
    review_label = _normalize_label(row.get("review_label"))
    predicted = _normalize_label(row.get("predicted_label"))
    label = review_label if review_label in {"ai", "real"} else predicted
    if label not in {"ai", "real"}:
        return None
    derived_relpath = _text(row.get("derived_relpath"))
    path = (output_dir / derived_relpath).resolve() if derived_relpath else None
    file_available = bool(path and path.exists() and path.is_file())
    sample_hash = _hash(row.get("sample_id"), row.get("report_id"), derived_relpath)
    supervised = review_label in {"ai", "real"}
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_id": f"stress_{sample_hash}",
        "source_kind": "stress_reviewed_variant" if supervised else "stress_weak_candidate",
        "report_id": _text(row.get("report_id")),
        "filename": _text(row.get("filename")),
        "file_path": _public_path(path, include_private_paths),
        "file_available": file_available,
        "label": label,
        "label_source": "human_review" if supervised else "model_prediction",
        "predicted_label": predicted,
        "review_status": _review_status(row.get("review_status")),
        "risk_level": _text(row.get("risk_level") or "unknown"),
        "confidence": row.get("confidence"),
        "scenario": _text(row.get("scenario") or "unknown"),
        "transform": _text(row.get("transform") or "unknown"),
        "split": _split(sample_hash),
        "sample_hash": sample_hash,
        "detector_registry_version": "",
        "threshold_profile": "stress_pack",
        "model_adapter_version": "",
    }


def _stress_rows(*, include_private_paths: bool) -> list[dict[str, Any]]:
    export = read_scenario_stress_pack_export(limit=100000, include_private_paths=False)
    if not export:
        return []
    output_dir = Path(_text(export.get("output_dir"), str(STRESS_PACK_OUTPUT_DIR)))
    rows = []
    for row in export.get("items") or []:
        if isinstance(row, dict):
            item = _stress_item(row, output_dir=output_dir, include_private_paths=include_private_paths)
            if item:
                rows.append(item)
    return rows


def build_manifest(
    records: Iterable[dict[str, Any]] | None = None,
    *,
    include_stress_pack: bool = True,
    include_private_paths: bool = False,
) -> list[dict[str, Any]]:
    source_records = list(records) if records is not None else report_store.list_reports()
    items = []
    for record in source_records:
        if isinstance(record, dict):
            item = _record_item(record, include_private_paths=include_private_paths)
            if item:
                items.append(item)
    if include_stress_pack:
        items.extend(_stress_rows(include_private_paths=include_private_paths))
    return sorted(items, key=lambda item: (item.get("label_source") != "human_review", item.get("source_kind"), item.get("sample_id")))


def build_summary(items: list[dict[str, Any]], *, min_supervised_labels: int = 20) -> dict[str, Any]:
    total = len(items)
    supervised = [item for item in items if item.get("label_source") == "human_review"]
    weak = [item for item in items if item.get("label_source") == "model_prediction"]
    file_ready = [item for item in items if item.get("file_available")]
    supervised_file_ready = [item for item in supervised if item.get("file_available")]
    supervised_labels = Counter(_text(item.get("label")) for item in supervised_file_ready)
    target_per_class = max(1, min_supervised_labels // 2)
    needed_ai_labels = max(0, target_per_class - int(supervised_labels.get("ai", 0)))
    needed_real_labels = max(0, target_per_class - int(supervised_labels.get("real", 0)))
    has_both_classes = supervised_labels.get("ai", 0) > 0 and supervised_labels.get("real", 0) > 0
    if len(supervised_file_ready) >= min_supervised_labels and has_both_classes:
        readiness_level = "train_ready"
        recommendation = "Enough reviewed local files exist to start lightweight local training or threshold calibration."
    elif supervised_file_ready and has_both_classes:
        readiness_level = "seed_ready"
        recommendation = "Both classes are present. Add more reviewed labels before treating metrics as reliable."
    elif supervised_file_ready:
        readiness_level = "single_class_only"
        recommendation = "Reviewed files exist, but both ai and real labels are required for supervised calibration."
    else:
        readiness_level = "blocked_by_labels"
        recommendation = "Add human review labels to current detector reports before building a supervised training set."
    return {
        "schema_version": "training_readiness_summary_v1",
        "total": total,
        "file_ready_count": len(file_ready),
        "supervised_ready_count": len(supervised_file_ready),
        "weak_candidate_count": len(weak),
        "min_supervised_labels": int(min_supervised_labels),
        "target_supervised_per_class": target_per_class,
        "needed_ai_labels": needed_ai_labels,
        "needed_real_labels": needed_real_labels,
        "has_both_classes": has_both_classes,
        "readiness_level": readiness_level,
        "recommendation": recommendation,
        "counts_by_label": dict(Counter(_text(item.get("label") or "unknown") for item in items)),
        "counts_by_label_source": dict(Counter(_text(item.get("label_source") or "unknown") for item in items)),
        "counts_by_source_kind": dict(Counter(_text(item.get("source_kind") or "unknown") for item in items)),
        "counts_by_split": dict(Counter(_text(item.get("split") or "unknown") for item in items)),
        "supervised_label_counts": dict(supervised_labels),
    }


def _label_queue_item(
    record: dict[str, Any],
    *,
    needed_ai_labels: int,
    needed_real_labels: int,
    include_private_paths: bool,
) -> dict[str, Any] | None:
    status = _review_status(record.get("review_status"))
    if _supervised_label(status):
        return None
    path = _path_from_record(record)
    if not (path and path.exists() and path.is_file()):
        return None
    predicted = _normalize_label(record.get("final_label"))
    if predicted == "ai":
        target_gap = "ai" if needed_ai_labels > 0 else "balanced_review"
        suggested = ["confirmed_ai", "false_positive"]
    elif predicted == "real":
        target_gap = "real" if needed_real_labels > 0 else "balanced_review"
        suggested = ["confirmed_real", "false_negative"]
    else:
        target_gap = "ai_or_real"
        suggested = ["confirmed_ai", "confirmed_real"]
    risk = _text(record.get("risk_level") or "unknown").lower()
    try:
        confidence = float(record.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    score = 0
    score += 50 if target_gap in {"ai", "real", "ai_or_real"} else 0
    score += 30 if status == "pending_review" else 0
    score += 25 if risk == "high" else 0
    score += 10 if predicted == "uncertain" else 0
    score += int(max(0.0, min(1.0, confidence)) * 10)
    sample_hash = _hash(record.get("report_id") or record.get("id"), record.get("file_sha256"), path)
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "report_id": _text(record.get("report_id") or record.get("id")),
        "filename": _text(record.get("image_name") or record.get("filename")),
        "created_at": _text(record.get("created_at")),
        "file_path": _public_path(path, include_private_paths),
        "file_available": True,
        "predicted_label": predicted,
        "review_status": status,
        "risk_level": _text(record.get("risk_level") or "unknown"),
        "confidence": record.get("confidence"),
        "target_gap": target_gap,
        "suggested_review_statuses": suggested,
        "priority_score": score,
        "sample_hash": sample_hash,
        "summary": _text(record.get("user_facing_summary") or record.get("report_summary") or record.get("recommendation")),
    }


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).strip().lower() in {"1", "true", "yes", "y"}


def _label_queue_item_from_manifest(
    item: dict[str, Any],
    *,
    needed_ai_labels: int,
    needed_real_labels: int,
    current_record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    current_status = _review_status(current_record.get("review_status")) if isinstance(current_record, dict) else _review_status(item.get("review_status"))
    if _supervised_label(current_status):
        return None
    if _text(item.get("label_source")) == "human_review":
        return None
    if not _is_truthy(item.get("file_available")):
        return None
    predicted = _normalize_label(item.get("predicted_label") or item.get("label"))
    if predicted == "ai":
        target_gap = "ai" if needed_ai_labels > 0 else "balanced_review"
        suggested = ["confirmed_ai", "false_positive"]
    elif predicted == "real":
        target_gap = "real" if needed_real_labels > 0 else "balanced_review"
        suggested = ["confirmed_real", "false_negative"]
    else:
        target_gap = "ai_or_real"
        suggested = ["confirmed_ai", "confirmed_real"]
    risk = _text(item.get("risk_level") or "unknown").lower()
    try:
        confidence = float(item.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    score = 0
    score += 50 if target_gap in {"ai", "real", "ai_or_real"} else 0
    score += 30 if current_status == "pending_review" else 0
    score += 25 if risk == "high" else 0
    score += 10 if predicted == "uncertain" else 0
    score += int(max(0.0, min(1.0, confidence)) * 10)
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "report_id": _text(item.get("report_id")),
        "filename": _text(item.get("filename")),
        "created_at": _text(item.get("created_at")),
        "file_path": "",
        "file_available": True,
        "predicted_label": predicted,
        "review_status": current_status,
        "risk_level": _text(item.get("risk_level") or "unknown"),
        "confidence": item.get("confidence"),
        "target_gap": target_gap,
        "suggested_review_statuses": suggested,
        "priority_score": score,
        "sample_hash": _text(item.get("sample_hash")),
        "summary": "",
    }


def _records_by_cached_item_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    report_ids = sorted({
        _text(item.get("report_id"))
        for item in items
        if isinstance(item, dict) and _text(item.get("report_id"))
    })
    try:
        return report_store.get_reports_by_ids(report_ids)
    except Exception:
        return {}


def build_label_queue_payload(
    records: Iterable[dict[str, Any]] | None = None,
    *,
    limit: int = 20,
    include_private_paths: bool = False,
    use_cached_summary: bool = True,
) -> dict[str, Any]:
    cached = read_outputs(limit=100000, include_private_paths=False) if records is None and use_cached_summary else None
    summary = cached.get("summary") if isinstance(cached, dict) and isinstance(cached.get("summary"), dict) else None
    if summary is not None:
        queue = []
        cached_items = [
            item
            for item in cached.get("items") or []
            if isinstance(item, dict)
            and _text(item.get("label_source")) != "human_review"
            and _is_truthy(item.get("file_available"))
        ]
        current_records = _records_by_cached_item_id(cached_items)
        for item in cached_items:
            queue_item = _label_queue_item_from_manifest(
                item,
                needed_ai_labels=int(summary.get("needed_ai_labels") or 0),
                needed_real_labels=int(summary.get("needed_real_labels") or 0),
                current_record=current_records.get(_text(item.get("report_id"))),
            )
            if queue_item:
                queue.append(queue_item)
        queue.sort(key=lambda item: (int(item.get("priority_score") or 0), item.get("created_at") or ""), reverse=True)
        safe_limit = max(0, min(int(limit), 200))
        gap = {
            "needed_ai_labels": summary.get("needed_ai_labels", 0),
            "needed_real_labels": summary.get("needed_real_labels", 0),
            "target_supervised_per_class": summary.get("target_supervised_per_class", TARGET_SUPERVISED_PER_CLASS),
            "supervised_label_counts": summary.get("supervised_label_counts", {}),
            "readiness_level": summary.get("readiness_level"),
            "recommendation": summary.get("recommendation"),
        }
        return {
            "schema_version": QUEUE_SCHEMA_VERSION,
            "created_at": now_iso(),
            "gap": gap,
            "summary": {
                "total_candidates": len(queue),
                "returned": min(len(queue), safe_limit),
                "file_ready_candidates": len(queue),
                "items_need_ai": sum(1 for item in queue if item.get("target_gap") == "ai"),
                "items_need_real": sum(1 for item in queue if item.get("target_gap") == "real"),
                "items_need_either": sum(1 for item in queue if item.get("target_gap") == "ai_or_real"),
                "source": "cached_training_readiness",
            },
            "items": queue[:safe_limit],
            "total": len(queue),
            "limit": safe_limit,
            "cached": True,
        }

    source_records = list(records) if records is not None else report_store.list_reports()
    if summary is None:
        readiness_items = build_manifest(source_records, include_stress_pack=True, include_private_paths=False)
        summary = build_summary(readiness_items)
    queue = []
    for record in source_records:
        if not isinstance(record, dict):
            continue
        item = _label_queue_item(
            record,
            needed_ai_labels=int(summary.get("needed_ai_labels") or 0),
            needed_real_labels=int(summary.get("needed_real_labels") or 0),
            include_private_paths=include_private_paths,
        )
        if item:
            queue.append(item)
    queue.sort(key=lambda item: (int(item.get("priority_score") or 0), item.get("created_at") or ""), reverse=True)
    safe_limit = max(0, min(int(limit), 200))
    gap = {
        "needed_ai_labels": summary.get("needed_ai_labels", 0),
        "needed_real_labels": summary.get("needed_real_labels", 0),
        "target_supervised_per_class": summary.get("target_supervised_per_class", TARGET_SUPERVISED_PER_CLASS),
        "supervised_label_counts": summary.get("supervised_label_counts", {}),
        "readiness_level": summary.get("readiness_level"),
        "recommendation": summary.get("recommendation"),
    }
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "created_at": now_iso(),
        "gap": gap,
        "summary": {
            "total_candidates": len(queue),
            "returned": min(len(queue), safe_limit),
            "file_ready_candidates": len(queue),
            "items_need_ai": sum(1 for item in queue if item.get("target_gap") == "ai"),
            "items_need_real": sum(1 for item in queue if item.get("target_gap") == "real"),
            "items_need_either": sum(1 for item in queue if item.get("target_gap") == "ai_or_real"),
        },
        "items": queue[:safe_limit],
        "total": len(queue),
        "limit": safe_limit,
        "cached": False,
    }


CSV_FIELDS = [
    "sample_id",
    "source_kind",
    "report_id",
    "filename",
    "file_path",
    "file_available",
    "label",
    "label_source",
    "predicted_label",
    "review_status",
    "risk_level",
    "confidence",
    "scenario",
    "transform",
    "split",
    "sample_hash",
    "detector_registry_version",
    "threshold_profile",
    "model_adapter_version",
]


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Training Readiness Summary",
        "",
        f"- schema_version: {summary.get('schema_version')}",
        f"- total: {summary.get('total')}",
        f"- file_ready_count: {summary.get('file_ready_count')}",
        f"- supervised_ready_count: {summary.get('supervised_ready_count')}",
        f"- weak_candidate_count: {summary.get('weak_candidate_count')}",
        f"- readiness_level: {summary.get('readiness_level')}",
        f"- has_both_classes: {summary.get('has_both_classes')}",
        f"- supervised_label_counts: {summary.get('supervised_label_counts', {})}",
        "",
        str(summary.get("recommendation") or ""),
    ]
    return "\n".join(lines) + "\n"


def _public_item(item: dict[str, Any], *, include_private_paths: bool = False) -> dict[str, Any]:
    public = dict(item)
    if not include_private_paths:
        public["file_path"] = ""
    return public


def build_payload(
    records: Iterable[dict[str, Any]] | None = None,
    *,
    include_stress_pack: bool = True,
    include_private_paths: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    items = build_manifest(
        records,
        include_stress_pack=include_stress_pack,
        include_private_paths=include_private_paths,
    )
    summary = build_summary(items)
    safe_limit = max(0, int(limit))
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "summary": summary,
        "total": len(items),
        "items": [_public_item(item, include_private_paths=include_private_paths) for item in items[:safe_limit]],
        "limit": safe_limit,
        "cached": False,
    }


def write_outputs(
    output_dir: str | Path | None = None,
    records: Iterable[dict[str, Any]] | None = None,
    *,
    include_stress_pack: bool = True,
) -> dict[str, Any]:
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    items = build_manifest(records, include_stress_pack=include_stress_pack, include_private_paths=True)
    summary = build_summary(items)
    csv_path = out_dir / "training_readiness_manifest.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow({field: item.get(field, "") for field in CSV_FIELDS})
    json_path = out_dir / "training_readiness_manifest.jsonl"
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    compact_path = out_dir / "training_readiness_compact.json"
    compact_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "created_at": now_iso(),
                "output_dir": str(out_dir),
                "summary": summary,
                "total": len(items),
                "item_count": len(items),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_json_path = out_dir / "training_readiness_summary.json"
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    summary_md_path = out_dir / "training_readiness_summary.md"
    summary_md_path.write_text(_summary_markdown(summary), encoding="utf-8")
    return {
        "output_dir": str(out_dir),
        "manifest_csv": str(csv_path),
        "manifest_jsonl": str(json_path),
        "compact_json": str(compact_path),
        "summary_json": str(summary_json_path),
        "summary_md": str(summary_md_path),
        "summary": summary,
        "total": len(items),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _read_csv_head(path: Path, limit: int, *, include_private_paths: bool) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [row for index, row in enumerate(csv.DictReader(handle)) if index < limit]
    except OSError:
        return []
    return [_public_item(row, include_private_paths=include_private_paths) for row in rows]


def read_outputs(
    output_dir: str | Path | None = None,
    *,
    limit: int = 200,
    include_private_paths: bool = False,
) -> dict[str, Any] | None:
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    compact = _read_json(out_dir / "training_readiness_compact.json")
    if not compact:
        return None
    safe_limit = max(0, int(limit))
    compact["items"] = _read_csv_head(out_dir / "training_readiness_manifest.csv", safe_limit, include_private_paths=include_private_paths)
    compact["limit"] = safe_limit
    compact["cached"] = True
    return compact
