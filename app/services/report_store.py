from __future__ import annotations

import html
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.history_store import now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser() if raw else default


REPORT_DB_PATH = _path_env("MINERVA_REPORT_DB_PATH", PROJECT_ROOT / ".tmp" / "reports.sqlite3")
HTML_REPORT_DIR = _path_env("MINERVA_HTML_REPORT_DIR", PROJECT_ROOT / ".tmp" / "html_reports")
REPORT_SCHEMA_VERSION = "v1"
DETECTOR_VERSION = "detector.day29"
MODEL_VERSION = "lightweight-baseline.no-pretrained"
DETECTOR_RESULT_SCHEMA_VERSION = "detector_result_v2"
DETECTOR_REGISTRY_VERSION = "day38_detector_registry_v1"
MODEL_ADAPTER_VERSION = "model_adapter_v2"
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
    "provenance",
    "detector_results",
    "detector_summary",
    "policy_result",
    "policy_snapshot",
    "report_payload_json",
    "export_payload_json",
}

REPORT_SUMMARY_COLUMNS = (
    "report_id",
    "created_at",
    "updated_at",
    "source_type",
    "image_name",
    "final_label",
    "risk_level",
    "confidence",
    "decision_reason",
    "recommendation",
    "user_facing_summary",
    "technical_explanation",
    "report_summary",
    "html_report_available",
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
)


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
                provenance TEXT,
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
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
        if "provenance" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN provenance TEXT")
        if "detector_result_schema_version" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN detector_result_schema_version TEXT")
        if "detector_results" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN detector_results TEXT")
        if "detector_summary" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN detector_summary TEXT")
        if "detector_registry_version" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN detector_registry_version TEXT")
        if "threshold_profile" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN threshold_profile TEXT")
        if "model_adapter_version" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN model_adapter_version TEXT")
        if "policy_version" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN policy_version TEXT")
        if "policy_result" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN policy_result TEXT")
        if "policy_snapshot" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN policy_snapshot TEXT")


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
    if label in {"uncertain", "unsure", "unknown", "review", "needs_review", "review_needed", "pending_review", "undetermined"}:
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


def _provenance_parts(provenance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(provenance, dict):
        return {}, {}, {}
    if isinstance(provenance.get("verified"), dict):
        return (
            provenance.get("verified") or {},
            provenance.get("unverified_markers") or {},
            provenance.get("diagnostics") or {},
        )
    return (
        {
            "c2pa_present": provenance.get("c2pa_present"),
            "c2pa_readable": provenance.get("c2pa_readable"),
            "c2pa_valid": provenance.get("c2pa_valid"),
            "c2pa_issuer": provenance.get("c2pa_issuer"),
            "c2pa_generator": provenance.get("c2pa_generator"),
            "openai_provenance_detected": provenance.get("openai_provenance_detected"),
            "confidence": provenance.get("provenance_confidence"),
        },
        {
            "binary_c2pa_marker_found": provenance.get("binary_c2pa_marker_found"),
            "binary_openai_marker_found": provenance.get("binary_openai_marker_found"),
            "binary_gpt_image_marker_found": provenance.get("binary_gpt_image_marker_found"),
            "marker_confidence": "weak" if provenance.get("binary_c2pa_marker_found") or provenance.get("binary_openai_marker_found") else "none",
            "used_for_final_decision": False,
        },
        {
            "c2pa_probe_status": provenance.get("c2pa_probe_status"),
            "c2patool_version": provenance.get("c2patool_version"),
            "c2patool_path": provenance.get("c2patool_path"),
            "error": provenance.get("error"),
            "error_detail": provenance.get("error_detail"),
            "stdout_preview": provenance.get("stdout_preview"),
            "stderr_preview": provenance.get("stderr_preview"),
        },
    )


def _html_report(record: dict[str, Any]) -> str:
    payload = record.get("report_payload_json") or {}
    raw_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    verified, markers, diagnostics = _provenance_parts(provenance)
    probe_status = str(diagnostics.get("c2pa_probe_status") or "")
    marker_found = any(
        bool(markers.get(key))
        for key in ("binary_c2pa_marker_found", "binary_openai_marker_found", "binary_gpt_image_marker_found")
    )
    if verified.get("openai_provenance_detected") and verified.get("c2pa_readable"):
        provenance_status = "Verified OpenAI C2PA detected"
        provenance_tier = "Verified provenance"
        provenance_note = "Verified OpenAI C2PA provenance detected. This is strong positive evidence of AI generation."
    elif probe_status == "claim_cbor_decode_error":
        provenance_status = "Unable to verify / claim decode error"
        provenance_tier = "Unable to verify"
        provenance_note = "C2PA data may be present, damaged, unsupported, or unreadable by the local tool. Any binary markers are weak diagnostic evidence only."
    elif marker_found:
        provenance_status = "OpenAI/C2PA binary markers found, but not verified"
        provenance_tier = "Unverified provenance markers"
        provenance_note = "Unverified C2PA/OpenAI binary markers were found, but no readable verified manifest was available."
    elif probe_status == "no_manifest":
        provenance_status = "No readable C2PA metadata found"
        provenance_tier = "Unable to verify"
        provenance_note = "C2PA provenance was not found after transformation. This does not prove the image is authentic; the system falls back to visual/model-based detection."
    elif provenance:
        provenance_status = "Unavailable"
        provenance_tier = "Unable to verify"
        provenance_note = "C2PA data may be missing, damaged, unsupported, or unreadable by the local tool."
    else:
        provenance_status = "Not checked"
        provenance_tier = "Unable to verify"
        provenance_note = ""
    openai_status = "Yes" if verified.get("openai_provenance_detected") else "No"
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
    <section><h2>C2PA Provenance</h2><div class="grid">
      <div class="cell"><span>Evidence tier</span><strong>{html.escape(provenance_tier)}</strong></div>
      <div class="cell"><span>C2PA status</span><strong>{html.escape(provenance_status)}</strong></div>
      <div class="cell"><span>OpenAI provenance</span><strong>{html.escape(openai_status)}</strong></div>
      <div class="cell"><span>Confidence</span><strong>{html.escape(str(verified.get("confidence") or "unknown"))}</strong></div>
      <div class="cell"><span>Generator</span><strong>{html.escape(str(verified.get("c2pa_generator") or "-"))}</strong></div>
      <div class="cell"><span>Issuer</span><strong>{html.escape(str(verified.get("c2pa_issuer") or "-"))}</strong></div>
      <div class="cell"><span>Valid</span><strong>{html.escape(str(verified.get("c2pa_valid") if verified.get("c2pa_valid") is not None else "unknown"))}</strong></div>
    </div><p>{html.escape(str(provenance_note or provenance.get("user_note") or ""))}</p></section>
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
        "provenance": detection_data.get("provenance"),
        "detector_result_schema_version": detection_data.get("detector_result_schema_version") or DETECTOR_RESULT_SCHEMA_VERSION,
        "detector_results": detection_data.get("detector_results") or [],
        "detector_summary": detection_data.get("detector_summary")
        or {
            "schema_version": DETECTOR_RESULT_SCHEMA_VERSION,
            "enabled_count": 0,
            "ok_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "disabled_count": 0,
            "primary_detector": None,
        },
        "detector_registry_version": detection_data.get("detector_registry_version") or DETECTOR_REGISTRY_VERSION,
        "threshold_profile": detection_data.get("threshold_profile") or "default",
        "model_adapter_version": detection_data.get("model_adapter_version") or MODEL_ADAPTER_VERSION,
        "policy_version": detection_data.get("policy_version"),
        "policy_result": detection_data.get("policy_result"),
        "policy_snapshot": detection_data.get("policy_snapshot"),
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
        "provenance",
        "detector_result_schema_version",
        "detector_results",
        "detector_summary",
        "detector_registry_version",
        "threshold_profile",
        "model_adapter_version",
        "policy_version",
        "policy_result",
        "policy_snapshot",
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


def _row_to_summary_record(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    record["html_report_available"] = bool(record.get("html_report_available"))
    record["id"] = record["report_id"]
    record["filename"] = record.get("image_name")
    record["reviewer"] = record.get("reviewed_by") or ""
    return record


def _summary_select_sql() -> str:
    return ", ".join(REPORT_SUMMARY_COLUMNS)


def _count_map(conn: sqlite3.Connection, field: str) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF({field}, ''), 'unknown') AS value, COUNT(*) AS count
        FROM reports
        GROUP BY COALESCE(NULLIF({field}, ''), 'unknown')
        """
    ).fetchall()
    return {str(row["value"]): int(row["count"] or 0) for row in rows}


def _global_summary(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total_records,
          SUM(CASE WHEN review_status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review,
          SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk,
          SUM(CASE WHEN final_label = 'uncertain' THEN 1 ELSE 0 END) AS uncertain
        FROM reports
        """
    ).fetchone()
    return {
        "total_records": int(row["total_records"] or 0) if row else 0,
        "pending_review": int(row["pending_review"] or 0) if row else 0,
        "high_risk": int(row["high_risk"] or 0) if row else 0,
        "uncertain": int(row["uncertain"] or 0) if row else 0,
    }


def _where_sql(
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
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if q and q.strip():
        clauses.append(
            """
            LOWER(
              COALESCE(image_name, '') || ' ' ||
              COALESCE(report_id, '') || ' ' ||
              COALESCE(final_label, '') || ' ' ||
              COALESCE(risk_level, '') || ' ' ||
              COALESCE(decision_reason, '') || ' ' ||
              COALESCE(user_facing_summary, '') || ' ' ||
              COALESCE(technical_explanation, '') || ' ' ||
              COALESCE(recommendation, '')
            ) LIKE ?
            """
        )
        params.append(f"%{q.strip().lower()}%")
    if risk_level:
        clauses.append("risk_level = ?")
        params.append(risk_level)
    if final_label:
        clauses.append("final_label = ?")
        params.append(final_label)
    if review_status:
        clauses.append("review_status = ?")
        params.append(review_status)
    if source_type:
        clauses.append("LOWER(COALESCE(source_type, history_type, '')) = ?")
        params.append(source_type.lower())

    date_value = str(date_range or "").strip().lower()
    today = datetime.now().date()
    if date_value == "today":
        clauses.append("substr(created_at, 1, 10) = ?")
        params.append(today.isoformat())
    elif date_value in {"last_7_days", "7d"}:
        clauses.append("substr(created_at, 1, 10) >= ?")
        params.append((today - timedelta(days=7)).isoformat())
    elif date_value in {"last_30_days", "30d"}:
        clauses.append("substr(created_at, 1, 10) >= ?")
        params.append((today - timedelta(days=30)).isoformat())

    if date_from:
        clauses.append("substr(created_at, 1, 10) >= ?")
        params.append(str(date_from)[:10])
    if date_to:
        clauses.append("substr(created_at, 1, 10) <= ?")
        params.append(str(date_to)[:10])

    confidence_value = str(confidence_range or "").strip().lower()
    if confidence_value in {"gte_0_8", ">=0.8", "high"}:
        clauses.append("confidence >= 0.8")
    elif confidence_value in {"0_5_0_8", "0.5-0.8", "medium"}:
        clauses.append("confidence >= 0.5 AND confidence < 0.8")
    elif confidence_value in {"lt_0_5", "<0.5", "low"}:
        clauses.append("confidence < 0.5")

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(f"({clause.strip()})" for clause in clauses), params


def _order_sql(sort: str | None = None, sort_by: str | None = None, sort_order: str | None = None) -> str:
    if sort_by:
        allowed = {
            "created_at": "created_at",
            "updated_at": "updated_at",
            "image_name": "image_name",
            "filename": "image_name",
            "final_label": "final_label",
            "risk_level": "risk_level",
            "confidence": "confidence",
            "review_status": "review_status",
            "source_type": "source_type",
        }
        key = str(sort_by).lower()
        if key not in allowed:
            raise ValueError(f"sort_by must be one of: {', '.join(sorted(allowed))}.")
        direction = "ASC" if str(sort_order or "desc").lower() == "asc" else "DESC"
        return f"ORDER BY {allowed[key]} {direction}"

    value = str(sort or "newest").lower()
    if value == "oldest":
        return "ORDER BY created_at ASC"
    if value in {"risk_priority", "risk"}:
        return """
        ORDER BY
          CASE risk_level WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
          CASE final_label WHEN 'uncertain' THEN 1 ELSE 0 END DESC,
          created_at DESC
        """
    if value in {"confidence_desc", "confidence_high"}:
        return "ORDER BY COALESCE(confidence, -1) DESC, created_at DESC"
    if value in {"confidence_asc", "confidence_low"}:
        return "ORDER BY COALESCE(confidence, 2) ASC, created_at DESC"
    return "ORDER BY created_at DESC"


def dashboard_snapshot(limit_recent: int = 10, db_path: Path | None = None) -> dict[str, Any]:
    init_db(db_path)
    safe_limit = max(1, min(int(limit_recent), 100))
    with _connect(db_path) as conn:
        overview = conn.execute(
            """
            SELECT
              COUNT(*) AS total_images_processed,
              SUM(CASE WHEN COALESCE(batch_id, '') = '' THEN 1 ELSE 0 END) AS single_detection_count,
              COUNT(DISTINCT NULLIF(batch_id, '')) AS batch_detection_count,
              AVG(COALESCE(confidence, 0.0)) AS average_confidence
            FROM reports
            """
        ).fetchone()
        final_counts = _count_map(conn, "final_label")
        risk_counts = _count_map(conn, "risk_level")
        confidence_rows = conn.execute(
            """
            SELECT bucket, COUNT(*) AS count
            FROM (
              SELECT CASE
                WHEN COALESCE(confidence, 0.0) >= 0.75 THEN 'high_confidence'
                WHEN COALESCE(confidence, 0.0) >= 0.5 THEN 'medium_confidence'
                ELSE 'low_confidence'
              END AS bucket
              FROM reports
            )
            GROUP BY bucket
            """
        ).fetchall()
        confidence_counts = {str(row["bucket"]): int(row["count"] or 0) for row in confidence_rows}
        trend_rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS date, COUNT(*) AS count
            FROM reports
            WHERE COALESCE(created_at, '') != ''
            GROUP BY substr(created_at, 1, 10)
            ORDER BY date ASC
            """
        ).fetchall()
        recent_rows = conn.execute(
            f"""
            SELECT {_summary_select_sql()}
            FROM reports
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        batch_rows = conn.execute(
            """
            SELECT
              batch_id AS id,
              MAX(created_at) AS timestamp,
              COUNT(*) AS total,
              COUNT(*) AS succeeded,
              0 AS failed,
              COALESCE(MAX(history_file), '') AS history_file
            FROM reports
            WHERE COALESCE(batch_id, '') != ''
            GROUP BY batch_id
            ORDER BY MAX(created_at) DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    total_images = int(overview["total_images_processed"] or 0) if overview else 0
    single_count = int(overview["single_detection_count"] or 0) if overview else 0
    batch_count = int(overview["batch_detection_count"] or 0) if overview else 0
    average_confidence = round(float(overview["average_confidence"] or 0.0), 4) if overview else 0.0
    return {
        "results": [_row_to_summary_record(row) for row in recent_rows],
        "batches": [dict(row) for row in batch_rows],
        "single_history_count": single_count,
        "aggregate": {
            "total_detections": single_count + batch_count,
            "single_detection_count": single_count,
            "batch_detection_count": batch_count,
            "total_images_processed": total_images,
            "final_label_distribution": final_counts,
            "risk_level_distribution": risk_counts,
            "confidence_distribution": confidence_counts,
            "average_confidence": average_confidence,
            "daily_trend": [{"date": str(row["date"]), "count": int(row["count"] or 0)} for row in trend_rows],
        },
    }


def search_report_summaries(
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
    db_path: Path | None = None,
) -> dict[str, Any]:
    init_db(db_path)
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    where_sql, params = _where_sql(
        q=q,
        risk_level=risk_level,
        final_label=final_label,
        review_status=review_status,
        source_type=source_type,
        date_range=date_range,
        date_from=date_from,
        date_to=date_to,
        confidence_range=confidence_range,
    )
    order_sql = _order_sql(sort=sort, sort_by=sort_by, sort_order=sort_order)
    with _connect(db_path) as conn:
        summary = _global_summary(conn)
        filtered_row = conn.execute(f"SELECT COUNT(*) AS count FROM reports {where_sql}", params).fetchone()
        rows = conn.execute(
            f"""
            SELECT {_summary_select_sql()}
            FROM reports
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, safe_limit, safe_offset],
        ).fetchall()
    return {
        "items": [_row_to_summary_record(row) for row in rows],
        "total": summary["total_records"],
        "filtered_total": int(filtered_row["count"] or 0) if filtered_row else 0,
        "summary": summary,
        "limit": safe_limit,
        "offset": safe_offset,
    }


def review_queue_summaries(limit: int = 20, db_path: Path | None = None) -> dict[str, Any]:
    init_db(db_path)
    safe_limit = max(1, min(int(limit), 100))
    warning_expr = """
      LOWER(
        COALESCE(decision_reason, '') || ' ' ||
        COALESCE(user_facing_summary, '') || ' ' ||
        COALESCE(technical_explanation, '') || ' ' ||
        COALESCE(recommendation, '')
      )
    """
    where_sql = f"""
    WHERE risk_level = 'high'
       OR final_label = 'uncertain'
       OR review_status = 'pending_review'
       OR confidence IS NULL
       OR confidence < 0.65
       OR {warning_expr} LIKE '%warning%'
       OR {warning_expr} LIKE '%error%'
       OR {warning_expr} LIKE '%uncertain%'
       OR {warning_expr} LIKE '%missing%'
    """
    priority_sql = """
    (
      CASE WHEN risk_level = 'high' THEN 40 ELSE 0 END +
      CASE WHEN final_label = 'uncertain' THEN 35 ELSE 0 END +
      CASE WHEN review_status = 'pending_review' THEN 25 ELSE 0 END +
      CASE WHEN confidence IS NULL OR confidence < 0.65 THEN 15 ELSE 0 END
    )
    """
    with _connect(db_path) as conn:
        total_row = conn.execute(f"SELECT COUNT(*) AS count FROM reports {where_sql}").fetchone()
        rows = conn.execute(
            f"""
            SELECT {_summary_select_sql()}
            FROM reports
            {where_sql}
            ORDER BY {priority_sql} DESC,
              CASE risk_level WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
              COALESCE(confidence, 0.0) ASC,
              created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return {
        "items": [_row_to_summary_record(row) for row in rows],
        "total": int(total_row["count"] or 0) if total_row else 0,
        "schema_version": REPORT_SCHEMA_VERSION,
    }


def get_report(report_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_reports_by_ids(report_ids: list[str], db_path: Path | None = None) -> dict[str, dict[str, Any]]:
    ids = [str(report_id) for report_id in report_ids if str(report_id or "").strip()]
    if not ids:
        return {}
    init_db(db_path)
    records: dict[str, dict[str, Any]] = {}
    with _connect(db_path) as conn:
        for index in range(0, len(ids), 200):
            chunk = ids[index : index + 200]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(f"SELECT * FROM reports WHERE report_id IN ({placeholders})", chunk).fetchall()
            for row in rows:
                record = _row_to_record(row)
                records[str(record.get("report_id"))] = record
    return records


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
