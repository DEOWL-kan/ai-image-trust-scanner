from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.product_output_schema import build_product_output  # noqa: E402


DEFAULT_V21_CSV = PROJECT_ROOT / "reports" / "day16_1_uncertain_decision_v21_results.csv"
DEFAULT_PRODUCT_JSON = PROJECT_ROOT / "reports" / "day17_product_outputs.json"
DEFAULT_REPORT_JSON = PROJECT_ROOT / "reports" / "day17_selective_evaluation.json"
DEFAULT_REPORT_MD = PROJECT_ROOT / "reports" / "day17_selective_evaluation.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day17 selective evaluation over product-level outputs."
    )
    parser.add_argument(
        "--product-json",
        type=Path,
        default=DEFAULT_PRODUCT_JSON,
        help="Existing Day17 product JSON/JSONL file. If missing, input CSV is used.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_V21_CSV,
        help="Day16.1 v21 CSV used to build product outputs when needed.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_product_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return []


def load_or_build_product_rows(product_path: Path, input_csv: Path) -> tuple[list[dict[str, Any]], str]:
    if product_path.exists():
        return read_product_rows(product_path), str(product_path)
    if not input_csv.exists():
        raise FileNotFoundError(
            f"Missing product JSON {product_path} and input CSV {input_csv}."
        )
    rows = []
    for raw in read_csv_rows(input_csv):
        image_path = str(raw.get("image_path") or "")
        rows.append(
            {
                "image_path": image_path,
                **build_product_output(raw, image_path=image_path, debug=True),
            }
        )
    product_path.parent.mkdir(parents=True, exist_ok=True)
    product_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return rows, str(input_csv)


def debug(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("debug_evidence")
    return value if isinstance(value, dict) else {}


def text_blob(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("image_path") or ""),
        str(row.get("final_label") or ""),
        str(row.get("risk_level") or ""),
        json.dumps(debug(row), ensure_ascii=False, default=str),
    ]
    return " ".join(parts).lower()


def has_format_risk(row: dict[str, Any]) -> bool:
    evidence = debug(row)
    risk_factors = evidence.get("risk_factors") or []
    fmt = (evidence.get("format_info") or {}).get("format")
    exif = (evidence.get("exif_info") or {}).get("has_exif")
    blob = text_blob(row)
    keywords = (
        "jpg",
        "jpeg",
        "no exif",
        "missing_exif",
        "missing metadata",
        "compressed",
        "resolution_instability",
        "format flip",
        "format_and_resolution_flip",
    )
    return (
        str(fmt).lower() in {"jpg", "jpeg"}
        or exif is False
        or any(item in risk_factors for item in ("jpeg_container_or_compression", "missing_exif", "resolution_instability"))
        or any(keyword in blob for keyword in keywords)
    )


def is_resolution_sensitive(row: dict[str, Any]) -> bool:
    evidence = debug(row)
    multi = evidence.get("multi_resolution") or {}
    flags = evidence.get("uncertainty_flags") or []
    risk_factors = evidence.get("risk_factors") or []
    return (
        int(multi.get("resolution_flip_count") or 0) > 0
        or "resolution_flip" in flags
        or "resolution_flip_v21" in flags
        or "resolution_instability" in risk_factors
    )


def summarize_subset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    confidences = [
        float(row.get("confidence"))
        for row in rows
        if isinstance(row.get("confidence"), (int, float))
    ]
    examples = [
        {
            "image_path": row.get("image_path"),
            "final_label": row.get("final_label"),
            "risk_level": row.get("risk_level"),
            "confidence": row.get("confidence"),
            "reason": (row.get("decision_reason") or [])[:2],
        }
        for row in rows[:10]
    ]
    return {
        "total": total,
        "label_distribution": dict(Counter(row.get("final_label", "unknown") for row in rows)),
        "risk_level_distribution": dict(Counter(row.get("risk_level", "unknown") for row in rows)),
        "average_confidence": round(mean(confidences), 4) if confidences else 0.0,
        "uncertain_ratio": round(
            sum(1 for row in rows if row.get("final_label") == "uncertain") / total,
            6,
        ) if total else 0.0,
        "sample_examples": examples,
    }


def build_subsets(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    selectors: dict[str, Callable[[dict[str, Any]], bool]] = {
        "all_samples": lambda row: True,
        "uncertain_samples": lambda row: row.get("final_label") == "uncertain",
        "likely_ai_samples": lambda row: row.get("final_label") == "likely_ai",
        "likely_real_samples": lambda row: row.get("final_label") == "likely_real",
        "medium_risk_samples": lambda row: row.get("risk_level") == "medium",
        "high_risk_samples": lambda row: row.get("risk_level") == "high",
        "possible_format_risk_samples": has_format_risk,
        "resolution_sensitive_samples": is_resolution_sensitive,
    }
    return {
        name: [row for row in rows if predicate(row)]
        for name, predicate in selectors.items()
    }


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    if not rows:
        return ["No rows."]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        values = [str(row.get(field, "")).replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    subset_rows = [
        {
            "subset": name,
            "total": stats["total"],
            "labels": stats["label_distribution"],
            "risks": stats["risk_level_distribution"],
            "avg_confidence": stats["average_confidence"],
            "uncertain_ratio": stats["uncertain_ratio"],
        }
        for name, stats in payload["subsets"].items()
    ]
    lines = [
        "# Day17 Selective Evaluation",
        "",
        "## Day17 Goal",
        "Day17 upgrades detector outputs into a front-end/API-ready product schema and evaluates key risk subsets. It does not re-tune the detector or claim commercial-grade accuracy.",
        "",
        "## Core Detection Policy",
        "No core detection weights, AI/Real score formulas, baseline thresholds, or pretrained model dependencies were modified for this report.",
        "",
        "## Product Schema Fields",
        "- `final_label`: product label mapped to `likely_ai`, `likely_real`, or `uncertain`.",
        "- `risk_level`: product risk bucket, limited to `high`, `medium`, or `low`.",
        "- `confidence`: rule-based decision confidence, not a model probability.",
        "- `decision_reason`: short user-facing reasons for the decision.",
        "- `recommendation`: next action guidance.",
        "- `user_facing_summary`: short explanation for ordinary users.",
        "- `technical_explanation`: developer/reviewer explanation.",
        "- `debug_evidence`: stable debug dictionary for API and front-end panels.",
        "",
        "## Selective Evaluation Results",
        "",
    ]
    lines.extend(markdown_table(
        subset_rows,
        ["subset", "total", "labels", "risks", "avg_confidence", "uncertain_ratio"],
    ))
    lines.extend([
        "",
        "## Frontend/API Readiness",
        "The product output layer is ready to connect to a front-end or API as a stable schema. The confidence field is explicitly a rule-based decision confidence, and debug evidence keeps raw Day16.1 fields available without changing existing reports.",
        "",
        "## Existing Issues",
        "- Accuracy is still limited by the current heuristic detector and overlapping score space.",
        "- Missing EXIF, JPEG compression, and resolution sensitivity can lower interpretability.",
        "- `uncertain` should be treated as a product state, not a failure.",
        "",
        "## Day18 Suggestions",
        "- Add API response examples and front-end debug panel rendering.",
        "- Add a small product copy QA pass for Chinese/English messages.",
        "- Track user-facing false-positive/false-negative examples without changing the core scoring formula.",
        "",
        "## Output Files",
        f"- product_outputs: `{payload['product_outputs_source']}`",
        f"- selective_evaluation_json: `{payload['output_json']}`",
        f"- selective_evaluation_md: `{payload['output_md']}`",
        "",
    ])

    if payload.get("notes"):
        lines.extend(["## Notes", ""])
        lines.extend(f"- {note}" for note in payload["notes"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    product_path = resolve_path(args.product_json)
    input_csv = resolve_path(args.input_csv)
    output_json = resolve_path(args.output_json)
    output_md = resolve_path(args.output_md)

    rows, source = load_or_build_product_rows(product_path, input_csv)
    subsets = build_subsets(rows)
    notes: list[str] = []
    if not subsets["resolution_sensitive_samples"]:
        notes.append(
            "No resolution-sensitive samples were found, or the available fields did not expose resolution flip information."
        )

    payload = {
        "day17_goal": "Selective Evaluation + Product-level Output Schema",
        "core_detection_changes": "none",
        "pretrained_model_dependency_changes": "none",
        "product_outputs_source": source,
        "subsets": {
            name: summarize_subset(items)
            for name, items in subsets.items()
        },
        "notes": notes,
        "output_json": str(output_json),
        "output_md": str(output_md),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(f"selective_evaluation_json: {output_json}")
    print(f"selective_evaluation_md: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
