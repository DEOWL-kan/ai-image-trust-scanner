from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from app.policy.evidence_policy import apply_evidence_policy
from app.services import report_store
from app.services.history_store import now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_VERSION = "review_manifest_v1"
REPLAY_SCHEMA_VERSION = "policy_replay_v1"
DEFAULT_REVIEW_MANIFEST_DIR = Path(
    os.getenv("MINERVA_REVIEW_MANIFEST_DIR", str(PROJECT_ROOT / ".tmp" / "review_manifests"))
).expanduser()
DEFAULT_POLICY_REPLAY_DIR = Path(
    os.getenv("MINERVA_POLICY_REPLAY_DIR", str(PROJECT_ROOT / ".tmp" / "policy_replay"))
).expanduser()
REVIEW_LABEL_BY_STATUS = {
    "confirmed_ai": "ai",
    "false_negative": "ai",
    "confirmed_real": "real",
    "false_positive": "real",
}


def _records(records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return records if records is not None else report_store.list_reports()


def _compact_hash(*parts: Any) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_binary_label(value: Any) -> str:
    label = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if label in {"ai", "ai_generated", "likely_ai", "generated", "synthetic", "artificial"}:
        return "ai"
    if label in {"real", "real_photo", "likely_real", "authentic", "photo", "camera"}:
        return "real"
    if label in {"needs_review", "review_needed", "uncertain", "unknown", "undetermined"}:
        return "review"
    return "unknown"


def _review_label(record: dict[str, Any]) -> str | None:
    status = str(record.get("review_status") or "").strip().lower().replace("-", "_")
    return REVIEW_LABEL_BY_STATUS.get(status)


def _detectors(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("detector_results")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    payload = record.get("report_payload_json")
    api_data = payload.get("api_data") if isinstance(payload, dict) and isinstance(payload.get("api_data"), dict) else {}
    value = api_data.get("detector_results")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _detector_id(item: dict[str, Any]) -> str:
    return str(item.get("detector_id") or item.get("id") or item.get("name") or "unknown").strip().lower()


def _detector_score(item: dict[str, Any]) -> float | None:
    for key in ("ai_score", "score", "raw_score"):
        try:
            value = item.get(key)
            if value is not None:
                return round(max(0.0, min(1.0, float(value))), 4)
        except (TypeError, ValueError):
            continue
    return None


def _detector_threshold(item: dict[str, Any]) -> float:
    try:
        return round(max(0.0, min(1.0, float(item.get("threshold", 0.5)))), 4)
    except (TypeError, ValueError):
        return 0.5


def _detector_label(item: dict[str, Any]) -> str:
    label = str(item.get("predicted_label") or item.get("label") or item.get("raw_label") or "").lower()
    if label in {"ai", "real", "error", "disabled", "skipped"}:
        return label
    score = _detector_score(item)
    if score is None:
        return "unknown"
    return "ai" if score >= _detector_threshold(item) else "real"


def _detector_status(item: dict[str, Any]) -> str:
    error = item.get("error") if isinstance(item.get("error"), dict) else {}
    return str(item.get("status") or ("error" if error.get("message") else "ok")).lower()


def _detector_summary(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compact = []
    ai_like: list[dict[str, Any]] = []
    real_like: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for item in _detectors(record):
        detector_id = _detector_id(item)
        score = _detector_score(item)
        threshold = _detector_threshold(item)
        label = _detector_label(item)
        status = _detector_status(item)
        role = str(item.get("role") or "diagnostic").lower()
        compact_item = {
            "detector_id": detector_id,
            "role": role,
            "status": status,
            "label": label,
            "ai_score": score,
            "threshold": threshold,
            "latency_ms": item.get("latency_ms"),
            "error": item.get("error") if isinstance(item.get("error"), dict) else {},
        }
        compact.append(compact_item)
        if status == "ok" and label == "ai":
            ai_like.append(compact_item)
        if status == "ok" and label == "real":
            real_like.append(compact_item)
        if status == "error":
            errors.append(compact_item)
    max_gap = 0.0
    for left in ai_like:
        for right in real_like:
            if left.get("ai_score") is not None and right.get("ai_score") is not None:
                max_gap = max(max_gap, abs(float(left["ai_score"]) - float(right["ai_score"])))
    primary_error = any(item["detector_id"] == "smogy" or item["role"] in {"primary", "primary_candidate"} for item in errors)
    return compact, {
        "ai_like": [item["detector_id"] for item in ai_like],
        "real_like": [item["detector_id"] for item in real_like],
        "error_detectors": [item["detector_id"] for item in errors],
        "has_conflict": bool(ai_like and real_like and max_gap >= 0.35),
        "has_primary_error": primary_error,
        "max_conflict_gap": round(max_gap, 4),
    }


def _provenance_summary(record: dict[str, Any]) -> dict[str, Any]:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    verified = provenance.get("verified") if isinstance(provenance.get("verified"), dict) else provenance
    diagnostics = provenance.get("diagnostics") if isinstance(provenance.get("diagnostics"), dict) else {}
    ai_declared = bool(
        verified.get("openai_provenance_detected")
        or verified.get("ai_generated")
        or verified.get("generated_by_ai")
    )
    readable = bool(verified.get("c2pa_readable") or verified.get("verified"))
    status = str(diagnostics.get("c2pa_probe_status") or "")
    if readable and ai_declared:
        tier = "verified_ai"
    elif readable:
        tier = "verified_present"
    elif status == "no_manifest" or not provenance:
        tier = "missing"
    else:
        tier = "unverified"
    return {
        "tier": tier,
        "ai_declared": ai_declared,
        "c2pa_readable": readable,
        "c2pa_probe_status": status,
    }


def _manifest_reasons(
    record: dict[str, Any],
    predicted_label: str,
    human_label: str | None,
    detector_state: dict[str, Any],
    provenance: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    status = str(record.get("review_status") or "").strip().lower().replace("-", "_")
    risk = str(record.get("risk_level") or "").strip().lower()
    if status:
        reasons.append(f"review_status:{status}")
    if human_label == "real" and predicted_label == "ai":
        reasons.append("false_positive_candidate")
    if human_label == "ai" and predicted_label == "real":
        reasons.append("false_negative_candidate")
    if predicted_label == "review":
        reasons.append("uncertain_or_review_label")
    if risk == "high":
        reasons.append("high_risk")
    if detector_state["has_conflict"]:
        reasons.append("detector_conflict")
    if detector_state["has_primary_error"]:
        reasons.append("primary_detector_error")
    if provenance["ai_declared"]:
        reasons.append("verified_ai_provenance")
    if provenance["tier"] == "missing":
        reasons.append("missing_provenance")
    return reasons


def _primary_slice(record: dict[str, Any], predicted_label: str, human_label: str | None, reasons: list[str]) -> str:
    status = str(record.get("review_status") or "").strip().lower().replace("-", "_")
    if status == "false_positive" or (human_label == "real" and predicted_label == "ai"):
        return "false_positive"
    if status == "false_negative" or (human_label == "ai" and predicted_label == "real"):
        return "false_negative"
    if status in {"confirmed_ai", "confirmed_real"}:
        return status
    if "detector_conflict" in reasons:
        return "detector_conflict"
    if "primary_detector_error" in reasons:
        return "primary_detector_error"
    if predicted_label == "review" or status == "pending_review":
        return "pending_or_uncertain"
    if "high_risk" in reasons:
        return "high_risk_unreviewed"
    return "monitor"


def _priority(primary_slice: str, reasons: list[str]) -> int:
    base = {
        "false_positive": 100,
        "false_negative": 100,
        "detector_conflict": 85,
        "primary_detector_error": 80,
        "pending_or_uncertain": 70,
        "high_risk_unreviewed": 65,
        "confirmed_ai": 45,
        "confirmed_real": 45,
        "monitor": 20,
    }.get(primary_slice, 20)
    return base + min(15, len(reasons) * 3)


def build_review_manifest(
    records: list[dict[str, Any]] | None = None,
    *,
    include_unreviewed: bool = True,
    include_private_paths: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for record in _records(records):
        human_label = _review_label(record)
        predicted_label = _normalize_binary_label(record.get("final_label"))
        detectors, detector_state = _detector_summary(record)
        provenance = _provenance_summary(record)
        reasons = _manifest_reasons(record, predicted_label, human_label, detector_state, provenance)
        should_include = bool(human_label) or (
            include_unreviewed
            and bool(
                {"high_risk", "detector_conflict", "primary_detector_error", "uncertain_or_review_label", "review_status:pending_review"}
                & set(reasons)
            )
        )
        if not should_include:
            continue
        primary_slice = _primary_slice(record, predicted_label, human_label, reasons)
        image_path = record.get("image_path") if include_private_paths else None
        item = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "sample_id": _compact_hash(record.get("report_id"), record.get("file_sha256"), record.get("image_name")),
            "report_id": record.get("report_id") or record.get("id"),
            "created_at": record.get("created_at"),
            "filename": record.get("image_name") or record.get("filename"),
            "image_path": image_path,
            "file_sha256": record.get("file_sha256"),
            "predicted_label": predicted_label,
            "review_label": human_label,
            "review_status": record.get("review_status"),
            "review_note": record.get("review_note"),
            "primary_slice": primary_slice,
            "priority": _priority(primary_slice, reasons),
            "reasons": reasons,
            "risk_level": record.get("risk_level"),
            "confidence": record.get("confidence"),
            "detectors": detectors,
            "detector_state": detector_state,
            "provenance": provenance,
            "policy": {
                "policy_version": record.get("policy_version"),
                "policy_profile": (record.get("policy_result") or {}).get("policy_profile")
                if isinstance(record.get("policy_result"), dict)
                else None,
                "threshold_profile": record.get("threshold_profile"),
                "decision_reason": record.get("decision_reason"),
            },
        }
        items.append(item)
    items.sort(key=lambda item: (int(item["priority"]), str(item.get("created_at") or "")), reverse=True)
    if limit is not None:
        items = items[: max(0, int(limit))]
    slice_counts = Counter(str(item.get("primary_slice") or "unknown") for item in items)
    label_counts = Counter(str(item.get("review_label") or "unlabeled") for item in items)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at": now_iso(),
        "include_unreviewed": include_unreviewed,
        "total": len(items),
        "summary": {
            "slice_counts": dict(slice_counts),
            "review_label_counts": dict(label_counts),
            "labeled_count": sum(1 for item in items if item.get("review_label")),
            "unlabeled_count": sum(1 for item in items if not item.get("review_label")),
        },
        "items": items,
    }


def _raw_report(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("report_payload_json")
    if not isinstance(payload, dict):
        return {}
    value = payload.get("raw_report")
    return value if isinstance(value, dict) else {}


def _api_data(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("report_payload_json")
    if isinstance(payload, dict) and isinstance(payload.get("api_data"), dict):
        return payload["api_data"]
    return {}


def _replay_inputs(record: dict[str, Any], profile: str) -> dict[str, Any]:
    raw_report = _raw_report(record)
    api_data = _api_data(record)
    return {
        "detector_results": _detectors(record),
        "metadata_result": raw_report.get("metadata_result") if isinstance(raw_report.get("metadata_result"), dict) else {},
        "provenance_result": record.get("provenance")
        if isinstance(record.get("provenance"), dict)
        else api_data.get("provenance") if isinstance(api_data.get("provenance"), dict) else {},
        "forensic_result": raw_report.get("forensic_result") if isinstance(raw_report.get("forensic_result"), dict) else {},
        "context": {
            "filename": record.get("image_name") or record.get("filename"),
            "source_type": record.get("source_type") or record.get("history_type"),
            "policy_profile": profile,
            "detector_summary": record.get("detector_summary") if isinstance(record.get("detector_summary"), dict) else {},
        },
    }


def _metric_template() -> dict[str, Any]:
    return {
        "total_records": 0,
        "replayable_records": 0,
        "input_labeled_records": 0,
        "labeled_records": 0,
        "decision_counts": {},
        "review_rate": None,
        "ai_recall": None,
        "real_false_positive_rate": None,
        "decisive_accuracy": None,
        "coverage": None,
        "score": None,
        "errors": 0,
    }


def _finalize_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = _metric_template()
    metrics["total_records"] = len(rows)
    metrics["replayable_records"] = sum(1 for row in rows if row.get("replay_status") == "ok")
    metrics["input_labeled_records"] = sum(1 for row in rows if row.get("review_label") in {"ai", "real"})
    metrics["errors"] = sum(1 for row in rows if row.get("replay_status") == "error")
    metrics["decision_counts"] = dict(Counter(str(row.get("replayed_class") or "unknown") for row in rows))
    replayable = [row for row in rows if row.get("replay_status") == "ok"]
    if replayable:
        review_count = sum(1 for row in replayable if row.get("replayed_class") == "review")
        metrics["review_rate"] = round(review_count / len(replayable), 4)
    labeled = [row for row in replayable if row.get("review_label") in {"ai", "real"}]
    metrics["labeled_records"] = len(labeled)
    if not labeled:
        return metrics
    ai_rows = [row for row in labeled if row.get("review_label") == "ai"]
    real_rows = [row for row in labeled if row.get("review_label") == "real"]
    decisive = [row for row in labeled if row.get("replayed_class") in {"ai", "real"}]
    if ai_rows:
        metrics["ai_recall"] = round(sum(1 for row in ai_rows if row.get("replayed_class") == "ai") / len(ai_rows), 4)
    if real_rows:
        metrics["real_false_positive_rate"] = round(
            sum(1 for row in real_rows if row.get("replayed_class") == "ai") / len(real_rows),
            4,
        )
    if decisive:
        metrics["decisive_accuracy"] = round(
            sum(1 for row in decisive if row.get("replayed_class") == row.get("review_label")) / len(decisive),
            4,
        )
    metrics["coverage"] = round(len(decisive) / len(labeled), 4)
    ai_recall = metrics["ai_recall"] if metrics["ai_recall"] is not None else 0.0
    real_fp = metrics["real_false_positive_rate"] if metrics["real_false_positive_rate"] is not None else 0.0
    review_rate = metrics["review_rate"] if metrics["review_rate"] is not None else 0.0
    metrics["score"] = round(ai_recall - (2.0 * real_fp) - (0.2 * review_rate), 4)
    return metrics


def replay_policy_profiles(
    records: list[dict[str, Any]] | None = None,
    *,
    profiles: list[str] | tuple[str, ...] | None = None,
    include_unlabeled: bool = True,
) -> dict[str, Any]:
    profile_names = [str(item).strip() for item in (profiles or ["strict_safe_plus", "high_recall_review"]) if str(item).strip()]
    source_records = _records(records)
    rows: list[dict[str, Any]] = []
    metrics_by_profile: dict[str, dict[str, Any]] = {}
    for profile in profile_names:
        profile_rows: list[dict[str, Any]] = []
        for record in source_records:
            review_label = _review_label(record)
            if not include_unlabeled and not review_label:
                continue
            base = {
                "schema_version": REPLAY_SCHEMA_VERSION,
                "report_id": record.get("report_id") or record.get("id"),
                "filename": record.get("image_name") or record.get("filename"),
                "profile": profile,
                "current_label": _normalize_binary_label(record.get("final_label")),
                "review_label": review_label,
                "review_status": record.get("review_status"),
                "risk_level": record.get("risk_level"),
                "confidence": record.get("confidence"),
            }
            try:
                inputs = _replay_inputs(record, profile)
                if not inputs["detector_results"]:
                    raise ValueError("record has no detector_results to replay")
                result = apply_evidence_policy(
                    inputs["detector_results"],
                    metadata_result=inputs["metadata_result"],
                    provenance_result=inputs["provenance_result"],
                    forensic_result=inputs["forensic_result"],
                    context=inputs["context"],
                    policy_profile=profile,
                )
                row = {
                    **base,
                    "replay_status": "ok",
                    "replayed_label": result.get("final_label"),
                    "replayed_class": _normalize_binary_label(result.get("final_label")),
                    "replayed_risk": result.get("risk_level"),
                    "replayed_confidence": result.get("confidence"),
                    "decision_reason": result.get("decision_reason"),
                    "primary_detector_thresholds": result.get("primary_detector_thresholds"),
                }
            except Exception as exc:
                row = {
                    **base,
                    "replay_status": "error",
                    "replayed_label": None,
                    "replayed_class": "unknown",
                    "replayed_risk": None,
                    "replayed_confidence": None,
                    "decision_reason": "",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            profile_rows.append(row)
            rows.append(row)
        metrics_by_profile[profile] = _finalize_metrics(profile_rows)
    labeled_counts = {profile: metrics["labeled_records"] for profile, metrics in metrics_by_profile.items()}
    recommended = _recommend_profile(metrics_by_profile)
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "created_at": now_iso(),
        "profiles": profile_names,
        "include_unlabeled": include_unlabeled,
        "total_source_records": len(source_records),
        "labeled_counts": labeled_counts,
        "recommended_profile": recommended,
        "metrics": metrics_by_profile,
        "rows": rows,
    }


def _recommend_profile(metrics_by_profile: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        (profile, metrics)
        for profile, metrics in metrics_by_profile.items()
        if metrics.get("labeled_records", 0) > 0 and metrics.get("score") is not None
    ]
    if not candidates:
        input_labeled = sum(int(metrics.get("input_labeled_records") or 0) for metrics in metrics_by_profile.values())
        if input_labeled:
            return {
                "profile": None,
                "reason": "Reviewed labels exist, but none of the labeled records have replayable detector_results. Label new reports generated by the current detector pipeline.",
            }
        return {
            "profile": None,
            "reason": "No reviewed labels are available. Add confirmed_ai/confirmed_real/false_positive/false_negative reviews first.",
        }
    candidates.sort(
        key=lambda item: (
            float(item[1].get("real_false_positive_rate") if item[1].get("real_false_positive_rate") is not None else 1.0),
            -float(item[1].get("ai_recall") if item[1].get("ai_recall") is not None else 0.0),
            float(item[1].get("review_rate") if item[1].get("review_rate") is not None else 1.0),
            -float(item[1].get("score") or 0.0),
        )
    )
    profile, metrics = candidates[0]
    return {
        "profile": profile,
        "reason": "Selected the lowest reviewed real false-positive rate, then highest AI recall and lower review burden.",
        "metrics": metrics,
    }


def write_review_manifest_exports(manifest: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, str]:
    out_dir = Path(output_dir or DEFAULT_REVIEW_MANIFEST_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "review_manifest.json"
    jsonl_path = out_dir / "review_manifest.jsonl"
    csv_path = out_dir / "review_manifest.csv"
    summary_json_path = out_dir / "review_manifest_summary.json"
    summary_path = out_dir / "review_manifest_summary.md"
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8", newline="") as handle:
        for item in manifest.get("items", []):
            handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    fields = [
        "sample_id",
        "report_id",
        "filename",
        "predicted_label",
        "review_label",
        "review_status",
        "primary_slice",
        "priority",
        "risk_level",
        "confidence",
        "image_path",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in manifest.get("items", []):
            writer.writerow({field: item.get(field, "") for field in fields})
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    summary_json_path.write_text(
        json.dumps(
            {
                "schema_version": manifest.get("schema_version"),
                "created_at": manifest.get("created_at"),
                "include_unreviewed": manifest.get("include_unreviewed"),
                "total": manifest.get("total"),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Review Manifest Summary",
        "",
        f"- schema_version: {manifest.get('schema_version')}",
        f"- created_at: {manifest.get('created_at')}",
        f"- total: {manifest.get('total')}",
        f"- labeled_count: {summary.get('labeled_count', 0)}",
        f"- unlabeled_count: {summary.get('unlabeled_count', 0)}",
        f"- slice_counts: {summary.get('slice_counts', {})}",
        f"- review_label_counts: {summary.get('review_label_counts', {})}",
        "",
        "Images are not copied; this manifest records local report IDs, optional local paths, review labels, and replay slices.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(json_path),
        "jsonl": str(jsonl_path),
        "csv": str(csv_path),
        "summary_json": str(summary_json_path),
        "summary": str(summary_path),
    }


def write_policy_replay_exports(report: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, str]:
    out_dir = Path(output_dir or DEFAULT_POLICY_REPLAY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "policy_replay.json"
    compact_json_path = out_dir / "policy_replay_compact.json"
    csv_path = out_dir / "policy_replay_rows.csv"
    summary_path = out_dir / "policy_replay_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    compact = dict(report)
    compact["row_count"] = len(report.get("rows", []))
    compact["row_limit"] = 0
    compact["rows"] = []
    compact_json_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    fields = [
        "report_id",
        "filename",
        "profile",
        "current_label",
        "review_label",
        "review_status",
        "replay_status",
        "replayed_label",
        "replayed_class",
        "replayed_risk",
        "replayed_confidence",
        "decision_reason",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in report.get("rows", []):
            writer.writerow({field: row.get(field, "") for field in fields})
    lines = [
        "# Policy Replay Summary",
        "",
        f"- schema_version: {report.get('schema_version')}",
        f"- created_at: {report.get('created_at')}",
        f"- total_source_records: {report.get('total_source_records')}",
        f"- profiles: {', '.join(report.get('profiles', []))}",
        f"- recommended_profile: {((report.get('recommended_profile') or {}).get('profile'))}",
        f"- recommendation_reason: {((report.get('recommended_profile') or {}).get('reason'))}",
        "",
        "## Metrics",
        "",
    ]
    for profile, metrics in (report.get("metrics") or {}).items():
        lines.extend(
            [
                f"### {profile}",
                "",
                f"- replayable_records: {metrics.get('replayable_records')}",
                f"- input_labeled_records: {metrics.get('input_labeled_records')}",
                f"- labeled_records: {metrics.get('labeled_records')}",
                f"- ai_recall: {metrics.get('ai_recall')}",
                f"- real_false_positive_rate: {metrics.get('real_false_positive_rate')}",
                f"- review_rate: {metrics.get('review_rate')}",
                f"- coverage: {metrics.get('coverage')}",
                f"- score: {metrics.get('score')}",
                "",
            ]
        )
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "json": str(json_path),
        "compact_json": str(compact_json_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _read_jsonl_head(path: Path, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
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
        return []
    return items


def _read_csv_head(path: Path, limit: int) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [row for index, row in enumerate(csv.DictReader(handle)) if index < limit]
    except OSError:
        return []


def read_review_manifest_export(output_dir: str | Path | None = None, *, limit: int = 200) -> dict[str, Any] | None:
    out_dir = Path(output_dir or DEFAULT_REVIEW_MANIFEST_DIR)
    summary_path = out_dir / "review_manifest_summary.json"
    jsonl_path = out_dir / "review_manifest.jsonl"
    summary = _read_json(summary_path)
    if not summary or not jsonl_path.exists():
        return None
    payload = dict(summary)
    payload["items"] = _read_jsonl_head(jsonl_path, max(0, int(limit)))
    payload["limit"] = max(0, int(limit))
    payload["cached"] = True
    return payload


def read_policy_replay_export(
    output_dir: str | Path | None = None,
    *,
    include_rows: bool = False,
    row_limit: int = 500,
) -> dict[str, Any] | None:
    out_dir = Path(output_dir or DEFAULT_POLICY_REPLAY_DIR)
    compact_path = out_dir / "policy_replay_compact.json"
    csv_path = out_dir / "policy_replay_rows.csv"
    payload = _read_json(compact_path)
    if not payload:
        return None
    payload["rows"] = _read_csv_head(csv_path, row_limit) if include_rows else []
    payload["row_limit"] = max(0, int(row_limit)) if include_rows else 0
    payload["cached"] = True
    return payload
