from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.history_store import HISTORY_DIR, now_iso
from app.services import report_store


REPORT_SCHEMA_VERSION = "report_center_v1"
REVIEW_STATUSES = {
    "unreviewed",
    "pending_review",
    "reviewed",
    "confirmed_ai",
    "confirmed_real",
    "false_positive",
    "false_negative",
    "needs_recheck",
    "needs_follow_up",
    "ignored",
}
RISK_PRIORITY = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
TEXT_FIELDS = (
    "filename",
    "image_name",
    "id",
    "report_id",
    "final_label",
    "risk_level",
    "decision_reason",
    "user_facing_summary",
    "technical_explanation",
    "recommendation",
    "debug_evidence",
)


class ReportRecordNotFound(Exception):
    """Raised when a report record id cannot be found in history JSON."""


PRIVATE_RESPONSE_FIELDS = {"image_path", "html_report_path"}
PRIVATE_NESTED_KEYS = {"image_path", "html_report_path", "absolute_path", "local_path", "source_path"}


def _looks_like_local_path(value: str) -> bool:
    text = value.strip()
    return bool(text.startswith(("/", "\\")) or (len(text) > 2 and text[1:3] in {":\\", ":/"}))


def _redact_private(value: Any, key: str | None = None) -> Any:
    lowered = (key or "").lower()
    if lowered in PRIVATE_NESTED_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {item_key: _redact_private(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact_private(item) for item in value]
    if isinstance(value, str) and ("path" in lowered or lowered.endswith("_file")) and _looks_like_local_path(value):
        return "[redacted]"
    return value


def public_report_record(record: dict[str, Any]) -> dict[str, Any]:
    public = {key: _redact_private(value, key) for key, value in record.items() if key not in PRIVATE_RESPONSE_FIELDS}
    if record.get("html_report_available") and record.get("report_id"):
        public["html_report_url"] = f"/api/v1/reports/{record['report_id']}/html"
    return public


def public_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    if isinstance(safe.get("items"), list):
        safe["items"] = [public_report_record(item) if isinstance(item, dict) else item for item in safe["items"]]
    return safe


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _get_path(source: Any, dotted: str) -> Any:
    current = source
    for key in dotted.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _text(value: Any, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, list):
        rendered = "; ".join(_text(item, "") for item in value).strip("; ")
        return rendered or fallback
    if isinstance(value, dict):
        for key in ("message", "summary", "explanation", "action", "code"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def normalize_final_label(value: Any) -> str:
    label = str(value or "").strip().lower().replace("-", "_")
    if label in {"ai", "ai_generated", "likely_ai", "generated", "synthetic", "artificial"}:
        return "ai_generated"
    if label in {"real", "real_photo", "likely_real", "authentic", "photo", "camera"}:
        return "real"
    if label in {"uncertain", "unsure", "unknown", "review", "undetermined"}:
        return "uncertain"
    return "unknown"


def normalize_risk_level(value: Any) -> str:
    risk = str(value or "").strip().lower().replace("-", "_")
    if risk in {"high", "very_high", "critical"}:
        return "high"
    if risk in {"medium", "moderate"}:
        return "medium"
    if risk in {"low", "minimal"}:
        return "low"
    return "unknown"


def normalize_confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 4)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _record_id(*, history_file: str, result: dict[str, Any], raw: dict[str, Any], index: int | None = None) -> str:
    stem = Path(history_file).stem
    return str(
        _first_defined(
            result.get("id"),
            result.get("record_id"),
            result.get("audit_id"),
            result.get("result_id"),
            result.get("request_id"),
            raw.get("id"),
            raw.get("record_id"),
            raw.get("audit_id"),
            f"{stem}_{index}" if index is not None else stem,
        )
    )


def _normalize_record(
    *,
    history_file: str,
    history_type: str,
    history_created_at: Any,
    result: dict[str, Any],
    raw: dict[str, Any],
    input_payload: dict[str, Any] | None = None,
    index: int | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    input_payload = input_payload or {}
    image = _get_path(raw, "response.data.image") or _get_path(raw, "data.image") or {}
    created_at = _first_defined(
        result.get("created_at"),
        result.get("timestamp"),
        result.get("detected_at"),
        result.get("report_time"),
        raw.get("created_at"),
        raw.get("timestamp"),
        history_created_at,
    )
    final_label_raw = _first_defined(result.get("final_label"), result.get("label"), result.get("decision"), raw.get("final_label"), raw.get("label"))
    risk_raw = _first_defined(result.get("risk_level"), result.get("risk"), result.get("severity"), raw.get("risk_level"), raw.get("risk"))
    confidence = normalize_confidence(
        _first_defined(result.get("confidence"), result.get("confidence_score"), result.get("score"), result.get("probability"), raw.get("confidence"))
    )
    record = {
        "id": _record_id(history_file=history_file, result=result, raw=raw, index=index),
        "filename": str(
            Path(
                str(
                    _first_defined(
                        result.get("filename"),
                        result.get("image_name"),
                        input_payload.get("filename"),
                        image.get("filename") if isinstance(image, dict) else None,
                        raw.get("filename"),
                        raw.get("image_name"),
                        "unknown",
                    )
                )
            ).name
        ),
        "created_at": str(created_at or ""),
        "final_label": normalize_final_label(final_label_raw),
        "risk_level": normalize_risk_level(risk_raw),
        "confidence": confidence,
        "decision_reason": _first_defined(result.get("decision_reason"), result.get("reason"), raw.get("decision_reason")),
        "recommendation": _first_defined(result.get("recommendation"), raw.get("recommendation")),
        "user_facing_summary": _first_defined(result.get("user_facing_summary"), result.get("summary"), raw.get("user_facing_summary")),
        "technical_explanation": _first_defined(result.get("technical_explanation"), result.get("explanation"), raw.get("technical_explanation")),
        "debug_evidence": _first_defined(result.get("debug_evidence"), result.get("evidence"), result.get("signals"), result.get("debug"), raw.get("debug_evidence")),
        "review_status": str(_first_defined(result.get("review_status"), raw.get("review_status"), "pending_review")),
        "review_note": str(_first_defined(result.get("review_note"), raw.get("review_note"), "")),
        "reviewed_at": _first_defined(result.get("reviewed_at"), raw.get("reviewed_at")),
        "reviewer": str(_first_defined(result.get("reviewer"), raw.get("reviewer"), "")),
        "history_file": history_file,
        "history_type": history_type,
        "batch_id": batch_id,
        "raw": raw,
    }
    if record["review_status"] not in REVIEW_STATUSES:
        record["review_status"] = "pending_review"
    return record


def _records_from_history(path: Path, history: dict[str, Any]) -> list[dict[str, Any]]:
    history_file = path.name
    history_type = str(history.get("history_type") or "unknown").lower()
    response = history.get("response") if isinstance(history.get("response"), dict) else {}
    history_created_at = history.get("created_at") or response.get("created_at")
    if history_type == "batch" or response.get("mode") == "batch":
        records: list[dict[str, Any]] = []
        batch_id = str(response.get("batch_id") or path.stem)
        for index, item in enumerate(response.get("results") if isinstance(response.get("results"), list) else []):
            if not isinstance(item, dict) or item.get("status") not in {"success", None}:
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            if not result:
                continue
            input_payload = item.get("input") if isinstance(item.get("input"), dict) else {}
            records.append(
                _normalize_record(
                    history_file=history_file,
                    history_type="batch",
                    history_created_at=history_created_at,
                    result=result,
                    raw={**item, "history_file": history_file},
                    input_payload=input_payload,
                    index=index,
                    batch_id=batch_id,
                )
            )
        return records

    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    if not isinstance(result, dict) or not result:
        return []
    return [
        _normalize_record(
            history_file=history_file,
            history_type="single",
            history_created_at=history_created_at,
            result=result,
            raw={**history, "history_file": history_file},
        )
    ]


def _legacy_to_persistent_record(record: dict[str, Any]) -> dict[str, Any]:
    data = {
        "report_id": record.get("id"),
        "filename": record.get("filename"),
        "final_label": record.get("final_label"),
        "risk_level": record.get("risk_level"),
        "confidence": record.get("confidence"),
        "decision_reason": record.get("decision_reason"),
        "recommendation": record.get("recommendation"),
        "user_facing_summary": record.get("user_facing_summary"),
        "technical_explanation": record.get("technical_explanation"),
        "debug_evidence": record.get("debug_evidence"),
        "review_status": record.get("review_status"),
        "review_note": record.get("review_note"),
        "reviewed_at": record.get("reviewed_at"),
        "reviewed_by": record.get("reviewer"),
        "history_file": record.get("history_file"),
        "history_type": record.get("history_type"),
        "batch_id": record.get("batch_id"),
    }
    return report_store.make_report_record(
        detection_data=data,
        source_type=str(record.get("history_type") or "legacy"),
        report_payload=record.get("raw") if isinstance(record.get("raw"), dict) else record,
        export_payload=record,
        report_id=str(record.get("id")),
        created_at=record.get("created_at"),
        history_file=record.get("history_file"),
        history_type=record.get("history_type"),
        batch_id=record.get("batch_id"),
    )


def load_report_records_from_history(history_dir: Path | None = None) -> list[dict[str, Any]]:
    source = Path(history_dir or HISTORY_DIR)
    if not source.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(source.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        history = _read_json(path)
        if history is None:
            continue
        records.extend(_records_from_history(path, history))
    return records


def bootstrap_sqlite_from_history(history_dir: Path | None = None) -> int:
    if report_store.count_reports() > 0:
        return 0
    imported = 0
    for record in load_report_records_from_history(history_dir):
        try:
            report_store.save_report(_legacy_to_persistent_record(record))
            imported += 1
        except Exception:
            continue
    return imported


def load_report_records(history_dir: Path | None = None) -> list[dict[str, Any]]:
    if history_dir is not None:
        return load_report_records_from_history(history_dir)
    bootstrap_sqlite_from_history()
    return report_store.list_reports()


def _matches_search(record: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(_text(record.get(field), "") for field in TEXT_FIELDS).lower()
    return needle in haystack


def _matches_date(record: dict[str, Any], date_range: str | None) -> bool:
    value = str(date_range or "all").lower()
    if value in {"", "all"}:
        return True
    parsed = _parse_datetime(record.get("created_at"))
    if parsed is None:
        return False
    now = datetime.now(parsed.tzinfo).astimezone(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    if value == "today":
        return parsed.date() == now.date()
    if value in {"last_7_days", "7d"}:
        return parsed >= now - timedelta(days=7)
    if value in {"last_30_days", "30d"}:
        return parsed >= now - timedelta(days=30)
    return True


def _matches_date_bounds(record: dict[str, Any], date_from: str | None, date_to: str | None) -> bool:
    parsed = _parse_datetime(record.get("created_at"))
    if parsed is None:
        return not date_from and not date_to
    if date_from:
        start = _parse_datetime(date_from)
        if start and parsed < start:
            return False
    if date_to:
        end = _parse_datetime(date_to)
        if end and parsed > end:
            return False
    return True


def _matches_confidence(record: dict[str, Any], confidence_range: str | None) -> bool:
    value = str(confidence_range or "all").lower()
    if value in {"", "all"}:
        return True
    confidence = record.get("confidence")
    if confidence is None:
        return False
    number = float(confidence)
    if value in {"gte_0_8", ">=0.8", "high"}:
        return number >= 0.8
    if value in {"0_5_0_8", "0.5-0.8", "medium"}:
        return 0.5 <= number < 0.8
    if value in {"lt_0_5", "<0.5", "low"}:
        return number < 0.5
    return True


def _record_has_warning(record: dict[str, Any]) -> bool:
    text = _text(record.get("debug_evidence"), "").lower() + " " + _text(record.get("decision_reason"), "").lower()
    return any(token in text for token in ("warning", "error", "inconsistent", "low_confidence", "uncertain", "missing"))


def queue_priority(record: dict[str, Any]) -> tuple[int, int, float]:
    confidence = record.get("confidence")
    low_confidence = confidence is None or float(confidence) < 0.65
    score = 0
    score += 40 if record.get("risk_level") == "high" else 0
    score += 35 if record.get("final_label") == "uncertain" else 0
    score += 25 if record.get("review_status") == "pending_review" else 0
    score += 15 if low_confidence else 0
    score += 10 if _record_has_warning(record) else 0
    return (score, RISK_PRIORITY.get(str(record.get("risk_level")), 0), -(float(confidence) if confidence is not None else 0.0))


def _sort_records(records: list[dict[str, Any]], sort: str | None) -> list[dict[str, Any]]:
    value = str(sort or "newest").lower()
    if value == "oldest":
        return sorted(records, key=lambda item: _parse_datetime(item.get("created_at")) or datetime.min)
    if value in {"risk_priority", "risk"}:
        return sorted(records, key=lambda item: (RISK_PRIORITY.get(item.get("risk_level"), 0), item.get("final_label") == "uncertain"), reverse=True)
    if value in {"confidence_desc", "confidence_high"}:
        return sorted(records, key=lambda item: item.get("confidence") if item.get("confidence") is not None else -1, reverse=True)
    if value in {"confidence_asc", "confidence_low"}:
        return sorted(records, key=lambda item: item.get("confidence") if item.get("confidence") is not None else 2)
    return sorted(records, key=lambda item: _parse_datetime(item.get("created_at")) or datetime.min, reverse=True)


def _sort_records_by(records: list[dict[str, Any]], sort_by: str | None, sort_order: str | None) -> list[dict[str, Any]]:
    if not sort_by:
        return records
    key = str(sort_by or "created_at").lower()
    reverse = str(sort_order or "desc").lower() != "asc"
    allowed = {
        "created_at",
        "updated_at",
        "image_name",
        "filename",
        "final_label",
        "risk_level",
        "confidence",
        "review_status",
        "source_type",
    }
    if key not in allowed:
        raise ValueError(f"sort_by must be one of: {', '.join(sorted(allowed))}.")
    if key in {"created_at", "updated_at"}:
        return sorted(records, key=lambda item: _parse_datetime(item.get(key)) or datetime.min, reverse=reverse)
    if key == "confidence":
        return sorted(records, key=lambda item: item.get("confidence") if item.get("confidence") is not None else -1, reverse=reverse)
    if key in {"image_name", "filename"}:
        return sorted(records, key=lambda item: str(item.get("image_name") or item.get("filename") or ""), reverse=reverse)
    return sorted(records, key=lambda item: str(item.get(key) or ""), reverse=reverse)


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_records": len(records),
        "pending_review": sum(1 for item in records if item.get("review_status") == "pending_review"),
        "high_risk": sum(1 for item in records if item.get("risk_level") == "high"),
        "uncertain": sum(1 for item in records if item.get("final_label") == "uncertain"),
    }


def search_reports(
    *,
    q: str | None = None,
    risk_level: str | None = None,
    final_label: str | None = None,
    review_status: str | None = None,
    source_type: str | None = None,
    date_range: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    confidence_range: str | None = None,
    sort: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    limit: int = 50,
    offset: int = 0,
    history_dir: Path | None = None,
) -> dict[str, Any]:
    all_records = load_report_records(history_dir)
    risk = normalize_risk_level(risk_level) if risk_level and risk_level != "all" else None
    label = normalize_final_label(final_label) if final_label and final_label != "all" else None
    status = str(review_status or "").strip().lower()
    status = status if status and status != "all" else None
    source = str(source_type or "").strip().lower()
    source = source if source and source != "all" else None

    filtered = [
        record
        for record in all_records
        if _matches_search(record, q)
        and (risk is None or record.get("risk_level") == risk)
        and (label is None or record.get("final_label") == label)
        and (status is None or record.get("review_status") == status)
        and (source is None or str(record.get("source_type") or record.get("history_type") or "").lower() == source)
        and _matches_date(record, date_range)
        and _matches_date_bounds(record, date_from, date_to)
        and _matches_confidence(record, confidence_range)
    ]
    sorted_records = _sort_records_by(filtered, sort_by, sort_order) if sort_by else _sort_records(filtered, sort)
    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(int(limit), 500))
    items = sorted_records[safe_offset : safe_offset + safe_limit]
    return public_report_payload({
        "items": items,
        "total": len(all_records),
        "filtered_total": len(filtered),
        "filters": {
            "q": q or "",
            "risk_level": risk_level or "all",
            "final_label": final_label or "all",
            "review_status": review_status or "all",
            "source_type": source_type or "all",
            "date_range": date_range or "all",
            "date_from": date_from or "",
            "date_to": date_to or "",
            "confidence_range": confidence_range or "all",
            "sort": sort or "newest",
            "limit": safe_limit,
            "offset": safe_offset,
        },
        "limit": safe_limit,
        "offset": safe_offset,
        "sort": {
            "sort_by": sort_by or "created_at",
            "sort_order": sort_order or ("desc" if str(sort or "newest").lower() != "oldest" else "asc"),
            "legacy_sort": sort or "newest",
        },
        "summary": _summary(all_records),
        "schema_version": REPORT_SCHEMA_VERSION,
    })


def review_queue(limit: int = 20, history_dir: Path | None = None) -> dict[str, Any]:
    records = load_report_records(history_dir)
    queued = [
        record
        for record in records
        if record.get("risk_level") == "high"
        or record.get("final_label") == "uncertain"
        or record.get("review_status") == "pending_review"
        or record.get("confidence") is None
        or float(record.get("confidence") or 0.0) < 0.65
        or _record_has_warning(record)
    ]
    queued = sorted(queued, key=queue_priority, reverse=True)
    safe_limit = max(1, min(int(limit), 100))
    return public_report_payload({"items": queued[:safe_limit], "total": len(queued), "schema_version": REPORT_SCHEMA_VERSION})


def get_report_detail(record_id: str, history_dir: Path | None = None) -> dict[str, Any]:
    if history_dir is None:
        bootstrap_sqlite_from_history()
        record = report_store.get_report(record_id)
        if record is None:
            raise ReportRecordNotFound(f"Report record not found: {record_id}")
        return public_report_record(record)
    for record in load_report_records_from_history(history_dir):
        if record.get("id") == record_id or record.get("report_id") == record_id:
            return public_report_record(record)
    raise ReportRecordNotFound(f"Report record not found: {record_id}")


def get_html_report_path(record_id: str) -> Path:
    bootstrap_sqlite_from_history()
    record = report_store.get_report(record_id)
    if record is None:
        raise ReportRecordNotFound(f"Report record not found: {record_id}")
    path = Path(str(record.get("html_report_path") or ""))
    if not path.exists():
        raise ReportRecordNotFound(f"HTML report not found: {record_id}")
    return path


def _find_record_target(history: dict[str, Any], path: Path, record_id: str) -> dict[str, Any] | None:
    history_type = str(history.get("history_type") or "unknown").lower()
    response = history.get("response") if isinstance(history.get("response"), dict) else {}
    if history_type == "batch" or response.get("mode") == "batch":
        results = response.get("results") if isinstance(response.get("results"), list) else []
        for index, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            candidate = _record_id(history_file=path.name, result=result, raw=item, index=index)
            if candidate == record_id:
                return result
        return None
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    if isinstance(result, dict):
        candidate = _record_id(history_file=path.name, result=result, raw=history)
        if candidate == record_id:
            return result
    return None


def update_review(record_id: str, payload: dict[str, Any], history_dir: Path | None = None) -> dict[str, Any]:
    status = str(payload.get("review_status") or "reviewed").strip().lower()
    if status not in REVIEW_STATUSES:
        raise ValueError(f"review_status must be one of: {', '.join(sorted(REVIEW_STATUSES))}.")
    note = str(payload.get("review_note") or "")
    reviewer = str(payload.get("reviewed_by") or payload.get("reviewer") or "local_user")
    if history_dir is None:
        bootstrap_sqlite_from_history()
        record = report_store.update_report_review(
            record_id,
            {
                "review_status": status,
                "review_note": note,
                "reviewed_by": reviewer,
            },
        )
        if record is None:
            raise ReportRecordNotFound(f"Report record not found: {record_id}")
        return public_report_record(record)
    source = Path(history_dir or HISTORY_DIR)
    if not source.exists():
        raise ReportRecordNotFound(f"Report record not found: {record_id}")

    for path in sorted(source.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        history = _read_json(path)
        if history is None:
            continue
        target = _find_record_target(history, path, record_id)
        if target is None:
            continue
        target["review_status"] = status
        target["review_note"] = note
        target["reviewed_at"] = now_iso()
        target["reviewer"] = reviewer
        _write_json(path, history)
        refreshed = _read_json(path) or history
        for record in _records_from_history(path, refreshed):
            if record.get("id") == record_id:
                return record
        raise ReportRecordNotFound(f"Report record not found after update: {record_id}")
    raise ReportRecordNotFound(f"Report record not found: {record_id}")


def export_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "id",
        "filename",
        "created_at",
        "final_label",
        "risk_level",
        "confidence",
        "review_status",
        "review_note",
        "reviewed_at",
        "reviewer",
        "report_schema_version",
        "detector_version",
        "model_version",
        "html_report_available",
        "decision_reason",
        "recommendation",
        "user_facing_summary",
    ]
    return [{field: _text(record.get(field), "") for field in fields} for record in records]


def export_csv(records: list[dict[str, Any]]) -> str:
    rows = export_rows(records)
    output = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else [
        "id",
        "filename",
        "created_at",
        "final_label",
        "risk_level",
        "confidence",
        "review_status",
        "review_note",
        "reviewed_at",
        "reviewer",
        "report_schema_version",
        "detector_version",
        "model_version",
        "html_report_available",
        "decision_reason",
        "recommendation",
        "user_facing_summary",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
