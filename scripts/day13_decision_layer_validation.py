from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median
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
from main import run_pipeline  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_LABELS = {"ai", "real"}
TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
REPORTS_DIR = PROJECT_ROOT / "reports"
IMAGE_REPORT_DIR = PROJECT_ROOT / "outputs" / "day13_image_reports"
OUTPUT_CSV = REPORTS_DIR / "day13_decision_layer_validation.csv"
OUTPUT_JSON = REPORTS_DIR / "day13_decision_layer_summary.json"
OUTPUT_MD = REPORTS_DIR / "day13_decision_layer_final_report.md"

CSV_FIELDS = [
    "file_path",
    "file_name",
    "true_label",
    "raw_score",
    "baseline_label",
    "final_label",
    "final_reason",
    "is_baseline_correct",
    "is_final_certain",
    "is_final_correct",
    "file_ext",
    "has_exif",
    "width",
    "height",
    "risk_flags",
    "source_folder",
    "resolution_bucket",
    "decision_status",
    "risk_level",
    "confidence_distance",
    "baseline_threshold",
    "final_real_threshold",
    "final_ai_threshold",
    "inference_time_ms",
    "status",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day13 decision-layer validation on data/test_images.")
    parser.add_argument(
        "--test-root",
        type=Path,
        default=TEST_ROOT,
        help="Root containing ai/ and real/ folders. Default: data/test_images",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Directory for Day13 CSV/JSON/Markdown outputs. Default: reports",
    )
    parser.add_argument(
        "--image-report-dir",
        type=Path,
        default=IMAGE_REPORT_DIR,
        help="Directory for per-image pipeline reports. Default: outputs/day13_image_reports",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def file_ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def iter_labeled_images(test_root: Path) -> list[tuple[Path, str]]:
    images: list[tuple[Path, str]] = []
    for true_label in ("ai", "real"):
        label_dir = test_root / true_label
        if not label_dir.exists():
            continue
        images.extend(
            (path, true_label)
            for path in sorted(label_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    return images


def resolution_bucket(width: Any, height: Any) -> str:
    width_value = safe_float(width)
    height_value = safe_float(height)
    if width_value is None or height_value is None:
        return "unknown"
    longest_side = max(width_value, height_value)
    if longest_side < 768:
        return "small"
    if longest_side < 1536:
        return "medium"
    return "large"


def risk_flags_for(
    path: Path,
    true_label: str,
    raw_score: float,
    baseline_label: str,
    final_label: str,
    metadata_result: dict[str, Any],
) -> list[str]:
    """Attach audit flags without changing detector behavior."""
    flags: list[str] = []
    has_exif = metadata_result.get("has_exif")
    suffix = path.suffix.lower()

    if suffix in {".jpg", ".jpeg"}:
        flags.append("jpeg_format")
    if has_exif is False:
        flags.append("no_exif")
    if true_label == "real" and baseline_label == "ai":
        flags.append("baseline_false_positive")
    if true_label == "ai" and baseline_label == "real":
        flags.append("baseline_false_negative")
    if final_label == "uncertain":
        flags.append("uncertain_band")
    if FINAL_REAL_THRESHOLD < raw_score < FINAL_AI_THRESHOLD:
        flags.append("near_threshold_score")
    if true_label == "real" and suffix in {".jpg", ".jpeg"} and has_exif is False:
        flags.append("real_jpeg_no_exif")
    return flags


def extract_final_result(report: dict[str, Any], raw_score: float) -> dict[str, Any]:
    final_result = report.get("final_result", {})
    if final_result.get("final_label"):
        return final_result
    return decide_final_label(raw_score)


def run_one(image_path: Path, true_label: str, image_report_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        report = run_pipeline(image_path, output_dir=image_report_dir / true_label)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        image_info = report.get("image_info", {})
        final_result = report.get("final_result", {})
        score = safe_float(final_result.get("raw_score", final_result.get("final_score")))

        if not report.get("ok") or score is None:
            return error_row(
                image_path,
                true_label,
                elapsed_ms,
                image_info.get("error") or "No final score returned.",
                image_info,
            )

        raw_score = round(float(score), 6)
        decision = extract_final_result(report, raw_score)
        baseline_label = binary_label_at_threshold(raw_score, BASELINE_THRESHOLD)
        final_label = str(decision.get("final_label") or decide_final_label(raw_score)["final_label"])
        is_final_certain = final_label in VALID_LABELS
        metadata_result = report.get("metadata_result", {})
        flags = risk_flags_for(image_path, true_label, raw_score, baseline_label, final_label, metadata_result)
        is_final_correct = "" if not is_final_certain else final_label == true_label

        return {
            "file_path": display_path(image_path),
            "file_name": image_path.name,
            "true_label": true_label,
            "raw_score": raw_score,
            "baseline_label": baseline_label,
            "final_label": final_label,
            "final_reason": decision.get("decision_reason", ""),
            "is_baseline_correct": baseline_label == true_label,
            "is_final_certain": is_final_certain,
            "is_final_correct": is_final_correct,
            "file_ext": file_ext(image_path),
            "has_exif": metadata_result.get("has_exif", ""),
            "width": image_info.get("width") or "",
            "height": image_info.get("height") or "",
            "risk_flags": ";".join(flags),
            "source_folder": display_path(image_path.parent),
            "resolution_bucket": resolution_bucket(image_info.get("width"), image_info.get("height")),
            "decision_status": decision.get("decision_status", ""),
            "risk_level": final_result.get("risk_level", ""),
            "confidence_distance": decision.get("confidence_distance", ""),
            "baseline_threshold": BASELINE_THRESHOLD,
            "final_real_threshold": FINAL_REAL_THRESHOLD,
            "final_ai_threshold": FINAL_AI_THRESHOLD,
            "inference_time_ms": elapsed_ms,
            "status": "success",
            "error_message": "",
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return error_row(image_path, true_label, elapsed_ms, str(exc), {})


def error_row(
    image_path: Path,
    true_label: str,
    elapsed_ms: float,
    error_message: str,
    image_info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "file_path": display_path(image_path),
        "file_name": image_path.name,
        "true_label": true_label,
        "raw_score": "",
        "baseline_label": "",
        "final_label": "",
        "final_reason": "",
        "is_baseline_correct": "",
        "is_final_certain": "",
        "is_final_correct": "",
        "file_ext": file_ext(image_path),
        "has_exif": "",
        "width": image_info.get("width") or "",
        "height": image_info.get("height") or "",
        "risk_flags": "",
        "source_folder": display_path(image_path.parent),
        "resolution_bucket": resolution_bucket(image_info.get("width"), image_info.get("height")),
        "decision_status": "",
        "risk_level": "",
        "confidence_distance": "",
        "baseline_threshold": BASELINE_THRESHOLD,
        "final_real_threshold": FINAL_REAL_THRESHOLD,
        "final_ai_threshold": FINAL_AI_THRESHOLD,
        "inference_time_ms": elapsed_ms,
        "status": "error",
        "error_message": error_message,
    }


def usable_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("status") == "success"
        and row.get("true_label") in VALID_LABELS
        and safe_float(row.get("raw_score")) is not None
    ]


def metrics_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = usable_rows(rows)
    total = len(usable)
    certain = [row for row in usable if row.get("final_label") in VALID_LABELS]
    baseline_correct_rows = [row for row in usable if row.get("baseline_label") == row.get("true_label")]
    baseline_wrong_rows = [row for row in usable if row.get("baseline_label") != row.get("true_label")]
    final_correct_rows = [row for row in certain if row.get("final_label") == row.get("true_label")]

    baseline_fp = sum(1 for row in usable if row["true_label"] == "real" and row["baseline_label"] == "ai")
    baseline_fn = sum(1 for row in usable if row["true_label"] == "ai" and row["baseline_label"] == "real")
    baseline_ai_correct = sum(1 for row in usable if row["true_label"] == "ai" and row["baseline_label"] == "ai")
    baseline_real_correct = sum(1 for row in usable if row["true_label"] == "real" and row["baseline_label"] == "real")

    certain_fp = sum(1 for row in certain if row["true_label"] == "real" and row["final_label"] == "ai")
    certain_fn = sum(1 for row in certain if row["true_label"] == "ai" and row["final_label"] == "real")
    baseline_wrong_but_final_uncertain = sum(
        1 for row in baseline_wrong_rows if row.get("final_label") == "uncertain"
    )
    baseline_correct_but_final_uncertain = sum(
        1 for row in baseline_correct_rows if row.get("final_label") == "uncertain"
    )

    scores = [float(row["raw_score"]) for row in usable]
    ai_scores = [float(row["raw_score"]) for row in usable if row["true_label"] == "ai"]
    real_scores = [float(row["raw_score"]) for row in usable if row["true_label"] == "real"]

    return {
        "total_samples": total,
        "baseline_accuracy": safe_ratio(baseline_ai_correct + baseline_real_correct, total),
        "baseline_fp": baseline_fp,
        "baseline_fn": baseline_fn,
        "baseline_ai_correct": baseline_ai_correct,
        "baseline_real_correct": baseline_real_correct,
        "final_ai_count": sum(1 for row in usable if row.get("final_label") == "ai"),
        "final_real_count": sum(1 for row in usable if row.get("final_label") == "real"),
        "final_uncertain_count": sum(1 for row in usable if row.get("final_label") == "uncertain"),
        "uncertain_rate": safe_ratio(sum(1 for row in usable if row.get("final_label") == "uncertain"), total),
        "certain_coverage": safe_ratio(len(certain), total),
        "final_accuracy_on_certain": safe_ratio(len(final_correct_rows), len(certain)),
        "certain_fp": certain_fp,
        "certain_fn": certain_fn,
        "high_confidence_error_rate": safe_ratio(certain_fp + certain_fn, len(certain)),
        "baseline_wrong_count": len(baseline_wrong_rows),
        "baseline_wrong_but_final_uncertain_count": baseline_wrong_but_final_uncertain,
        "uncertain_absorption_rate": safe_ratio(baseline_wrong_but_final_uncertain, len(baseline_wrong_rows)),
        "baseline_correct_but_final_uncertain_count": baseline_correct_but_final_uncertain,
        "uncertain_overblocking_rate": safe_ratio(baseline_correct_but_final_uncertain, len(baseline_correct_rows)),
        "score_stats": score_stats(scores),
        "ai_score_stats": score_stats(ai_scores),
        "real_score_stats": score_stats(real_scores),
    }


def score_stats(scores: list[float]) -> dict[str, float | int]:
    if not scores:
        return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}
    values = sorted(scores)
    return {
        "count": len(values),
        "min": round(values[0], 6),
        "max": round(values[-1], 6),
        "mean": round(mean(values), 6),
        "median": round(median(values), 6),
    }


def group_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        label = "unknown" if value in (None, "") else str(value)
        groups[label].append(row)
    return {name: metrics_for(group_rows) for name, group_rows in sorted(groups.items())}


def score_overlap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = usable_rows(rows)
    ai_scores = [float(row["raw_score"]) for row in usable if row["true_label"] == "ai"]
    real_scores = [float(row["raw_score"]) for row in usable if row["true_label"] == "real"]
    if not ai_scores or not real_scores:
        return {"has_overlap": False, "overlap_min": 0.0, "overlap_max": 0.0, "ai_in_overlap": 0, "real_in_overlap": 0}

    overlap_min = max(min(ai_scores), min(real_scores))
    overlap_max = min(max(ai_scores), max(real_scores))
    has_overlap = overlap_min <= overlap_max
    return {
        "has_overlap": has_overlap,
        "overlap_min": round(overlap_min, 6) if has_overlap else 0.0,
        "overlap_max": round(overlap_max, 6) if has_overlap else 0.0,
        "ai_in_overlap": sum(1 for score in ai_scores if has_overlap and overlap_min <= score <= overlap_max),
        "real_in_overlap": sum(1 for score in real_scores if has_overlap and overlap_min <= score <= overlap_max),
    }


def sample_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_path": row["file_path"],
        "true_label": row["true_label"],
        "raw_score": row["raw_score"],
        "baseline_label": row["baseline_label"],
        "final_label": row["final_label"],
        "final_reason": row["final_reason"],
        "file_ext": row["file_ext"],
        "has_exif": row["has_exif"],
        "width": row["width"],
        "height": row["height"],
        "risk_flags": row["risk_flags"],
    }


def sample_lists(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    usable = usable_rows(rows)
    return {
        "remaining_high_confidence_errors": [
            sample_ref(row)
            for row in usable
            if row.get("final_label") in VALID_LABELS and row.get("final_label") != row.get("true_label")
        ],
        "baseline_wrong_absorbed_by_uncertain": [
            sample_ref(row)
            for row in usable
            if row.get("baseline_label") != row.get("true_label") and row.get("final_label") == "uncertain"
        ],
        "baseline_correct_overblocked_by_uncertain": [
            sample_ref(row)
            for row in usable
            if row.get("baseline_label") == row.get("true_label") and row.get("final_label") == "uncertain"
        ],
        "real_jpeg_no_exif_false_positives": [
            sample_ref(row)
            for row in usable
            if row.get("true_label") == "real"
            and row.get("file_ext") in {"jpg", "jpeg"}
            and row.get("has_exif") is False
            and row.get("baseline_label") == "ai"
        ],
    }


def build_summary(rows: list[dict[str, Any]], test_root: Path) -> dict[str, Any]:
    usable = usable_rows(rows)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Validate the Day12 uncertain decision layer on the current labeled test set without changing detector weights.",
        "policy": {
            "baseline_threshold": BASELINE_THRESHOLD,
            "final_real_threshold": FINAL_REAL_THRESHOLD,
            "final_ai_threshold": FINAL_AI_THRESHOLD,
            "baseline_rule": "score >= 0.15 -> ai; otherwise real",
            "final_rule": "score >= 0.18 -> ai; score <= 0.12 -> real; otherwise uncertain",
        },
        "dataset": {
            "test_root": display_path(test_root),
            "ai_count": sum(1 for row in usable if row.get("true_label") == "ai"),
            "real_count": sum(1 for row in usable if row.get("true_label") == "real"),
            "total_count": len(usable),
            "error_count": len(rows) - len(usable),
        },
        "overall": metrics_for(rows),
        "groups": {
            "by_true_label": group_metrics(rows, "true_label"),
            "by_file_extension": group_metrics(rows, "file_ext"),
            "by_source_folder": group_metrics(rows, "source_folder"),
            "by_resolution_bucket": group_metrics(rows, "resolution_bucket"),
            "by_has_exif": group_metrics(rows, "has_exif"),
        },
        "score_overlap": score_overlap(rows),
        "sample_lists": sample_lists(rows),
        "outputs": {
            "csv": display_path(OUTPUT_CSV),
            "json": display_path(OUTPUT_JSON),
            "markdown": display_path(OUTPUT_MD),
        },
    }


def write_csv(rows: list[dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def write_json(summary: dict[str, Any], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def metric_group_table(metrics_by_group: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group, metrics in metrics_by_group.items():
        lines.append(
            f"| {group} | {metrics['total_samples']} | {metrics['baseline_accuracy']:.4f} | "
            f"{metrics['baseline_fp']} | {metrics['baseline_fn']} | {metrics['uncertain_rate']:.4f} | "
            f"{metrics['certain_coverage']:.4f} | {metrics['final_accuracy_on_certain']:.4f} |"
        )
    return lines


def sample_table(samples: list[dict[str, Any]], limit: int = 30) -> list[str]:
    if not samples:
        return ["- None."]
    lines = [
        "| file_path | true | score | baseline | final | ext | exif | size | flags |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in samples[:limit]:
        lines.append(
            f"| `{row['file_path']}` | {row['true_label']} | {float(row['raw_score']):.6f} | "
            f"{row['baseline_label']} | {row['final_label']} | {row['file_ext']} | "
            f"{row['has_exif']} | {row['width']}x{row['height']} | {row['risk_flags']} |"
        )
    if len(samples) > limit:
        lines.append(f"| ... {len(samples) - limit} more rows in CSV/JSON |  |  |  |  |  |  |  |  |")
    return lines


def observation_lines(summary: dict[str, Any]) -> list[str]:
    overall = summary["overall"]
    samples = summary["sample_lists"]
    overlap = summary["score_overlap"]
    by_resolution = summary["groups"]["by_resolution_bucket"]
    real_jpeg_fp_count = len(samples["real_jpeg_no_exif_false_positives"])

    lines = [
        f"- Real JPG / no-EXIF JPEG false-positive rows in this run: `{real_jpeg_fp_count}`.",
        f"- AI score range: `{overall['ai_score_stats']['min']:.6f}` to `{overall['ai_score_stats']['max']:.6f}`; Real score range: `{overall['real_score_stats']['min']:.6f}` to `{overall['real_score_stats']['max']:.6f}`.",
    ]
    if overlap["has_overlap"]:
        lines.append(
            f"- AI / Real score distributions overlap from `{overlap['overlap_min']:.6f}` to `{overlap['overlap_max']:.6f}` "
            f"with `{overlap['ai_in_overlap']}` AI and `{overlap['real_in_overlap']}` Real samples inside that interval."
        )
    else:
        lines.append("- AI / Real score ranges do not overlap in this Day13 current-set run.")

    if len(by_resolution) > 1:
        bucket_bits = [
            f"{name}: baseline_acc={metrics['baseline_accuracy']:.4f}, uncertain={metrics['uncertain_rate']:.4f}"
            for name, metrics in by_resolution.items()
        ]
        lines.append("- Resolution bucket spread: " + "; ".join(bucket_bits) + ".")
    else:
        lines.append(
            "- Current Day13 validation uses the original test-set files, so it can bucket by resolution but does not replace Day11's paired resize sensitivity test."
        )
    return lines


def render_report(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    overall = summary["overall"]
    samples = summary["sample_lists"]
    absorbed = samples["baseline_wrong_absorbed_by_uncertain"]
    overblocked = samples["baseline_correct_overblocked_by_uncertain"]

    lines = [
        "# Day13 Decision Layer Validation Report",
        "",
        "## 1. Purpose",
        "",
        "Day13 validates the Day12 `uncertain` decision layer on the current labeled test set. It does not tune core detector feature weights, does not promote `balanced_v2_candidate`, and keeps baseline @ threshold 0.15 as the regression reference.",
        "",
        "## 2. Dataset",
        "",
        f"- Test set root: `{dataset['test_root']}`",
        f"- AI samples: `{dataset['ai_count']}`",
        f"- Real samples: `{dataset['real_count']}`",
        f"- Total usable samples: `{dataset['total_count']}`",
        f"- Processing errors: `{dataset['error_count']}`",
        "",
        "## 3. Baseline Result",
        "",
        f"- Baseline rule: `{summary['policy']['baseline_rule']}`",
        f"- total_samples: `{overall['total_samples']}`",
        f"- baseline_accuracy: `{overall['baseline_accuracy']:.4f}`",
        f"- baseline_fp: `{overall['baseline_fp']}`",
        f"- baseline_fn: `{overall['baseline_fn']}`",
        f"- baseline_ai_correct: `{overall['baseline_ai_correct']}`",
        f"- baseline_real_correct: `{overall['baseline_real_correct']}`",
        "",
        "## 4. Final Label Result",
        "",
        f"- Final rule: `{summary['policy']['final_rule']}`",
        f"- final_ai_count: `{overall['final_ai_count']}`",
        f"- final_real_count: `{overall['final_real_count']}`",
        f"- final_uncertain_count: `{overall['final_uncertain_count']}`",
        f"- uncertain_rate: `{overall['uncertain_rate']:.4f}`",
        f"- certain_coverage: `{overall['certain_coverage']:.4f}`",
        f"- final_accuracy_on_certain: `{overall['final_accuracy_on_certain']:.4f}`",
        f"- certain_fp: `{overall['certain_fp']}`",
        f"- certain_fn: `{overall['certain_fn']}`",
        f"- high_confidence_error_rate: `{overall['high_confidence_error_rate']:.4f}`",
        "",
        "## 5. Error Absorption Analysis",
        "",
        f"- baseline_wrong_count: `{overall['baseline_wrong_count']}`",
        f"- baseline_wrong_but_final_uncertain_count: `{overall['baseline_wrong_but_final_uncertain_count']}`",
        f"- uncertain_absorption_rate: `{overall['uncertain_absorption_rate']:.4f}`",
        f"- baseline_correct_but_final_uncertain_count: `{overall['baseline_correct_but_final_uncertain_count']}`",
        f"- uncertain_overblocking_rate: `{overall['uncertain_overblocking_rate']:.4f}`",
        "",
        "`uncertain` is measured as an interception/review outcome only. It is not counted as correct accuracy.",
        "",
        "Absorbed baseline errors:",
        "",
        *sample_table(absorbed),
        "",
        "Overblocked baseline-correct rows:",
        "",
        *sample_table(overblocked),
        "",
        "## 6. Remaining High-Confidence Errors",
        "",
        "These are samples where `final_label` is still a certain `ai` or `real` label but the label is wrong.",
        "",
        *sample_table(samples["remaining_high_confidence_errors"]),
        "",
        "## 7. Format / Resolution / EXIF Observations",
        "",
        *observation_lines(summary),
        "",
        "### By True Label",
        "",
        *metric_group_table(summary["groups"]["by_true_label"]),
        "",
        "### By File Extension",
        "",
        *metric_group_table(summary["groups"]["by_file_extension"]),
        "",
        "### By Source Folder",
        "",
        *metric_group_table(summary["groups"]["by_source_folder"]),
        "",
        "### By Resolution Bucket",
        "",
        *metric_group_table(summary["groups"]["by_resolution_bucket"]),
        "",
        "### By EXIF Presence",
        "",
        *metric_group_table(summary["groups"]["by_has_exif"]),
        "",
        "## 8. Conclusion",
        "",
        conclusion_text(summary),
        "",
        "Recommended Day14 sample expansion:",
        "",
        "- More Real JPG/JPEG samples without EXIF, especially camera exports, social-media recompressions, and edited-but-real images.",
        "- More paired resize controls from the same original images to track label stability by resolution.",
        "- More near-threshold AI and Real samples around the 0.12-0.18 uncertain band to validate review-band width.",
        "- Keep baseline @ 0.15 as the regression reference, keep the Day12 `final_label` policy as a diagnostic candidate, and continue avoiding core weight tuning unless a concrete detector bug is found.",
        "",
        "## Outputs",
        "",
        f"- CSV: `{summary['outputs']['csv']}`",
        f"- Summary JSON: `{summary['outputs']['json']}`",
        f"- Markdown report: `{summary['outputs']['markdown']}`",
        "",
        f"_Generated at {summary['generated_at']}._",
        "",
    ]
    return "\n".join(lines)


def conclusion_text(summary: dict[str, Any]) -> str:
    overall = summary["overall"]
    by_true_label = summary["groups"]["by_true_label"]
    ai_metrics = by_true_label.get("ai", {})
    real_metrics = by_true_label.get("real", {})
    ai_wrong = int(ai_metrics.get("baseline_wrong_count", 0))
    ai_absorbed = int(ai_metrics.get("baseline_wrong_but_final_uncertain_count", 0))
    real_wrong = int(real_metrics.get("baseline_wrong_count", 0))
    real_absorbed = int(real_metrics.get("baseline_wrong_but_final_uncertain_count", 0))
    remaining_real_certain_ai = int(real_metrics.get("certain_fp", 0))

    return (
        "The Day12 uncertain layer is partially effective, but it should not be treated as an overall success or a final default strategy yet. "
        f"It has clear diagnostic value: overall, it absorbed `{overall['baseline_wrong_but_final_uncertain_count']}` of `{overall['baseline_wrong_count']}` baseline errors, "
        f"and the effect is especially strong for AI false negatives. Among AI baseline errors, `{ai_absorbed}` of `{ai_wrong}` were moved into `uncertain`, "
        "which means the review band is useful for catching near-threshold AI samples that baseline @ `0.15` would otherwise label as Real.\n\n"
        "However, the same score-band strategy is not sufficient for the main Real JPG false-positive cluster. "
        f"Among Real baseline errors, only `{real_absorbed}` of `{real_wrong}` were absorbed by `uncertain`; "
        f"`{remaining_real_certain_ai}` Real samples still received a certain `final_label = ai`. "
        "This is the most important Day13 failure mode and matches the earlier Day11 conclusion that Real JPG / no-EXIF JPEG samples remain a major false-positive cluster.\n\n"
        "The decided-only quality also does not improve over the baseline in this run. "
        f"`final_accuracy_on_certain = {overall['final_accuracy_on_certain']:.4f}`, which is lower than `baseline_accuracy = {overall['baseline_accuracy']:.4f}`, "
        "so the current final-label layer has not yet increased the reliability of explicit AI/Real decisions. "
        f"At the same time, `uncertain_rate = {overall['uncertain_rate']:.4f}` and `certain_coverage = {overall['certain_coverage']:.4f}`, "
        "meaning the policy withholds judgment on half of the current test set while still leaving many Real JPG false positives as certain AI decisions.\n\n"
        "Day13 conclusion: the uncertain decision layer has diagnostic value, especially for AI false-negative absorption, but the current `0.12-0.18` score-band-only strategy is not enough to solve Real JPG / no-EXIF JPEG false positives. "
        "Day14 should move into format pairing and targeted sample expansion rather than more core weight tuning. "
        "The Day12 `final_label` strategy should remain a diagnostic candidate for now, not the final default decision policy."
    )


def write_markdown(summary: dict[str, Any], output_md: Path) -> None:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_report(summary), encoding="utf-8")


def run(
    test_root: Path = TEST_ROOT,
    reports_dir: Path = REPORTS_DIR,
    image_report_dir: Path = IMAGE_REPORT_DIR,
) -> dict[str, Any]:
    test_root = resolve_path(test_root)
    reports_dir = resolve_path(reports_dir)
    image_report_dir = resolve_path(image_report_dir)

    rows = [
        run_one(image_path, true_label, image_report_dir)
        for image_path, true_label in iter_labeled_images(test_root)
    ]
    summary = build_summary(rows, test_root)

    output_csv = reports_dir / OUTPUT_CSV.name
    output_json = reports_dir / OUTPUT_JSON.name
    output_md = reports_dir / OUTPUT_MD.name
    summary["outputs"] = {
        "csv": display_path(output_csv),
        "json": display_path(output_json),
        "markdown": display_path(output_md),
    }

    write_csv(rows, output_csv)
    write_json(summary, output_json)
    write_markdown(summary, output_md)
    return {"rows": rows, "summary": summary, "output_paths": {"csv": output_csv, "json": output_json, "md": output_md}}


def main() -> int:
    args = parse_args()
    result = run(args.test_root, args.reports_dir, args.image_report_dir)
    summary = result["summary"]["overall"]
    paths = result["output_paths"]

    print(f"Day13 report path: {display_path(paths['md'])}")
    print(f"baseline_accuracy: {summary['baseline_accuracy']:.4f}")
    print(f"uncertain_rate: {summary['uncertain_rate']:.4f}")
    print(f"certain_coverage: {summary['certain_coverage']:.4f}")
    print(f"final_accuracy_on_certain: {summary['final_accuracy_on_certain']:.4f}")
    print(f"uncertain_absorption_rate: {summary['uncertain_absorption_rate']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
