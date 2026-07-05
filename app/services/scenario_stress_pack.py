from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from app.services import report_store
from app.services.history_store import now_iso


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "scenario_stress_pack_v1"
DEFAULT_OUTPUT_DIR = Path(
    os.getenv("MINERVA_SCENARIO_STRESS_DIR", str(PROJECT_ROOT / ".tmp" / "scenario_stress_packs"))
).expanduser()
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SCENARIOS = [
    {
        "scenario": "social_compression",
        "description": "JPEG/WebP-like social platform recompression.",
        "transform": "jpeg_q50",
        "extension": ".jpg",
    },
    {
        "scenario": "screenshot",
        "description": "Screenshot-style rasterization with canvas margins.",
        "transform": "screenshot_sim",
        "extension": ".png",
    },
    {
        "scenario": "crop",
        "description": "Center crop then resize back to original canvas.",
        "transform": "center_crop_75",
        "extension": ".jpg",
    },
    {
        "scenario": "low_light",
        "description": "Brightness reduction with mild contrast adjustment.",
        "transform": "low_light",
        "extension": ".jpg",
    },
    {
        "scenario": "indoor",
        "description": "Warm indoor lighting cast.",
        "transform": "warm_indoor",
        "extension": ".jpg",
    },
    {
        "scenario": "object_closeup",
        "description": "Tight central crop to mimic object close-up uploads.",
        "transform": "closeup_crop_55",
        "extension": ".jpg",
    },
    {
        "scenario": "modern_generator",
        "description": "Generator-audit slice for current AI/provenance-positive samples.",
        "transform": "audit_copy_q90",
        "extension": ".jpg",
    },
]


def _records(records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return records if records is not None else report_store.list_reports()


def _compact_hash(*parts: Any) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_label(value: Any) -> str:
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
    if status in {"confirmed_ai", "false_negative"}:
        return "ai"
    if status in {"confirmed_real", "false_positive"}:
        return "real"
    return None


def _source_path(record: dict[str, Any]) -> Path | None:
    raw = str(record.get("image_path") or "").strip()
    if not raw or raw == "[redacted]":
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS else None


def _risk_score(record: dict[str, Any]) -> tuple[int, str]:
    review_label = _review_label(record)
    label = _normalize_label(record.get("final_label"))
    risk = str(record.get("risk_level") or "").lower()
    confidence = record.get("confidence")
    try:
        conf = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        conf = 0.0
    score = 0
    score += 100 if review_label else 0
    score += 40 if risk == "high" else 0
    score += 35 if label == "review" else 0
    score += 20 if str(record.get("review_status") or "").lower() == "pending_review" else 0
    score += int(conf * 10)
    return score, str(record.get("created_at") or "")


def _candidate_records(records: list[dict[str, Any]], max_sources: int) -> list[dict[str, Any]]:
    with_paths = []
    for record in records:
        path = _source_path(record)
        if path and path.exists() and path.is_file():
            with_paths.append(record)
    with_paths.sort(key=_risk_score, reverse=True)
    return with_paths[: max(0, int(max_sources))]


def _ensure_rgb(image: Any) -> Any:
    return image.convert("RGB") if getattr(image, "mode", "RGB") != "RGB" else image


def _center_crop(image: Any, ratio: float) -> Any:
    width, height = image.size
    crop_w = max(1, int(width * ratio))
    crop_h = max(1, int(height * ratio))
    left = max(0, (width - crop_w) // 2)
    top = max(0, (height - crop_h) // 2)
    return image.crop((left, top, left + crop_w, top + crop_h)).resize((width, height))


def _save_transformed_image(source_path: Path, output_path: Path, transform: str) -> dict[str, Any]:
    from PIL import Image, ImageEnhance, ImageOps

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        image = _ensure_rgb(opened)
        if transform == "jpeg_q50":
            image.save(output_path, format="JPEG", quality=50, optimize=True)
        elif transform == "screenshot_sim":
            max_dim = 1280
            image.thumbnail((max_dim, max_dim))
            canvas = Image.new("RGB", (image.width + 48, image.height + 72), (238, 242, 247))
            canvas.paste(image, (24, 48))
            canvas.save(output_path, format="PNG", optimize=True)
        elif transform == "center_crop_75":
            _center_crop(image, 0.75).save(output_path, format="JPEG", quality=88, optimize=True)
        elif transform == "low_light":
            dark = ImageEnhance.Brightness(image).enhance(0.55)
            dark = ImageEnhance.Contrast(dark).enhance(1.12)
            dark.save(output_path, format="JPEG", quality=88, optimize=True)
        elif transform == "warm_indoor":
            warm = ImageOps.colorize(ImageOps.grayscale(image), black="#24180f", white="#ffd8a8")
            blended = Image.blend(image, warm, 0.28)
            blended.save(output_path, format="JPEG", quality=88, optimize=True)
        elif transform == "closeup_crop_55":
            _center_crop(image, 0.55).save(output_path, format="JPEG", quality=90, optimize=True)
        else:
            image.save(output_path, format="JPEG", quality=90, optimize=True)
        return {
            "width": int(getattr(image, "width", 0)),
            "height": int(getattr(image, "height", 0)),
            "bytes": output_path.stat().st_size if output_path.exists() else 0,
        }


def _scenario_rows_for_record(
    record: dict[str, Any],
    *,
    output_dir: Path,
    write_images: bool,
    include_private_paths: bool,
) -> list[dict[str, Any]]:
    source_path = _source_path(record)
    source_exists = bool(source_path and source_path.exists() and source_path.is_file())
    source_key = _compact_hash(record.get("report_id"), record.get("file_sha256"), record.get("image_name"), source_path)
    predicted_label = _normalize_label(record.get("final_label"))
    review_label = _review_label(record)
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        derived_rel = Path("derived") / scenario["scenario"] / f"{source_key}_{scenario['transform']}{scenario['extension']}"
        derived_path = output_dir / derived_rel
        row = {
            "schema_version": SCHEMA_VERSION,
            "sample_id": f"{source_key}_{scenario['scenario']}",
            "source_sample_id": source_key,
            "report_id": record.get("report_id") or record.get("id"),
            "filename": record.get("image_name") or record.get("filename"),
            "scenario": scenario["scenario"],
            "transform": scenario["transform"],
            "description": scenario["description"],
            "predicted_label": predicted_label,
            "review_label": review_label,
            "review_status": record.get("review_status"),
            "risk_level": record.get("risk_level"),
            "confidence": record.get("confidence"),
            "source_path": str(source_path) if include_private_paths and source_path else "",
            "derived_path": str(derived_path) if include_private_paths else "",
            "derived_relpath": str(derived_rel).replace("\\", "/"),
            "status": "source_missing",
            "error": "",
            "width": None,
            "height": None,
            "bytes": 0,
        }
        if source_exists and write_images:
            try:
                meta = _save_transformed_image(source_path, derived_path, str(scenario["transform"]))
                row.update({"status": "ready", **meta})
            except Exception as exc:
                row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        elif source_exists:
            row["status"] = "planned"
        rows.append(row)
    return rows


def build_scenario_stress_pack(
    records: list[dict[str, Any]] | None = None,
    *,
    output_dir: str | Path | None = None,
    max_sources: int = 50,
    write_images: bool = True,
    include_private_paths: bool = True,
) -> dict[str, Any]:
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_records = _records(records)
    candidates = _candidate_records(source_records, max_sources)
    rows: list[dict[str, Any]] = []
    for record in candidates:
        rows.extend(
            _scenario_rows_for_record(
                record,
                output_dir=out_dir,
                write_images=write_images,
                include_private_paths=include_private_paths,
            )
        )
    status_counts = Counter(str(row.get("status") or "unknown") for row in rows)
    scenario_counts = Counter(str(row.get("scenario") or "unknown") for row in rows)
    label_counts = Counter(str(row.get("review_label") or row.get("predicted_label") or "unknown") for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "output_dir": str(out_dir),
        "source_record_count": len(source_records),
        "selected_source_count": len(candidates),
        "scenario_count": len(SCENARIOS),
        "total": len(rows),
        "write_images": bool(write_images),
        "summary": {
            "status_counts": dict(status_counts),
            "scenario_counts": dict(scenario_counts),
            "label_counts": dict(label_counts),
            "ready_count": int(status_counts.get("ready", 0)),
            "planned_count": int(status_counts.get("planned", 0)),
            "error_count": int(status_counts.get("error", 0)),
        },
        "items": rows,
    }


def _public_row(row: dict[str, Any], include_private_paths: bool = False) -> dict[str, Any]:
    if include_private_paths:
        return dict(row)
    safe = dict(row)
    safe["source_path"] = ""
    safe["derived_path"] = ""
    return safe


def write_scenario_stress_pack_exports(pack: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, str]:
    out_dir = Path(output_dir or pack.get("output_dir") or DEFAULT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "scenario_stress_pack.json"
    compact_path = out_dir / "scenario_stress_pack_compact.json"
    csv_path = out_dir / "scenario_stress_pack.csv"
    summary_path = out_dir / "scenario_stress_pack_summary.md"
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    compact = dict(pack)
    compact["items"] = []
    compact["item_count"] = len(pack.get("items", []))
    compact_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    fields = [
        "sample_id",
        "source_sample_id",
        "report_id",
        "filename",
        "scenario",
        "transform",
        "predicted_label",
        "review_label",
        "review_status",
        "risk_level",
        "confidence",
        "status",
        "derived_relpath",
        "width",
        "height",
        "bytes",
        "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in pack.get("items", []):
            writer.writerow({field: item.get(field, "") for field in fields})
    summary = pack.get("summary") if isinstance(pack.get("summary"), dict) else {}
    lines = [
        "# Scenario Stress Pack Summary",
        "",
        f"- schema_version: {pack.get('schema_version')}",
        f"- created_at: {pack.get('created_at')}",
        f"- source_record_count: {pack.get('source_record_count')}",
        f"- selected_source_count: {pack.get('selected_source_count')}",
        f"- scenario_count: {pack.get('scenario_count')}",
        f"- total: {pack.get('total')}",
        f"- write_images: {pack.get('write_images')}",
        f"- status_counts: {summary.get('status_counts', {})}",
        f"- scenario_counts: {summary.get('scenario_counts', {})}",
        "",
        "Images and derived variants stay under ignored local data directories.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(json_path),
        "compact_json": str(compact_path),
        "csv": str(csv_path),
        "summary": str(summary_path),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _read_csv_head(path: Path, limit: int, include_private_paths: bool = False) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [row for index, row in enumerate(csv.DictReader(handle)) if index < limit]
    except OSError:
        return []
    return [_public_row(row, include_private_paths=include_private_paths) for row in rows]


def read_scenario_stress_pack_export(
    output_dir: str | Path | None = None,
    *,
    limit: int = 200,
    include_private_paths: bool = False,
) -> dict[str, Any] | None:
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    compact_path = out_dir / "scenario_stress_pack_compact.json"
    csv_path = out_dir / "scenario_stress_pack.csv"
    payload = _read_json(compact_path)
    if not payload:
        return None
    payload["items"] = _read_csv_head(csv_path, max(0, int(limit)), include_private_paths=include_private_paths)
    payload["limit"] = max(0, int(limit))
    payload["cached"] = True
    return payload
