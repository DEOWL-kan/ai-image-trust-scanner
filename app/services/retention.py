from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RETENTION_SCHEMA_VERSION = "retention_policy_v1"


def _path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser() if raw else default


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(str(os.getenv(name, str(default))).strip()))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RetentionTarget:
    name: str
    root: Path
    max_age_days: int
    patterns: tuple[str, ...]
    private_data: bool = True


def default_targets() -> list[RetentionTarget]:
    return [
        RetentionTarget(
            name="uploads",
            root=_path_env("MINERVA_UPLOAD_DIR", PROJECT_ROOT / ".tmp" / "api_uploads"),
            max_age_days=_int_env("MINERVA_RETENTION_UPLOAD_DAYS", 7),
            patterns=("*",),
        ),
        RetentionTarget(
            name="api_reports",
            root=_path_env("MINERVA_API_REPORT_DIR", PROJECT_ROOT / ".tmp" / "api_reports"),
            max_age_days=_int_env("MINERVA_RETENTION_API_REPORT_DAYS", 30),
            patterns=("*",),
        ),
        RetentionTarget(
            name="api_history",
            root=_path_env("MINERVA_API_HISTORY_DIR", PROJECT_ROOT / ".tmp" / "api_history"),
            max_age_days=_int_env("MINERVA_RETENTION_API_HISTORY_DAYS", 90),
            patterns=("*.json",),
        ),
        RetentionTarget(
            name="html_reports",
            root=_path_env("MINERVA_HTML_REPORT_DIR", PROJECT_ROOT / ".tmp" / "html_reports"),
            max_age_days=_int_env("MINERVA_RETENTION_HTML_REPORT_DAYS", 90),
            patterns=("*.html",),
        ),
        RetentionTarget(
            name="c2pa_manifests",
            root=_path_env("MINERVA_C2PA_MANIFEST_DIR", PROJECT_ROOT / ".tmp" / "c2pa_manifests"),
            max_age_days=_int_env("MINERVA_RETENTION_C2PA_MANIFEST_DAYS", 180),
            patterns=("*",),
        ),
    ]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _iter_files(target: RetentionTarget) -> Iterable[Path]:
    root = target.root
    if not root.exists() or not root.is_dir():
        return []
    files: dict[Path, None] = {}
    for pattern in target.patterns:
        for path in root.rglob(pattern):
            if path.is_symlink() or not path.is_file():
                continue
            files[path] = None
    return sorted(files)


def _file_item(path: Path, root: Path, now_ts: float) -> dict[str, Any]:
    stat = path.stat()
    age_days = max(0.0, (now_ts - stat.st_mtime) / 86400.0)
    return {
        "path": str(path),
        "relative_path": path.relative_to(root).as_posix(),
        "size_bytes": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "age_days": round(age_days, 3),
    }


def build_retention_plan(
    *,
    targets: list[RetentionTarget] | None = None,
    now_ts: float | None = None,
    include_candidates: bool = True,
) -> dict[str, Any]:
    now = float(now_ts if now_ts is not None else datetime.now(tz=timezone.utc).timestamp())
    target_summaries = []
    totals = {
        "scanned_files": 0,
        "would_delete_files": 0,
        "would_delete_bytes": 0,
    }
    for target in targets or default_targets():
        root = target.root.expanduser()
        target_total = 0
        delete_items = []
        missing = not root.exists()
        for path in _iter_files(RetentionTarget(target.name, root, target.max_age_days, target.patterns, target.private_data)):
            target_total += 1
            item = _file_item(path, root, now)
            if item["age_days"] >= target.max_age_days:
                delete_items.append(item)
        totals["scanned_files"] += target_total
        totals["would_delete_files"] += len(delete_items)
        totals["would_delete_bytes"] += sum(int(item["size_bytes"]) for item in delete_items)
        target_summaries.append(
            {
                "name": target.name,
                "root": str(root),
                "max_age_days": target.max_age_days,
                "patterns": list(target.patterns),
                "private_data": target.private_data,
                "missing": missing,
                "scanned_files": target_total,
                "would_delete_files": len(delete_items),
                "would_delete_bytes": sum(int(item["size_bytes"]) for item in delete_items),
                "candidates": delete_items if include_candidates else [],
            }
        )
    return {
        "schema_version": RETENTION_SCHEMA_VERSION,
        "created_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "apply": False,
        "totals": totals,
        "targets": target_summaries,
    }


def apply_retention_plan(plan: dict[str, Any]) -> dict[str, Any]:
    deleted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for target in plan.get("targets") or []:
        root = Path(str(target.get("root") or "")).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        for item in target.get("candidates") or []:
            path = Path(str(item.get("path") or "")).expanduser()
            if not _is_within(path, root):
                errors.append({"path": str(path), "error": "candidate is outside configured target root"})
                continue
            if path.is_symlink() or not path.is_file():
                continue
            try:
                path.unlink()
                deleted.append(item)
            except OSError as exc:
                errors.append({"path": str(path), "error": str(exc)})
    totals = dict(plan.get("totals") or {})
    totals["deleted_files"] = len(deleted)
    totals["deleted_bytes"] = sum(int(item.get("size_bytes") or 0) for item in deleted)
    return {
        **plan,
        "apply": True,
        "totals": totals,
        "deleted": deleted,
        "errors": errors,
    }


def run_retention_policy(
    *,
    apply: bool = False,
    targets: list[RetentionTarget] | None = None,
    include_candidates: bool = True,
) -> dict[str, Any]:
    plan = build_retention_plan(targets=targets, include_candidates=include_candidates or apply)
    if not apply:
        return plan
    return apply_retention_plan(plan)
