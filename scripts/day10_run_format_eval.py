from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import decide_final_label, load_decision_policy  # noqa: E402
from core.score_fusion import load_detector_weight_config  # noqa: E402
from main import run_pipeline  # noqa: E402
from scripts.day9_weight_ablation import profile_score  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
CONTROL_ROOT = PROJECT_ROOT / "data" / "day10_format_control"
REPORTS_DIR = PROJECT_ROOT / "reports"
IMAGE_REPORT_DIR = REPORTS_DIR / "day10_format_eval_image_reports"
OUTPUT_CSV = REPORTS_DIR / "day10_format_eval_results.csv"
OUTPUT_MD = REPORTS_DIR / "day10_format_eval_report.md"
SUMMARY_MD = REPORTS_DIR / "day10_summary.md"
CSV_FIELDS = [
    "image_path",
    "source_id",
    "true_label",
    "format_group",
    "raw_score",
    "binary_pred_baseline",
    "threshold",
    "is_correct",
    "final_label",
    "decision_status",
    "uncertainty_margin",
    "confidence_distance",
    "decision_reason",
    "balanced_v2_candidate_score",
    "balanced_v2_candidate_pred",
    "status",
    "error_message",
    "inference_time_ms",
]


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def image_files(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Missing directory: {directory}")
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def source_id_for(path: Path, true_label: str, format_group: str) -> str:
    stem = path.stem
    for suffix in ("__png", "__jpeg_q95", "__jpeg_q85"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return f"{true_label}/{stem}"


def iter_eval_items() -> list[tuple[Path, str, str]]:
    items: list[tuple[Path, str, str]] = []
    for true_label in ("ai", "real"):
        for path in image_files(TEST_ROOT / true_label):
            items.append((path, true_label, "original"))
        for format_group in ("png", "jpeg_q95", "jpeg_q85"):
            for path in image_files(CONTROL_ROOT / true_label / format_group):
                items.append((path, true_label, format_group))
    return items


def binary_label(score: float, threshold: float) -> str:
    return "ai" if score >= threshold else "real"


def evaluate_one(
    image_path: Path,
    true_label: str,
    format_group: str,
    threshold: float,
    uncertainty_margin: float,
    balanced_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    report_dir = IMAGE_REPORT_DIR / format_group
    try:
        report = run_pipeline(image_path, output_dir=report_dir)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        final_result = report.get("final_result", {})
        raw_score = safe_float(final_result.get("final_score"), -1.0)
        if not report.get("ok") or raw_score < 0:
            return {
                "image_path": display_path(image_path),
                "source_id": source_id_for(image_path, true_label, format_group),
                "true_label": true_label,
                "format_group": format_group,
                "raw_score": "",
                "binary_pred_baseline": "",
                "threshold": f"{threshold:.6f}",
                "is_correct": "",
                "final_label": "",
                "decision_status": "",
                "uncertainty_margin": f"{uncertainty_margin:.6f}",
                "confidence_distance": "",
                "decision_reason": "",
                "balanced_v2_candidate_score": "",
                "balanced_v2_candidate_pred": "",
                "status": "error",
                "error_message": report.get("image_info", {}).get("error") or "No final score returned.",
                "inference_time_ms": elapsed_ms,
            }

        decision = decide_final_label(raw_score, threshold=threshold, uncertainty_margin=uncertainty_margin)
        pred = binary_label(raw_score, threshold)
        balanced_score = ""
        balanced_pred = ""
        if balanced_profile is not None:
            balanced_score_value = profile_score(report, "balanced_v2_candidate", balanced_profile)
            balanced_score = f"{balanced_score_value:.6f}"
            balanced_pred = binary_label(balanced_score_value, threshold)

        return {
            "image_path": display_path(image_path),
            "source_id": source_id_for(image_path, true_label, format_group),
            "true_label": true_label,
            "format_group": format_group,
            "raw_score": f"{raw_score:.6f}",
            "binary_pred_baseline": pred,
            "threshold": f"{threshold:.6f}",
            "is_correct": "yes" if pred == true_label else "no",
            "final_label": decision["final_label"],
            "decision_status": decision["decision_status"],
            "uncertainty_margin": f"{uncertainty_margin:.6f}",
            "confidence_distance": f"{decision['confidence_distance']:.6f}",
            "decision_reason": decision["decision_reason"],
            "balanced_v2_candidate_score": balanced_score,
            "balanced_v2_candidate_pred": balanced_pred,
            "status": "success",
            "error_message": "",
            "inference_time_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "image_path": display_path(image_path),
            "source_id": source_id_for(image_path, true_label, format_group),
            "true_label": true_label,
            "format_group": format_group,
            "raw_score": "",
            "binary_pred_baseline": "",
            "threshold": f"{threshold:.6f}",
            "is_correct": "",
            "final_label": "",
            "decision_status": "",
            "uncertainty_margin": f"{uncertainty_margin:.6f}",
            "confidence_distance": "",
            "decision_reason": "",
            "balanced_v2_candidate_score": "",
            "balanced_v2_candidate_pred": "",
            "status": "error",
            "error_message": str(exc),
            "inference_time_ms": elapsed_ms,
        }


def write_csv(rows: list[dict[str, Any]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0


def metrics_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row["status"] == "success"]
    tp = sum(1 for row in usable if row["true_label"] == "ai" and row["binary_pred_baseline"] == "ai")
    tn = sum(1 for row in usable if row["true_label"] == "real" and row["binary_pred_baseline"] == "real")
    fp = sum(1 for row in usable if row["true_label"] == "real" and row["binary_pred_baseline"] == "ai")
    fn = sum(1 for row in usable if row["true_label"] == "ai" and row["binary_pred_baseline"] == "real")
    total = len(usable)
    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    decided = [row for row in usable if row["decision_status"] == "decided"]
    decided_correct = sum(1 for row in decided if row["final_label"] == row["true_label"])
    return {
        "total": total,
        "errors": len(rows) - total,
        "accuracy": safe_ratio(tp + tn, total),
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
        "decided_accuracy": safe_ratio(decided_correct, len(decided)),
        "coverage": safe_ratio(len(decided), total),
        "uncertain_count": total - len(decided),
        "uncertain_rate": safe_ratio(total - len(decided), total),
    }


def group_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for format_group in ("original", "png", "jpeg_q95", "jpeg_q85"):
        result[format_group] = metrics_for([row for row in rows if row["format_group"] == format_group])
    return result


def average_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["status"] != "success":
            continue
        groups[(row["true_label"], row["format_group"])].append(float(row["raw_score"]))
    return [
        {
            "true_label": true_label,
            "format_group": format_group,
            "count": len(values),
            "avg_raw_score": round(mean(values), 6),
        }
        for (true_label, format_group), values in sorted(groups.items())
    ]


def format_deltas(rows: list[dict[str, Any]]) -> dict[str, float]:
    by_source: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row["status"] != "success" or row["format_group"] == "original":
            continue
        by_source[row["source_id"]][row["format_group"]] = float(row["raw_score"])

    q95_deltas: list[float] = []
    q85_deltas: list[float] = []
    all_deltas: list[float] = []
    for scores in by_source.values():
        if "png" in scores and "jpeg_q95" in scores:
            delta = abs(scores["png"] - scores["jpeg_q95"])
            q95_deltas.append(delta)
            all_deltas.append(delta)
        if "png" in scores and "jpeg_q85" in scores:
            delta = abs(scores["png"] - scores["jpeg_q85"])
            q85_deltas.append(delta)
            all_deltas.append(delta)

    return {
        "mean_abs_delta_png_vs_jpeg_q95": round(mean(q95_deltas), 6) if q95_deltas else 0.0,
        "mean_abs_delta_png_vs_jpeg_q85": round(mean(q85_deltas), 6) if q85_deltas else 0.0,
        "max_delta": round(max(all_deltas), 6) if all_deltas else 0.0,
    }


def render_report(rows: list[dict[str, Any]], threshold: float, uncertainty_margin: float) -> str:
    metrics = group_metrics(rows)
    score_rows = average_scores(rows)
    deltas = format_deltas(rows)
    original_accuracy = metrics["original"]["accuracy"]
    controlled_accuracies = [metrics[group]["accuracy"] for group in ("png", "jpeg_q95", "jpeg_q85")]
    controlled_avg_accuracy = mean(controlled_accuracies) if controlled_accuracies else 0.0
    accuracy_gap = abs(original_accuracy - controlled_avg_accuracy)
    format_sensitive = (
        deltas["mean_abs_delta_png_vs_jpeg_q95"] >= 0.02
        or deltas["mean_abs_delta_png_vs_jpeg_q85"] >= 0.02
        or deltas["max_delta"] >= 0.05
        or accuracy_gap >= 0.10
    )

    lines = [
        "# Day10 Format Control Evaluation",
        "",
        "## Scope",
        "",
        "- Evaluates original images plus controlled PNG, JPEG quality 95, and JPEG quality 85 versions.",
        f"- Baseline threshold: `{threshold:.2f}`",
        f"- Uncertainty margin: `{uncertainty_margin:.2f}`",
        "- `balanced_v2_candidate` is included only as a diagnostic CSV field and is not the default strategy.",
        "",
        "## Metrics By Format Group",
        "",
        "| format_group | accuracy | FP | FN | TP | TN | precision | recall | F1 | decided_accuracy | coverage | uncertain_count | uncertain_rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in ("original", "png", "jpeg_q95", "jpeg_q85"):
        item = metrics[group]
        lines.append(
            f"| {group} | {item['accuracy']:.4f} | {item['fp']} | {item['fn']} | "
            f"{item['tp']} | {item['tn']} | {item['precision']:.4f} | {item['recall']:.4f} | "
            f"{item['f1']:.4f} | {item['decided_accuracy']:.4f} | {item['coverage']:.4f} | "
            f"{item['uncertain_count']} | {item['uncertain_rate']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Average Raw Score",
            "",
            "| true_label | format_group | count | avg_raw_score |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in score_rows:
        lines.append(
            f"| {row['true_label']} | {row['format_group']} | {row['count']} | {row['avg_raw_score']:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Same-Source Format Deltas",
            "",
            f"- mean_abs_delta_png_vs_jpeg_q95: `{deltas['mean_abs_delta_png_vs_jpeg_q95']:.6f}`",
            f"- mean_abs_delta_png_vs_jpeg_q85: `{deltas['mean_abs_delta_png_vs_jpeg_q85']:.6f}`",
            f"- max_delta: `{deltas['max_delta']:.6f}`",
            "",
            "## Conclusion",
            "",
        ]
    )
    if format_sensitive:
        lines.append("- The detector shows meaningful format or encoding sensitivity in this controlled run.")
    else:
        lines.append("- The controlled PNG/JPEG score deltas are small, so this run does not show strong format sensitivity inside the controlled set.")
    if accuracy_gap >= 0.10:
        lines.append(
            "- Original-set results differ materially from the controlled-format results, so the original evaluation is likely biased by source format."
        )
    else:
        lines.append(
            "- Original-set accuracy is not far from the controlled-format average, but the original dataset still has a known format-distribution confound."
        )
    lines.extend(
        [
            "- If PNG/JPEG conversion causes large score movement, treat current detector behavior as format-sensitive.",
            "- If original results differ from controlled PNG/JPEG results, treat the original test-set evaluation as biased.",
            "- Baseline @ 0.15 remains the regression reference; it is not replaced by `balanced_v2_candidate`.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(OUTPUT_CSV)}`",
            f"- `{display_path(OUTPUT_MD)}`",
            f"- `{display_path(IMAGE_REPORT_DIR)}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(rows: list[dict[str, Any]], threshold: float, uncertainty_margin: float) -> None:
    OUTPUT_MD.write_text(render_report(rows, threshold, uncertainty_margin), encoding="utf-8")


def render_summary(rows: list[dict[str, Any]], threshold: float, uncertainty_margin: float) -> str:
    metrics = group_metrics(rows)
    deltas = format_deltas(rows)
    original = metrics["original"]
    format_sensitive = (
        deltas["mean_abs_delta_png_vs_jpeg_q95"] >= 0.02
        or deltas["mean_abs_delta_png_vs_jpeg_q85"] >= 0.02
        or deltas["max_delta"] >= 0.05
    )
    return "\n".join(
        [
            "# Day10 Summary",
            "",
            "## What Changed",
            "",
            "- Added a dataset format audit for `data/test_images/ai` and `data/test_images/real`.",
            "- Added PNG/JPEG controlled copies under `data/day10_format_control/`.",
            "- Added a format-control evaluation that reuses the current detector pipeline.",
            "- Added a default uncertain decision layer and product-facing `final_label` output.",
            "",
            "## Why Dataset Debiasing Matters",
            "",
            "- The current original test set can mix label signal with file-format signal.",
            "- If AI images are mostly PNG and Real images are mostly JPEG, accuracy can reflect encoding/provenance differences instead of genuine visual authenticity detection.",
            "- Controlled PNG/JPEG copies let the same source image be scored under different encodings.",
            "",
            "## PNG/JPEG Format-Control Results",
            "",
            "| format_group | accuracy | FP | FN | TP | TN | decided_accuracy | coverage | uncertain_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *[
                (
                    f"| {group} | {metrics[group]['accuracy']:.4f} | {metrics[group]['fp']} | "
                    f"{metrics[group]['fn']} | {metrics[group]['tp']} | {metrics[group]['tn']} | "
                    f"{metrics[group]['decided_accuracy']:.4f} | {metrics[group]['coverage']:.4f} | "
                    f"{metrics[group]['uncertain_rate']:.4f} |"
                )
                for group in ("original", "png", "jpeg_q95", "jpeg_q85")
            ],
            "",
            "Format deltas:",
            "",
            f"- mean_abs_delta_png_vs_jpeg_q95: `{deltas['mean_abs_delta_png_vs_jpeg_q95']:.6f}`",
            f"- mean_abs_delta_png_vs_jpeg_q85: `{deltas['mean_abs_delta_png_vs_jpeg_q85']:.6f}`",
            f"- max_delta: `{deltas['max_delta']:.6f}`",
            "",
            "## Uncertain Decision Layer",
            "",
            f"- `threshold = {threshold:.2f}`",
            f"- `uncertainty_margin = {uncertainty_margin:.2f}`",
            "- `score >= 0.18` -> `final_label=ai`, `decision_status=decided`",
            "- `score <= 0.12` -> `final_label=real`, `decision_status=decided`",
            "- `0.12 < score < 0.18` -> `final_label=uncertain`, `decision_status=uncertain`",
            "- `uncertain` is a refusal to force a low-confidence hard judgment, not an error.",
            "",
            "## Final Label Output",
            "",
            "- Product-facing outputs now include `raw_score`, `threshold`, `uncertainty_margin`, `binary_label_at_threshold`, `final_label`, `decision_status`, `confidence_distance`, and `decision_reason`.",
            "- Legacy score fields such as `final_score` and Day8 binary prediction fields are preserved for regression continuity.",
            "",
            "## Current Default Strategy",
            "",
            f"- baseline threshold: `{threshold:.2f}`",
            f"- uncertainty_margin: `{uncertainty_margin:.2f}`",
            "- final_label values: `ai`, `real`, `uncertain`",
            "- `balanced_v2_candidate` remains diagnostic only and is not enabled as default.",
            "",
            "## Conclusions Not Supported Yet",
            "",
            "- Do not use the format-biased original test set alone to claim real detector performance.",
            "- Do not promote `balanced_v2_candidate` to the default strategy from the current evidence.",
            f"- Original baseline @ 0.15 accuracy in this run: `{original['accuracy']:.4f}` with FP `{original['fp']}` and FN `{original['fn']}`.",
            f"- Controlled-format sensitivity flag: `{'yes' if format_sensitive else 'no'}`.",
            "",
            "## Day11 Suggestions",
            "",
            "- Expand a debiased balanced test set.",
            "- Ensure both AI and Real classes include PNG and JPEG sources.",
            "- Add compression quality variants, resolution variants, screenshots, and social-platform compressed images.",
            "- Re-run threshold scans only after the debiased set is in place.",
            "",
            "## Day10 Outputs",
            "",
            "- `reports/day10_dataset_format_audit.csv`",
            "- `reports/day10_dataset_format_audit.md`",
            "- `reports/day10_format_control_mapping.csv`",
            "- `reports/day10_format_eval_results.csv`",
            "- `reports/day10_format_eval_report.md`",
            "- `reports/day10_summary.md`",
            "- `data/day10_format_control/`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )


def write_summary(rows: list[dict[str, Any]], threshold: float, uncertainty_margin: float) -> None:
    SUMMARY_MD.write_text(render_summary(rows, threshold, uncertainty_margin), encoding="utf-8")


def run() -> list[dict[str, Any]]:
    config = load_detector_weight_config()
    decision_policy = load_decision_policy(config)
    threshold = decision_policy["threshold"]
    uncertainty_margin = decision_policy["uncertainty_margin"]
    balanced_profile = config.get("profiles", {}).get("balanced_v2_candidate")

    rows = [
        evaluate_one(path, true_label, format_group, threshold, uncertainty_margin, balanced_profile)
        for path, true_label, format_group in iter_eval_items()
    ]
    write_csv(rows)
    write_report(rows, threshold, uncertainty_margin)
    write_summary(rows, threshold, uncertainty_margin)
    return rows


def main() -> int:
    rows = run()
    metrics = group_metrics(rows)
    print(f"Evaluated rows: {len(rows)}")
    for group in ("original", "png", "jpeg_q95", "jpeg_q85"):
        item = metrics[group]
        print(
            f"{group}: accuracy={item['accuracy']:.4f}, FP={item['fp']}, FN={item['fn']}, "
            f"uncertain={item['uncertain_count']}"
        )
    print(f"CSV: {display_path(OUTPUT_CSV)}")
    print(f"Report: {display_path(OUTPUT_MD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
