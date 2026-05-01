from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import (  # noqa: E402
    BASELINE_THRESHOLD,
    FINAL_AI_THRESHOLD,
    FINAL_REAL_THRESHOLD,
    binary_label_at_threshold,
    decide_final_label,
)


DAY10_RESULTS_CSV = PROJECT_ROOT / "reports" / "day10_format_eval_results.csv"
DAY11_RESOLUTION_CSV = PROJECT_ROOT / "reports" / "day11" / "day11_resolution_eval_results.csv"
REPORTS_DIR = PROJECT_ROOT / "reports"
OUTPUT_CSV = REPORTS_DIR / "day12_final_label_outputs.csv"
OUTPUT_JSON = REPORTS_DIR / "day12_final_label_summary.json"
OUTPUT_MD = REPORTS_DIR / "day12_uncertain_decision_report.md"
VALID_LABELS = {"ai", "real"}
OUTPUT_FIELDS = [
    "image_path",
    "file_name",
    "true_label",
    "score",
    "binary_label_at_threshold",
    "final_label",
    "baseline_threshold",
    "final_real_threshold",
    "final_ai_threshold",
    "is_binary_correct",
    "is_final_decided",
    "is_final_correct_when_decided",
    "input_source",
    "source_id",
    "format_group",
    "resolution_group",
    "file_extension",
    "width",
    "height",
    "status",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day12 uncertain final-label decision report.")
    parser.add_argument(
        "--day10-results",
        type=Path,
        default=DAY10_RESULTS_CSV,
        help="Day10 format-control results CSV.",
    )
    parser.add_argument(
        "--day11-resolution-results",
        type=Path,
        default=DAY11_RESOLUTION_CSV,
        help="Day11 resolution-control results CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Output directory. Default: reports",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def normalize_row(row: dict[str, str], input_source: str) -> dict[str, Any]:
    image_path = row.get("image_path", "")
    score = safe_float(row.get("raw_score") or row.get("score"))
    true_label = row.get("true_label", "")
    source_binary = row.get("binary_label_at_threshold") or row.get("binary_pred_baseline")
    status = row.get("status", "")
    error_message = row.get("error_message", "")

    if status == "success" and score is not None:
        binary_label = binary_label_at_threshold(score, BASELINE_THRESHOLD)
        decision = decide_final_label(score)
        final_label = str(decision["final_label"])
        is_binary_correct = binary_label == true_label if true_label in VALID_LABELS else None
        is_final_decided = final_label != "uncertain"
        is_final_correct = None if not is_final_decided else final_label == true_label
    else:
        binary_label = source_binary or ""
        final_label = ""
        is_binary_correct = None
        is_final_decided = None
        is_final_correct = None

    return {
        "image_path": image_path,
        "file_name": Path(image_path).name,
        "true_label": true_label,
        "score": "" if score is None else round(score, 6),
        "binary_label_at_threshold": binary_label,
        "final_label": final_label,
        "baseline_threshold": BASELINE_THRESHOLD,
        "final_real_threshold": FINAL_REAL_THRESHOLD,
        "final_ai_threshold": FINAL_AI_THRESHOLD,
        "is_binary_correct": is_binary_correct,
        "is_final_decided": is_final_decided,
        "is_final_correct_when_decided": is_final_correct,
        "input_source": input_source,
        "source_id": row.get("source_id", ""),
        "format_group": row.get("format_group", ""),
        "resolution_group": row.get("resolution_group", ""),
        "file_extension": Path(image_path).suffix.lower(),
        "width": row.get("width", ""),
        "height": row.get("height", ""),
        "status": status,
        "error_message": error_message,
    }


def collect_rows(day10_results: Path, day11_resolution_results: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    day10_rows = read_csv(day10_results)
    day11_rows = read_csv(day11_resolution_results)
    rows = [
        normalize_row(row, "day10_format_control")
        for row in day10_rows
    ] + [
        normalize_row(row, "day11_resolution_control")
        for row in day11_rows
    ]
    metadata = {
        "day10_results_csv": display_path(day10_results),
        "day10_rows": len(day10_rows),
        "day11_resolution_csv": display_path(day11_resolution_results),
        "day11_resolution_rows": len(day11_rows),
        "missing_inputs": [
            display_path(path)
            for path in (day10_results, day11_resolution_results)
            if not path.exists()
        ],
        "missing_fields": {
            "has_exif": "not present in the normalized Day10/Day11 result CSV files",
        },
    }
    return rows, metadata


def usable_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("status") == "success"
        and row.get("true_label") in VALID_LABELS
        and isinstance(row.get("score"), (int, float))
    ]


def metrics_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = usable_rows(rows)
    total = len(usable)
    final_ai_count = sum(1 for row in usable if row["final_label"] == "ai")
    final_real_count = sum(1 for row in usable if row["final_label"] == "real")
    final_uncertain_count = sum(1 for row in usable if row["final_label"] == "uncertain")
    decided = [row for row in usable if row["final_label"] != "uncertain"]

    binary_tp = sum(1 for row in usable if row["true_label"] == "ai" and row["binary_label_at_threshold"] == "ai")
    binary_tn = sum(1 for row in usable if row["true_label"] == "real" and row["binary_label_at_threshold"] == "real")
    binary_fp = sum(1 for row in usable if row["true_label"] == "real" and row["binary_label_at_threshold"] == "ai")
    binary_fn = sum(1 for row in usable if row["true_label"] == "ai" and row["binary_label_at_threshold"] == "real")

    residual_fp = sum(1 for row in decided if row["true_label"] == "real" and row["final_label"] == "ai")
    residual_fn = sum(1 for row in decided if row["true_label"] == "ai" and row["final_label"] == "real")
    decided_correct = sum(1 for row in decided if row["final_label"] == row["true_label"])

    binary_errors = [
        row for row in usable
        if row["binary_label_at_threshold"] != row["true_label"]
    ]
    binary_error_captured = [
        row for row in binary_errors
        if row["final_label"] == "uncertain"
    ]
    binary_fp_captured = sum(
        1 for row in binary_error_captured
        if row["true_label"] == "real" and row["binary_label_at_threshold"] == "ai"
    )
    binary_fn_captured = sum(
        1 for row in binary_error_captured
        if row["true_label"] == "ai" and row["binary_label_at_threshold"] == "real"
    )

    return {
        "total": total,
        "final_ai_count": final_ai_count,
        "final_real_count": final_real_count,
        "final_uncertain_count": final_uncertain_count,
        "uncertain_rate": safe_ratio(final_uncertain_count, total),
        "coverage_rate": safe_ratio(len(decided), total),
        "binary_accuracy": safe_ratio(binary_tp + binary_tn, total),
        "binary_false_positives": binary_fp,
        "binary_false_negatives": binary_fn,
        "binary_confusion_matrix": {
            "true_ai_pred_ai": binary_tp,
            "true_ai_pred_real": binary_fn,
            "true_real_pred_ai": binary_fp,
            "true_real_pred_real": binary_tn,
        },
        "decided_total": len(decided),
        "decided_accuracy": safe_ratio(decided_correct, len(decided)),
        "residual_fp_after_uncertain": residual_fp,
        "residual_fn_after_uncertain": residual_fn,
        "binary_fp_captured_by_uncertain": binary_fp_captured,
        "binary_fn_captured_by_uncertain": binary_fn_captured,
        "binary_error_capture_rate": safe_ratio(len(binary_error_captured), len(binary_errors)),
    }


def summarize_groups(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            groups[value].append(row)
    return {name: metrics_for(group_rows) for name, group_rows in sorted(groups.items())}


def sample_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_path": row["image_path"],
        "true_label": row["true_label"],
        "score": row["score"],
        "binary_label_at_threshold": row["binary_label_at_threshold"],
        "final_label": row["final_label"],
        "source_id": row.get("source_id", ""),
        "format_group": row.get("format_group", ""),
        "resolution_group": row.get("resolution_group", ""),
    }


def sample_lists(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    usable = usable_rows(rows)
    residual_fp = [
        sample_ref(row) for row in usable
        if row["final_label"] == "ai" and row["true_label"] == "real"
    ]
    residual_fn = [
        sample_ref(row) for row in usable
        if row["final_label"] == "real" and row["true_label"] == "ai"
    ]
    uncertain = [
        sample_ref(row) for row in usable
        if row["final_label"] == "uncertain"
    ]
    uncertain_binary_wrong = [
        sample_ref(row) for row in usable
        if row["final_label"] == "uncertain"
        and row["binary_label_at_threshold"] != row["true_label"]
    ]
    return {
        "residual_false_positives": residual_fp,
        "residual_false_negatives": residual_fn,
        "uncertain_samples": uncertain,
        "uncertain_samples_binary_wrong": uncertain_binary_wrong,
    }


def scenario_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "real_jpeg_exif_unknown": [
            row for row in rows
            if row.get("true_label") == "real"
            and (row.get("file_extension") in {".jpg", ".jpeg"} or str(row.get("format_group", "")).startswith("jpeg"))
        ],
        "ai_png": [
            row for row in rows
            if row.get("true_label") == "ai"
            and (row.get("file_extension") == ".png" or row.get("format_group") == "png")
        ],
        "converted_samples": [
            row for row in rows
            if row.get("input_source") == "day10_format_control" and row.get("format_group") not in {"", "original"}
        ],
        "resized_samples": [
            row for row in rows
            if row.get("input_source") == "day11_resolution_control" or row.get("resolution_group")
        ],
    }


def build_summary(rows: list[dict[str, Any]], input_metadata: dict[str, Any]) -> dict[str, Any]:
    scenarios = scenario_rows(rows)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "policy": {
            "baseline_threshold": BASELINE_THRESHOLD,
            "final_real_threshold": FINAL_REAL_THRESHOLD,
            "final_ai_threshold": FINAL_AI_THRESHOLD,
            "binary_rule": "score >= 0.15 -> ai; score < 0.15 -> real",
            "final_rule": "score >= 0.18 -> ai; score <= 0.12 -> real; otherwise uncertain",
        },
        "input_metadata": input_metadata,
        "overall": metrics_for(rows),
        "scenarios": {name: metrics_for(items) for name, items in scenarios.items()},
        "by_input_source": summarize_groups(rows, "input_source"),
        "by_format_group": summarize_groups(rows, "format_group"),
        "by_resolution_group": summarize_groups(rows, "resolution_group"),
        "by_source_id": summarize_groups(rows, "source_id"),
        "sample_lists": sample_lists(rows),
    }


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / OUTPUT_CSV.name
    output_json = output_dir / OUTPUT_JSON.name
    output_md = output_dir / OUTPUT_MD.name

    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_md.write_text(render_report(summary, output_csv, output_json, output_md), encoding="utf-8")
    return {"csv": output_csv, "json": output_json, "md": output_md}


def metric_table(metrics_by_name: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| group | total | binary_accuracy | FP | FN | decided_total | decided_accuracy | uncertain_rate | coverage_rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in metrics_by_name.items():
        lines.append(
            f"| {name} | {metrics['total']} | {metrics['binary_accuracy']:.4f} | "
            f"{metrics['binary_false_positives']} | {metrics['binary_false_negatives']} | "
            f"{metrics['decided_total']} | {metrics['decided_accuracy']:.4f} | "
            f"{metrics['uncertain_rate']:.4f} | {metrics['coverage_rate']:.4f} |"
        )
    return lines


def sample_table(samples: list[dict[str, Any]], limit: int = 25) -> list[str]:
    if not samples:
        return ["- None."]
    lines = [
        "| image_path | true_label | score | binary | final | source_id | variant |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in samples[:limit]:
        variant = row.get("format_group") or row.get("resolution_group") or ""
        lines.append(
            f"| `{row['image_path']}` | {row['true_label']} | {float(row['score']):.6f} | "
            f"{row['binary_label_at_threshold']} | {row['final_label']} | {row.get('source_id', '')} | {variant} |"
        )
    if len(samples) > limit:
        lines.append(f"| ... {len(samples) - limit} more rows in CSV/JSON |  |  |  |  |  |  |")
    return lines


def render_report(summary: dict[str, Any], output_csv: Path, output_json: Path, output_md: Path) -> str:
    overall = summary["overall"]
    samples = summary["sample_lists"]
    missing_inputs = summary["input_metadata"]["missing_inputs"]
    missing_input_text = ", ".join(f"`{path}`" for path in missing_inputs) if missing_inputs else "None."

    lines = [
        "# Day12 Uncertain Decision Report",
        "",
        "## Goal",
        "",
        "- Baseline @ 0.15 remains the default regression reference.",
        "- `final_label` is an output-layer trusted decision: `ai`, `real`, or `uncertain`.",
        "- `uncertain` is a refusal/review band, not an error category.",
        "- Core detector scoring weights were not modified.",
        "- `balanced_v2_candidate` remains diagnostic only and is not the default model.",
        "",
        "## Decision Policy",
        "",
        f"- `BASELINE_THRESHOLD = {BASELINE_THRESHOLD:.2f}`",
        f"- `FINAL_REAL_THRESHOLD = {FINAL_REAL_THRESHOLD:.2f}`",
        f"- `FINAL_AI_THRESHOLD = {FINAL_AI_THRESHOLD:.2f}`",
        "- Binary baseline: `score >= 0.15 -> ai`, `score < 0.15 -> real`.",
        "- Final label: `score >= 0.18 -> ai`, `score <= 0.12 -> real`, otherwise `uncertain`.",
        "",
        "## Three-Way Label Distribution",
        "",
        f"- final_ai_count: `{overall['final_ai_count']}`",
        f"- final_real_count: `{overall['final_real_count']}`",
        f"- final_uncertain_count: `{overall['final_uncertain_count']}`",
        f"- uncertain_rate: `{overall['uncertain_rate']:.4f}`",
        f"- coverage_rate: `{overall['coverage_rate']:.4f}`",
        "",
        "## Binary Baseline Metrics",
        "",
        f"- binary accuracy: `{overall['binary_accuracy']:.4f}`",
        f"- binary false positives: `{overall['binary_false_positives']}`",
        f"- binary false negatives: `{overall['binary_false_negatives']}`",
        "",
        "| true_label | pred_ai | pred_real |",
        "| --- | ---: | ---: |",
        f"| ai | {overall['binary_confusion_matrix']['true_ai_pred_ai']} | {overall['binary_confusion_matrix']['true_ai_pred_real']} |",
        f"| real | {overall['binary_confusion_matrix']['true_real_pred_ai']} | {overall['binary_confusion_matrix']['true_real_pred_real']} |",
        "",
        "## Decided-Only Metrics",
        "",
        f"- decided_total: `{overall['decided_total']}`",
        f"- decided_accuracy: `{overall['decided_accuracy']:.4f}`",
        f"- residual_fp_after_uncertain: `{overall['residual_fp_after_uncertain']}`",
        f"- residual_fn_after_uncertain: `{overall['residual_fn_after_uncertain']}`",
        "",
        "## Binary Error Capture",
        "",
        f"- binary_fp_captured_by_uncertain: `{overall['binary_fp_captured_by_uncertain']}`",
        f"- binary_fn_captured_by_uncertain: `{overall['binary_fn_captured_by_uncertain']}`",
        f"- binary_error_capture_rate: `{overall['binary_error_capture_rate']:.4f}`",
        "",
        "## Scenario Analysis",
        "",
        *metric_table(summary["scenarios"]),
        "",
        "Notes:",
        "",
        "- `real_jpeg_exif_unknown` covers Real JPEG/JPG rows visible in the current CSV inputs, but the normalized Day10/Day11 CSVs do not include a `has_exif` field, so no-EXIF JPEG cannot be separated yet.",
        "- `converted_samples` comes from Day10 PNG/JPEG controlled variants.",
        "- `resized_samples` comes from Day11 resolution-control variants.",
        "",
        "## By Format Group",
        "",
        *metric_table(summary["by_format_group"]),
        "",
        "## By Resolution Group",
        "",
        *metric_table(summary["by_resolution_group"]),
        "",
        "## Sample-Level Residual False Positives",
        "",
        *sample_table(samples["residual_false_positives"]),
        "",
        "## Sample-Level Residual False Negatives",
        "",
        *sample_table(samples["residual_false_negatives"]),
        "",
        "## Uncertain Samples",
        "",
        *sample_table(samples["uncertain_samples"]),
        "",
        "## Uncertain Samples That Were Binary Errors",
        "",
        *sample_table(samples["uncertain_samples_binary_wrong"]),
        "",
        "## Inputs And Outputs",
        "",
        f"- Missing input files: {missing_input_text}",
        f"- `{display_path(output_csv)}`",
        f"- `{display_path(output_json)}`",
        f"- `{display_path(output_md)}`",
        "",
        f"_Generated at {summary['generated_at']}._",
        "",
    ]
    return "\n".join(lines)


def run(
    day10_results: Path = DAY10_RESULTS_CSV,
    day11_resolution_results: Path = DAY11_RESOLUTION_CSV,
    output_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    day10_results = resolve_path(day10_results)
    day11_resolution_results = resolve_path(day11_resolution_results)
    output_dir = resolve_path(output_dir)
    rows, input_metadata = collect_rows(day10_results, day11_resolution_results)
    summary = build_summary(rows, input_metadata)
    output_paths = write_outputs(rows, summary, output_dir)
    return {"rows": rows, "summary": summary, "output_paths": output_paths}


def main() -> int:
    args = parse_args()
    result = run(args.day10_results, args.day11_resolution_results, args.output_dir)
    summary = result["summary"]["overall"]
    paths = result["output_paths"]
    print(f"Rows: {summary['total']}")
    print(f"Uncertain rate: {summary['uncertain_rate']:.4f}")
    print(f"Coverage rate: {summary['coverage_rate']:.4f}")
    print(f"Decided accuracy: {summary['decided_accuracy']:.4f}")
    print(f"CSV: {display_path(paths['csv'])}")
    print(f"Summary: {display_path(paths['json'])}")
    print(f"Report: {display_path(paths['md'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
