from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.history_store import HISTORY_DIR


SCHEMA_VERSION = "dashboard_v1"
DEFAULT_HISTORY_DIR = HISTORY_DIR

FINAL_LABELS = ("ai_generated", "real", "uncertain")
RISK_LEVELS = ("low", "medium", "high", "unknown")
CONFIDENCE_BUCKETS = ("high_confidence", "medium_confidence", "low_confidence")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _empty_counter(keys: tuple[str, ...]) -> dict[str, int]:
    return {key: 0 for key in keys}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 4)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_final_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"ai", "ai_generated", "likely_ai", "generated", "artificial"}:
        return "ai_generated"
    if label in {"real", "real_photo", "likely_real", "photo", "camera", "authentic"}:
        return "real"
    return "uncertain"


def _normalize_risk_level(value: Any) -> str:
    risk = str(value or "").strip().lower()
    if risk in {"low", "medium", "high"}:
        return risk
    if risk in {"very_high", "critical"}:
        return "high"
    return "unknown"


def _confidence_bucket(confidence: float) -> str:
    if confidence >= 0.75:
        return "high_confidence"
    if confidence >= 0.5:
        return "medium_confidence"
    return "low_confidence"


def _recommendation_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("message") or value.get("action") or "")
    return str(value or "")


def _parse_sort_datetime(value: Any) -> datetime:
    text = str(value or "")
    if text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.min


def _read_history_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{path.name}: {type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, f"{path.name}: root JSON value is not an object"
    return data, None


def _result_from_single(history: dict[str, Any]) -> dict[str, Any] | None:
    response = history.get("response") if isinstance(history.get("response"), dict) else {}
    if response.get("success") is False:
        return None

    data = response.get("data")
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        result = dict(data["result"])
        image = data.get("image") if isinstance(data.get("image"), dict) else {}
        result.setdefault("filename", image.get("filename"))
        return result
    if isinstance(data, dict):
        return data
    if {"final_label", "risk_level", "confidence"}.intersection(response.keys()):
        return response
    return None


def _compact_result(
    *,
    history_file: str,
    history_type: str,
    timestamp: Any,
    result: dict[str, Any],
    input_payload: dict[str, Any] | None = None,
    index: int | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    input_payload = input_payload or {}
    final_label = _normalize_final_label(result.get("final_label"))
    risk_level = _normalize_risk_level(result.get("risk_level"))
    confidence = _safe_float(result.get("confidence"))
    filename = (
        result.get("filename")
        or input_payload.get("filename")
        or input_payload.get("source")
        or "unknown"
    )
    result_id = str(result.get("id") or result.get("request_id") or "")
    if not result_id:
        suffix = f"_{index}" if index is not None else ""
        result_id = f"{Path(history_file).stem}{suffix}"

    return {
        "id": result_id,
        "timestamp": str(result.get("timestamp") or result.get("processed_at") or timestamp or ""),
        "filename": str(Path(str(filename)).name or filename),
        "final_label": final_label,
        "risk_level": risk_level,
        "confidence": confidence,
        "user_facing_summary": str(result.get("user_facing_summary") or ""),
        "recommendation": _recommendation_text(result.get("recommendation")),
        "history_type": history_type,
        "history_file": history_file,
        "batch_id": batch_id,
    }


def _extract_history(
    history: dict[str, Any],
    history_file: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    history_type = str(history.get("history_type") or "").lower()
    response = history.get("response") if isinstance(history.get("response"), dict) else {}
    request = history.get("request") if isinstance(history.get("request"), dict) else {}
    timestamp = history.get("created_at") or response.get("created_at")

    if history_type == "batch" or response.get("mode") == "batch":
        batch_id = str(response.get("batch_id") or Path(history_file).stem)
        batch = {
            "id": batch_id,
            "timestamp": str(response.get("created_at") or timestamp or ""),
            "total": _safe_int(response.get("total") or request.get("input_count")),
            "succeeded": _safe_int(response.get("succeeded")),
            "failed": _safe_int(response.get("failed")),
            "history_file": history_file,
        }
        records: list[dict[str, Any]] = []
        raw_results = response.get("results")
        if isinstance(raw_results, list):
            for index, item in enumerate(raw_results):
                if not isinstance(item, dict) or item.get("status") not in {"success", None}:
                    continue
                result = item.get("result")
                if not isinstance(result, dict):
                    continue
                input_payload = item.get("input") if isinstance(item.get("input"), dict) else {}
                records.append(
                    _compact_result(
                        history_file=history_file,
                        history_type="batch",
                        timestamp=timestamp,
                        result=result,
                        input_payload=input_payload,
                        index=index,
                        batch_id=batch_id,
                    )
                )
        return records, batch

    result = _result_from_single(history)
    if not isinstance(result, dict):
        return [], None
    return [
        _compact_result(
            history_file=history_file,
            history_type="single",
            timestamp=timestamp,
            result=result,
        )
    ], None


def load_dashboard_history(history_dir: Path | None = None) -> dict[str, Any]:
    source = Path(history_dir or DEFAULT_HISTORY_DIR)
    loaded_files = 0
    skipped_files = 0
    warnings: list[str] = []
    results: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    single_history_count = 0

    if not source.exists():
        return {
            "results": results,
            "batches": batches,
            "single_history_count": single_history_count,
            "debug": {
                "history_source": str(source),
                "result_files_loaded": loaded_files,
                "skipped_files": skipped_files,
                "warnings": warnings,
                "schema_version": SCHEMA_VERSION,
            },
        }

    for path in sorted(source.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        history, warning = _read_history_file(path)
        if warning:
            skipped_files += 1
            warnings.append(warning)
            continue

        loaded_files += 1
        history_type = str(history.get("history_type") or "").lower()
        if history_type == "single":
            single_history_count += 1
        try:
            file_results, batch = _extract_history(history, path.name)
        except Exception as exc:
            skipped_files += 1
            warnings.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        results.extend(file_results)
        if batch:
            batches.append(batch)

    results.sort(key=lambda item: _parse_sort_datetime(item.get("timestamp")), reverse=True)
    batches.sort(key=lambda item: _parse_sort_datetime(item.get("timestamp")), reverse=True)
    return {
        "results": results,
        "batches": batches,
        "single_history_count": single_history_count,
        "debug": {
            "history_source": str(source),
            "result_files_loaded": loaded_files,
            "skipped_files": skipped_files,
            "warnings": warnings,
            "schema_version": SCHEMA_VERSION,
        },
    }


def _chart_points(values: dict[str, int], labels: dict[str, str]) -> list[dict[str, Any]]:
    return [{"label": labels[key], "value": int(values.get(key, 0))} for key in labels]


def _daily_trend(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in results:
        timestamp = str(item.get("timestamp") or "")
        date = timestamp[:10]
        if date:
            counts[date] += 1
    return [{"date": date, "count": counts[date]} for date in sorted(counts)]


def _alerts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uncertain = [item for item in results if item.get("final_label") == "uncertain"]
    high_risk = [item for item in results if item.get("risk_level") == "high"]
    false_positive_review = [
        item
        for item in results
        if item.get("final_label") == "ai_generated" and float(item.get("confidence") or 0.0) < 0.65
    ]
    alert_defs = [
        ("uncertain_samples", "warning", uncertain),
        ("high_risk_samples", "critical", high_risk),
        ("false_positive_review_candidates", "info", false_positive_review),
    ]
    return [
        {
            "type": alert_type,
            "severity": severity,
            "count": len(items),
            "samples": items[:5],
        }
        for alert_type, severity, items in alert_defs
        if items
    ]


def build_dashboard_payload(
    *,
    history_dir: Path | None = None,
    limit_recent: int = 10,
    include_debug: bool = False,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit_recent), 100))
    loaded = load_dashboard_history(history_dir)
    results = loaded["results"]
    batches = loaded["batches"]

    final_counts = _empty_counter(FINAL_LABELS)
    final_counts.update(Counter(item["final_label"] for item in results))
    risk_counts = _empty_counter(RISK_LEVELS)
    risk_counts.update(Counter(item["risk_level"] for item in results))
    confidence_counts = _empty_counter(CONFIDENCE_BUCKETS)
    confidence_counts.update(Counter(_confidence_bucket(float(item.get("confidence") or 0.0)) for item in results))

    total_images = len(results)
    confidence_sum = sum(float(item.get("confidence") or 0.0) for item in results)
    average_confidence = round(confidence_sum / total_images, 4) if total_images else 0.0
    high_risk_count = risk_counts["high"]
    uncertain_count = final_counts["uncertain"]

    chart_data = {
        "label_pie": _chart_points(
            final_counts,
            {
                "ai_generated": "AI Generated",
                "real": "Real",
                "uncertain": "Uncertain",
            },
        ),
        "risk_bar": _chart_points(
            risk_counts,
            {
                "low": "Low",
                "medium": "Medium",
                "high": "High",
                "unknown": "Unknown",
            },
        ),
        "confidence_bar": _chart_points(
            confidence_counts,
            {
                "high_confidence": "High Confidence",
                "medium_confidence": "Medium Confidence",
                "low_confidence": "Low Confidence",
            },
        ),
        "daily_trend": _daily_trend(results),
    }

    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "summary": {
            "total_detections": loaded["single_history_count"] + len(batches),
            "single_detection_count": loaded["single_history_count"],
            "batch_detection_count": len(batches),
            "total_images_processed": total_images,
            "final_label_distribution": final_counts,
            "risk_level_distribution": risk_counts,
            "confidence_distribution": confidence_counts,
            "decision_quality": {
                "uncertain_rate": round(uncertain_count / total_images, 4) if total_images else 0.0,
                "high_risk_rate": round(high_risk_count / total_images, 4) if total_images else 0.0,
                "average_confidence": average_confidence,
            },
        },
        "recent_results": results[:safe_limit],
        "recent_batches": batches[:safe_limit],
        "chart_data": chart_data,
        "alerts": _alerts(results),
        "debug": loaded["debug"] if include_debug else {"schema_version": SCHEMA_VERSION},
    }
    return payload


def build_recent_results_payload(
    *,
    history_dir: Path | None = None,
    limit: int = 20,
    final_label: str | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    normalized_label = _normalize_final_label(final_label) if final_label else None
    normalized_risk = _normalize_risk_level(risk_level) if risk_level else None
    results = load_dashboard_history(history_dir)["results"]
    if normalized_label:
        results = [item for item in results if item.get("final_label") == normalized_label]
    if normalized_risk:
        results = [item for item in results if item.get("risk_level") == normalized_risk]
    results = results[:safe_limit]
    return {
        "status": "ok",
        "count": len(results),
        "results": results,
    }


def build_chart_data_payload(history_dir: Path | None = None) -> dict[str, Any]:
    summary = build_dashboard_payload(history_dir=history_dir, limit_recent=1, include_debug=False)
    chart_data = summary["chart_data"]
    return {
        "status": "ok",
        "generated_at": summary["generated_at"],
        "charts": {
            "label_distribution": chart_data["label_pie"],
            "risk_distribution": chart_data["risk_bar"],
            "confidence_distribution": chart_data["confidence_bar"],
            "daily_detection_trend": chart_data["daily_trend"],
        },
    }
