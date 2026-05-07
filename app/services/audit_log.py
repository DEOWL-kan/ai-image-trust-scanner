from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.services.history_store import now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_PATH = PROJECT_ROOT / "data" / "app" / "audit_events.jsonl"
logger = logging.getLogger(__name__)


def _clean(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if len(text) > 500:
        return text[:497] + "..."
    return text


def write_audit_event(
    event_type: str,
    *,
    report_id: str | None = None,
    action_status: str = "ok",
    error_message: Any = None,
    old_review_status: Any = None,
    new_review_status: Any = None,
    extra: dict[str, Any] | None = None,
) -> None:
    event = {
        "timestamp": now_iso(),
        "event_type": event_type,
        "report_id": _clean(report_id),
        "action_status": _clean(action_status),
        "error_message": _clean(error_message),
        "old_review_status": _clean(old_review_status),
        "new_review_status": _clean(new_review_status),
    }
    if extra:
        event["extra"] = {str(key): _clean(value) for key, value in extra.items()}
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.warning("Failed to write audit event %s: %s", event_type, exc)
