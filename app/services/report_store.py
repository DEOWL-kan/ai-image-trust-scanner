from __future__ import annotations

import html
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.history_store import now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DB_PATH = PROJECT_ROOT / "data" / "app" / "reports.sqlite3"
HTML_REPORT_DIR = PROJECT_ROOT / "outputs" / "html_reports"
REPORT_SCHEMA_VERSION = "v1"
DETECTOR_VERSION = "detector.day29"
MODEL_VERSION = "lightweight-baseline.no-pretrained"
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

JSON_FIELDS = {
    "decision_reason",
    "debug_evidence",
    "report_payload_json",
    "export_payload_json",
}


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or REPORT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                image_name TEXT,
                image_path TEXT,
                file_sha256 TEXT,
                final_label TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                confidence REAL,
                decision_reason TEXT,
                recommendation TEXT,
                user_facing_summary TEXT,
                technical_explanation TEXT,
                debug_evidence TEXT,
                report_title TEXT,
                report_summary TEXT,
                html_report_path TEXT,
                html_report_available INTEGER NOT NULL DEFAULT 0,
                report_payload_json TEXT,
                export_payload_json TEXT,
                review_status TEXT NOT NULL,
                review_note TEXT,
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_updated_at TEXT,
                report_schema_version TEXT NOT NULL,
                detector_version TEXT NOT NULL,
                model_version TEXT NOT NULL,
                history_file TEXT,
                history_type TEXT,
                batch_id TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_risk_level ON reports(risk_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_final_label ON reports(final_label)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_review_status ON reports(review_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_source_type ON reports(source_type)")


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except Exception:
        return value


def normalize_final_label(value: Any) -> str:
    label = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
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


def default_review_status(final_label: Any, risk_level: Any) -> str:
    label = normalize_final_label(final_label)
    risk = normalize_risk_level(risk_level)
    if risk == "high" or label == "uncertain":
        return "pending_review"
    return "unreviewed"


def _text(value: Any, fallback: str = "") -> str:
    if value in (None, ""):
        return fallback
    if isinstance(value, list):
        return "; ".join(_text(item, "") for item in value).strip("; ") or fallback
    if isinstance(value, dict):
        for key in ("message", "summary", "explanation", "action", "code"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _html_report(record: dict[str, Any]) -> str:
    payload = record.get("report_payload_json") or {}
    raw_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(record.get("report_title") or "AI Image Trust Scanner Report"))}</title>
  <style>
    body {{ margin: 0; background: #f5f7fb; color: #102033; font-family: Arial, "Microsoft YaHei", sans-serif; line-height: 1.55; }}
    main {{ width: min(980px, calc(100% - 40px)); margin: 32px auto; }}
    section, header {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 20px; margin-bottom: 14px; }}
    h1 {{ margin: 0 0 6px; font-size: 26px; }} h2 {{ margin: 0 0 10px; font-size: 16px; color: #475569; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .cell {{ border-top: 1px solid #e6edf5; padding-top: 10px; overflow-wrap: anywhere; }}
    .cell span {{ display: block; color: #64748b; font-size: 12px; font-weight: 700; }}
    pre {{ overflow: auto; max-height: 520px; border-radius: 8px; background: #f1f5f9; padding: 14px; }}
    @media (max-width: 680px) {{ main {{ width: calc(100% - 24px); }} .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{html.escape(str(record.get("report_title") or "检测报告"))}</h1>
      <p>{html.escape(str(record.get("report_summary") or record.get("user_facing_summary") or ""))}</p>
      <div class="grid">
        <div class="cell"><span>报告 ID</span><strong>{html.escape(str(record.get("report_id") or ""))}</strong></div>
        <div class="cell"><span>文件名</span><strong>{html.escape(str(record.get("image_name") or ""))}</strong></div>
        <div class="cell"><span>生成时间</span><strong>{html.escape(str(record.get("created_at") or ""))}</strong></div>
      </div>
    </header>
    <section><h2>检测结论</h2><div class="grid">
      <div class="cell"><span>标签</span><strong>{html.escape(str(record.get("final_label") or ""))}</strong></div>
      <div class="cell"><span>风险</span><strong>{html.escape(str(record.get("risk_level") or ""))}</strong></div>
      <div class="cell"><span>置信度</span><strong>{html.escape(str(record.get("confidence") or ""))}</strong></div>
    </div></section>
    <section><h2>判断依据</h2><p>{html.escape(_text(record.get("decision_reason"), ""))}</p></section>
    <section><h2>建议</h2><p>{html.escape(str(record.get("recommendation") or ""))}</p></section>
    <section><h2>技术解释</h2><p>{html.escape(str(record.get("technical_explanation") or ""))}</p></section>
    <section><h2>版本信息</h2><div class="grid">
      <div class="cell"><span>report_schema_version</span><strong>{html.escape(str(record.get("report_schema_version") or ""))}</strong></div>
      <div class="cell"><span>detector_version</span><strong>{html.escape(str(record.get("detector_version") or ""))}</strong></div>
      <div class="cell"><span>model_version</span><strong>{html.escape(str(record.get("model_version") or ""))}</strong></div>
    </div></section>
    <section><h2>完整 JSON</h2><pre>{html.escape(raw_json)}</pre></section>
  </main>
</body>
</html>"""


def write_html_report(record: dict[str, Any]) -> str:
    HTML_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = HTML_REPORT_DIR / f"{record['report_id']}.html"
    path.write_text(_html_report(record), encoding="utf-8")
    return str(path.resolve())


def make_report_record(
    *,
    detection_data: dict[str, Any],
    source_type: str,
    image_path: str | None = None,
    file_sha256: str | None = None,
    report_payload: dict[str, Any] | None = None,
    export_payload: dict[str, Any] | None = None,
    report_id: str | None = None,
    created_at: str | None = None,
    history_file: str | None = None,
    history_type: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    now = now_iso()
    final_label = normalize_final_label(detection_data.get("final_label"))
    risk_level = normalize_risk_level(detection_data.get("risk_level"))
    confidence = normalize_confidence(detection_data.get("confidence"))
    record = {
        "report_id": str(report_id or detection_data.get("report_id") or detection_data.get("id") or uuid.uuid4()),
        "created_at": str(created_at or detection_data.get("created_at") or detection_data.get("timestamp") or now),
        "updated_at": now,
        "source_type": str(source_type or "single"),
        "image_name": detection_data.get("image_name") or detection_data.get("filename"),
        "image_path": image_path or detection_data.get("image_path"),
        "file_sha256": file_sha256 or detection_data.get("file_sha256"),
        "final_label": final_label,
        "risk_level": risk_level,
        "confidence": confidence,
        "decision_reason": detection_data.get("decision_reason"),
        "recommendation": _text(detection_data.get("recommendation"), None),
        "user_facing_summary": detection_data.get("user_facing_summary"),
        "technical_explanation": _text(detection_data.get("technical_explanation"), None),
        "debug_evidence": detection_data.get("debug_evidence"),
        "report_title": detection_data.get("report_title") or f"检测报告 - {detection_data.get('filename') or 'image'}",
        "report_summary": detection_data.get("report_summary") or detection_data.get("user_facing_summary"),
        "html_report_path": None,
        "html_report_available": True,
        "report_payload_json": report_payload or detection_data,
        "export_payload_json": export_payload or detection_data,
        "review_status": detection_data.get("review_status") or default_review_status(final_label, risk_level),
        "review_note": detection_data.get("review_note"),
        "reviewed_by": detection_data.get("reviewed_by") or detection_data.get("reviewer"),
        "reviewed_at": detection_data.get("reviewed_at"),
        "review_updated_at": detection_data.get("review_updated_at"),
        "report_schema_version": detection_data.get("report_schema_version") or REPORT_SCHEMA_VERSION,
        "detector_version": detection_data.get("detector_version") or DETECTOR_VERSION,
        "model_version": detection_data.get("model_version") or MODEL_VERSION,
        "history_file": history_file or detection_data.get("history_file"),
        "history_type": history_type or detection_data.get("history_type"),
        "batch_id": batch_id or detection_data.get("batch_id"),
    }
    record["html_report_path"] = write_html_report(record)
    return record


def _db_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    for field in JSON_FIELDS:
        payload[field] = _json_dumps(payload.get(field))
    payload["html_report_available"] = 1 if payload.get("html_report_available") else 0
    return payload


def save_report(record: dict[str, Any], db_path: Path | None = None) -> dict[str, Any]:
    init_db(db_path)
    payload = _db_payload(record)
    fields = [
        "report_id",
        "created_at",
        "updated_at",
        "source_type",
        "image_name",
        "image_path",
        "file_sha256",
        "final_label",
        "risk_level",
        "confidence",
        "decision_reason",
        "recommendation",
        "user_facing_summary",
        "technical_explanation",
        "debug_evidence",
        "report_title",
        "report_summary",
        "html_report_path",
        "html_report_available",
        "report_payload_json",
        "export_payload_json",
        "review_status",
        "review_note",
        "reviewed_by",
        "reviewed_at",
        "review_updated_at",
        "report_schema_version",
        "detector_version",
        "model_version",
        "history_file",
        "history_type",
        "batch_id",
    ]
    placeholders = ", ".join(":" + field for field in fields)
    updates = ", ".join(f"{field}=excluded.{field}" for field in fields if field != "report_id")
    with _connect(db_path) as conn:
        conn.execute(
            f"""
            INSERT INTO reports ({", ".join(fields)})
            VALUES ({placeholders})
            ON CONFLICT(report_id) DO UPDATE SET {updates}
            """,
            {field: payload.get(field) for field in fields},
        )
    return get_report(str(record["report_id"]), db_path=db_path) or record


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    for field in JSON_FIELDS:
        record[field] = _json_loads(record.get(field))
    record["html_report_available"] = bool(record.get("html_report_available"))
    record["id"] = record["report_id"]
    record["filename"] = record.get("image_name")
    record["reviewer"] = record.get("reviewed_by") or ""
    return record


def get_report(report_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    return _row_to_record(row) if row else None


def count_reports(db_path: Path | None = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM reports").fetchone()
    return int(row["count"] if row else 0)


def list_reports(db_path: Path | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM reports").fetchall()
    return [_row_to_record(row) for row in rows]


def update_report_review(report_id: str, payload: dict[str, Any], db_path: Path | None = None) -> dict[str, Any] | None:
    status = str(payload.get("review_status") or "reviewed").strip().lower().replace("-", "_")
    if status not in REVIEW_STATUSES:
        raise ValueError(f"review_status must be one of: {', '.join(sorted(REVIEW_STATUSES))}.")
    note = str(payload.get("review_note") or "")
    reviewer = str(payload.get("reviewed_by") or payload.get("reviewer") or "local_user")
    now = now_iso()
    init_db(db_path)
    with _connect(db_path) as conn:
        result = conn.execute(
            """
            UPDATE reports
            SET review_status = ?,
                review_note = ?,
                reviewed_by = ?,
                reviewed_at = ?,
                review_updated_at = ?,
                updated_at = ?
            WHERE report_id = ?
            """,
            (status, note, reviewer, now, now, now, report_id),
        )
        if result.rowcount == 0:
            return None
    return get_report(report_id, db_path=db_path)
