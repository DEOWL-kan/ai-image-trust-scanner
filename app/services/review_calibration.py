from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from app.services import report_store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = Path(
    os.getenv("MINERVA_REVIEW_CALIBRATION_DIR", str(PROJECT_ROOT / ".tmp" / "review_calibration"))
).expanduser()
SCHEMA_VERSION = "review_calibration_manifest_v1"

REVIEW_LABELS = {
    "confirmed_ai": "ai",
    "false_negative": "ai",
    "confirmed_real": "real",
    "false_positive": "real",
}
REVIEW_TOUCHED_STATUSES = {
    "reviewed",
    "confirmed_ai",
    "confirmed_real",
    "false_positive",
    "false_negative",
    "needs_recheck",
    "needs_follow_up",
    "ignored",
}


def _text(value: Any, fallback: str = "") -> str:
    if value in (None, ""):
        return fallback
    return str(value)


def _normal_label(value: Any) -> str:
    label = _text(value).strip().lower().replace("-", "_").replace(" ", "_")
    if label in {"ai", "ai_generated", "likely_ai", "generated", "synthetic", "artificial"}:
        return "ai"
    if label in {"real", "real_photo", "likely_real", "authentic", "photo", "camera"}:
        return "real"
    if label in {"uncertain", "needs_review", "review_needed", "unknown", "undetermined"}:
        return "uncertain"
    return "unknown"


def _review_label(review_status: Any) -> str | None:
    return REVIEW_LABELS.get(_text(review_status).strip().lower().replace("-", "_"))


def _case_type(predicted_label: str, review_status: str, review_label: str | None) -> str:
    if review_status == "ignored":
        return "ignored"
    if review_status in {"needs_recheck", "needs_follow_up"}:
        return review_status
    if review_label is None:
        return "reviewed_unlabeled" if review_status == "reviewed" else "unreviewed"
    if predicted_label == review_label:
        return "confirmed_correct"
    if predicted_label == "ai" and review_label == "real":
        return "false_positive"
    if predicted_label == "real" and review_label == "ai":
        return "false_negative"
    if predicted_label == "uncertain" and review_label == "ai":
        return "uncertain_true_ai"
    if predicted_label == "uncertain" and review_label == "real":
        return "uncertain_true_real"
    return "label_disagreement"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 6)


def _detector_id(detector: dict[str, Any]) -> str:
    return _text(detector.get("detector_id") or detector.get("id") or detector.get("name") or "unknown")


def _compact_detectors(record: dict[str, Any]) -> list[dict[str, Any]]:
    detectors = record.get("detector_results")
    if not isinstance(detectors, list):
        return []
    compact = []
    for detector in detectors:
        if not isinstance(detector, dict):
            continue
        compact.append(
            {
                "detector_id": _detector_id(detector),
                "role": _text(detector.get("role") or "unknown"),
                "status": _text(detector.get("status") or "unknown"),
                "predicted_label": _normal_label(detector.get("predicted_label") or detector.get("label")),
                "ai_score": _number(detector.get("ai_score")),
                "confidence": _number(detector.get("confidence")),
                "threshold": _number(detector.get("threshold")),
                "threshold_profile": _text(detector.get("threshold_profile") or record.get("threshold_profile") or "default"),
                "latency_ms": detector.get("latency_ms"),
            }
        )
    return compact


def _policy_action(record: dict[str, Any]) -> str:
    policy = record.get("policy_result")
    if isinstance(policy, dict):
        return _text(policy.get("action") or policy.get("recommended_action"))
    return ""


def manifest_item(record: dict[str, Any]) -> dict[str, Any]:
    review_status = _text(record.get("review_status") or "unreviewed").strip().lower().replace("-", "_")
    predicted_label = _normal_label(record.get("final_label"))
    label = _review_label(review_status)
    detectors = _compact_detectors(record)
    primary_detector = next((item for item in detectors if item.get("role") == "primary"), None)
    secondary_detector = next((item for item in detectors if item.get("role") == "secondary"), None)
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": _text(record.get("report_id") or record.get("id")),
        "created_at": _text(record.get("created_at")),
        "filename": _text(record.get("image_name") or record.get("filename")),
        "source_type": _text(record.get("source_type") or "unknown"),
        "batch_id": _text(record.get("batch_id")),
        "predicted_label": predicted_label,
        "risk_level": _text(record.get("risk_level") or "unknown"),
        "confidence": _number(record.get("confidence")),
        "review_status": review_status,
        "review_label": label,
        "case_type": _case_type(predicted_label, review_status, label),
        "review_note_present": bool(record.get("review_note")),
        "threshold_profile": _text(record.get("threshold_profile") or "default"),
        "policy_version": _text(record.get("policy_version")),
        "policy_action": _policy_action(record),
        "detector_result_schema_version": _text(record.get("detector_result_schema_version")),
        "detector_registry_version": _text(record.get("detector_registry_version")),
        "model_adapter_version": _text(record.get("model_adapter_version")),
        "primary_detector_id": primary_detector.get("detector_id") if primary_detector else "",
        "primary_ai_score": primary_detector.get("ai_score") if primary_detector else None,
        "secondary_detector_id": secondary_detector.get("detector_id") if secondary_detector else "",
        "secondary_ai_score": secondary_detector.get("ai_score") if secondary_detector else None,
        "detectors": detectors,
    }


def build_manifest(records: Iterable[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    source = list(records) if records is not None else report_store.list_reports()
    items = [manifest_item(record) for record in source if isinstance(record, dict)]
    return sorted(items, key=lambda item: (item.get("created_at") or "", item.get("report_id") or ""))


def _threshold_candidates() -> list[float]:
    return [round(value / 100.0, 2) for value in range(5, 100, 5)]


def _binary_metrics(rows: list[tuple[float, str]], threshold: float) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for score, label in rows:
        predicted_ai = score >= threshold
        truth_ai = label == "ai"
        if predicted_ai and truth_ai:
            tp += 1
        elif predicted_ai and not truth_ai:
            fp += 1
        elif not predicted_ai and not truth_ai:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    balanced_accuracy = (recall + tnr) / 2.0
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "fpr": round(fpr, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
    }


def threshold_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_detector: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for item in items:
        label = item.get("review_label")
        if label not in {"ai", "real"}:
            continue
        for detector in item.get("detectors") or []:
            if not isinstance(detector, dict):
                continue
            score = _number(detector.get("ai_score"))
            detector_id = _text(detector.get("detector_id") or "unknown")
            if score is not None and detector_id:
                by_detector[detector_id].append((score, label))

    diagnostics: dict[str, Any] = {}
    for detector_id, rows in sorted(by_detector.items()):
        label_counts = Counter(label for _, label in rows)
        metrics = [_binary_metrics(rows, threshold) for threshold in _threshold_candidates()]
        best = max(metrics, key=lambda item: (item["balanced_accuracy"], -item["fpr"], item["recall"], item["threshold"]))
        diagnostics[detector_id] = {
            "sample_count": len(rows),
            "label_counts": dict(label_counts),
            "best_threshold": best,
            "thresholds": metrics,
            "warning": "" if set(label_counts) == {"ai", "real"} else "needs both ai and real review labels for reliable threshold tuning",
        }
    return diagnostics


def build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    reviewed_count = sum(1 for item in items if item.get("review_status") in REVIEW_TOUCHED_STATUSES)
    labeled_count = sum(1 for item in items if item.get("review_label") in {"ai", "real"})
    detector_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in items:
        for detector in item.get("detectors") or []:
            if not isinstance(detector, dict):
                continue
            detector_status_counts[_text(detector.get("detector_id") or "unknown")][_text(detector.get("status") or "unknown")] += 1
    return {
        "schema_version": "review_calibration_summary_v1",
        "total": total,
        "reviewed_count": reviewed_count,
        "labeled_count": labeled_count,
        "review_coverage": round(reviewed_count / total, 4) if total else 0.0,
        "label_coverage": round(labeled_count / total, 4) if total else 0.0,
        "counts_by_case_type": dict(Counter(_text(item.get("case_type") or "unknown") for item in items)),
        "counts_by_predicted_label": dict(Counter(_text(item.get("predicted_label") or "unknown") for item in items)),
        "counts_by_review_label": dict(Counter(_text(item.get("review_label") or "unlabeled") for item in items)),
        "counts_by_review_status": dict(Counter(_text(item.get("review_status") or "unknown") for item in items)),
        "detector_status_counts": {detector_id: dict(counter) for detector_id, counter in sorted(detector_status_counts.items())},
        "threshold_diagnostics": threshold_diagnostics(items),
    }


CSV_FIELDS = [
    "report_id",
    "created_at",
    "filename",
    "source_type",
    "batch_id",
    "predicted_label",
    "risk_level",
    "confidence",
    "review_status",
    "review_label",
    "case_type",
    "review_note_present",
    "threshold_profile",
    "policy_version",
    "policy_action",
    "primary_detector_id",
    "primary_ai_score",
    "secondary_detector_id",
    "secondary_ai_score",
    "detectors_json",
]


def write_outputs(output_dir: Path | str = DEFAULT_OUTPUT_DIR, records: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    items = build_manifest(records)
    summary = build_summary(items)

    jsonl_path = out_dir / "review_calibration_manifest.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    csv_path = out_dir / "review_calibration_manifest.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            row = dict(item)
            row["detectors_json"] = json.dumps(item.get("detectors") or [], ensure_ascii=False, sort_keys=True, default=str)
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})

    summary_json_path = out_dir / "review_calibration_summary.json"
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    summary_md_path = out_dir / "review_calibration_summary.md"
    summary_md_path.write_text(_summary_markdown(summary), encoding="utf-8")

    return {
        "output_dir": str(out_dir),
        "manifest_jsonl": str(jsonl_path),
        "manifest_csv": str(csv_path),
        "summary_json": str(summary_json_path),
        "summary_md": str(summary_md_path),
        "summary": summary,
    }


def read_outputs(output_dir: Path | str = DEFAULT_OUTPUT_DIR, *, limit: int = 200) -> dict[str, Any] | None:
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    summary_json_path = out_dir / "review_calibration_summary.json"
    jsonl_path = out_dir / "review_calibration_manifest.jsonl"
    try:
        summary = json.loads(summary_json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    items: list[dict[str, Any]] = []
    try:
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(items) >= limit:
                    break
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    items.append(value)
    except OSError:
        items = []
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "total": int(summary.get("total") or len(items)),
        "items": items,
        "limit": max(0, int(limit)),
        "cached": True,
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Review Calibration Summary",
        "",
        f"- total: {summary.get('total', 0)}",
        f"- reviewed_count: {summary.get('reviewed_count', 0)}",
        f"- labeled_count: {summary.get('labeled_count', 0)}",
        f"- review_coverage: {summary.get('review_coverage', 0.0)}",
        f"- label_coverage: {summary.get('label_coverage', 0.0)}",
        "",
        "## Case Types",
    ]
    for key, value in sorted((summary.get("counts_by_case_type") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Detector Threshold Diagnostics"])
    diagnostics = summary.get("threshold_diagnostics") or {}
    if not diagnostics:
        lines.append("- none")
    for detector_id, payload in sorted(diagnostics.items()):
        best = payload.get("best_threshold") or {}
        lines.append(
            f"- {detector_id}: samples={payload.get('sample_count', 0)}, "
            f"best_threshold={best.get('threshold')}, balanced_accuracy={best.get('balanced_accuracy')}, "
            f"precision={best.get('precision')}, recall={best.get('recall')}, fpr={best.get('fpr')}"
        )
    return "\n".join(lines) + "\n"
