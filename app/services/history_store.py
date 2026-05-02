from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = PROJECT_ROOT / "outputs" / "api_history"
API_CONTRACT_VERSION = "v1"


class HistoryStoreError(Exception):
    """Base class for history store errors."""


class HistoryNotFoundError(HistoryStoreError):
    """Raised when a requested history JSON file does not exist."""


class InvalidHistoryFilenameError(HistoryStoreError):
    """Raised when a requested filename is not safe to read."""


class CorruptHistoryError(HistoryStoreError):
    """Raised when a history JSON file cannot be decoded."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def started_timer() -> float:
    return perf_counter()


def duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def new_history_id(history_type: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{history_type}_{timestamp}_{suffix}"


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def save_history(
    *,
    history_type: str,
    response: dict[str, Any],
    request: dict[str, Any],
    duration_ms_value: float,
    history_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, str]:
    if history_type not in {"single", "batch"}:
        raise ValueError("history_type must be 'single' or 'batch'.")

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = history_id or new_history_id(history_type)
    path = HISTORY_DIR / f"{safe_id}.json"
    while path.exists():
        safe_id = new_history_id(history_type)
        path = HISTORY_DIR / f"{safe_id}.json"

    payload = {
        "history_type": history_type,
        "api_version": API_CONTRACT_VERSION,
        "created_at": created_at or now_iso(),
        "request": request,
        "response": response,
        "runtime": {
            "duration_ms": duration_ms_value,
            "service": "fastapi",
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "filename": path.name,
        "path": _relative_path(path),
    }


def _safe_history_path(filename: str) -> Path:
    name = Path(filename).name
    if not name or name != filename or Path(filename).suffix.lower() != ".json":
        raise InvalidHistoryFilenameError("Only JSON filenames inside outputs/api_history can be read.")

    path = (HISTORY_DIR / name).resolve()
    history_root = HISTORY_DIR.resolve()
    if path.parent != history_root:
        raise InvalidHistoryFilenameError("Only JSON filenames inside outputs/api_history can be read.")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorruptHistoryError(f"History JSON is damaged: {path.name}") from exc
    if not isinstance(data, dict):
        raise CorruptHistoryError(f"History JSON must contain an object: {path.name}")
    return data


def read_history(filename: str) -> dict[str, Any]:
    path = _safe_history_path(filename)
    if not path.exists():
        raise HistoryNotFoundError(f"History file not found: {filename}")
    return _read_json(path)


def list_history(limit: int = 20, history_type: str = "all") -> dict[str, Any]:
    if history_type not in {"single", "batch", "all"}:
        raise ValueError("history_type must be single, batch, or all.")

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    safe_limit = max(1, min(int(limit), 100))
    files = sorted(HISTORY_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)

    items: list[dict[str, Any]] = []
    total_found = 0
    for path in files:
        try:
            data = _read_json(path)
        except CorruptHistoryError:
            data = {
                "history_type": "unknown",
                "created_at": None,
                "request": {},
                "response": {},
            }

        item_type = str(data.get("history_type") or "unknown")
        if history_type != "all" and item_type != history_type:
            continue

        total_found += 1
        if len(items) >= safe_limit:
            continue

        response = data.get("response") if isinstance(data.get("response"), dict) else {}
        request = data.get("request") if isinstance(data.get("request"), dict) else {}
        items.append(
            {
                "filename": path.name,
                "history_type": item_type,
                "created_at": data.get("created_at"),
                "mode": response.get("mode") or request.get("mode"),
                "total": response.get("total") or request.get("input_count"),
                "succeeded": response.get("succeeded"),
                "failed": response.get("failed"),
                "path": _relative_path(path),
            }
        )

    return {
        "api_version": API_CONTRACT_VERSION,
        "total_found": total_found,
        "limit": safe_limit,
        "items": items,
    }
