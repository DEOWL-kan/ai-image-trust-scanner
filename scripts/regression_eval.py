from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from threshold_sweep import (  # noqa: E402
    ImageScore,
    display_path,
    predicted_label,
    run as run_threshold_sweep,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day7 regression evaluation against the Day6 threshold baseline.",
    )
    parser.add_argument(
        "--real-dir",
        type=Path,
        default=Path("data/test_images/real"),
        help="Directory containing real-image test samples. Default: data/test_images/real",
    )
    parser.add_argument(
        "--ai-dir",
        type=Path,
        default=Path("data/test_images/ai"),
        help="Directory containing AI-image test samples. Default: data/test_images/ai",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory for Day7 reports. Default: reports",
    )
    parser.add_argument(
        "--day6-baseline",
        type=Path,
        default=Path("outputs/day6/threshold_calibration.csv"),
        help="Day6 threshold calibration CSV. Default: outputs/day6/threshold_calibration.csv",
    )
    parser.add_argument("--start", default="0.10", help="Threshold start. Default: 0.10")
    parser.add_argument("--end", default="0.90", help="Threshold end. Default: 0.90")
    parser.add_argument("--step", default="0.05", help="Threshold step. Default: 0.05")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def normalize_day6_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "threshold": safe_float(row.get("threshold")),
        "accuracy": safe_float(row.get("accuracy")),
        "precision": safe_float(row.get("precision") or row.get("precision_ai")),
        "recall": safe_float(row.get("recall") or row.get("recall_ai")),
        "f1": safe_float(row.get("f1") or row.get("f1_ai")),
        "true_positive": safe_int(row.get("tp") or row.get("true_positive")),
        "true_negative": safe_int(row.get("tn") or row.get("true_negative")),
        "false_positive": safe_int(row.get("fp") or row.get("false_positive")),
        "false_negative": safe_int(row.get("fn") or row.get("false_negative")),
    }


def choose_best_f1(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            -float(row["f1"]),
            abs(int(row["false_positive"]) - int(row["false_negative"])),
            -float(row["accuracy"]),
            abs(float(row["threshold"]) - 0.5),
            float(row["threshold"]),
        ),
    )[0]


def load_day6_baseline(path: Path) -> tuple[dict[str, Any] | None, str]:
    path = resolve_path(path)
    if not path.exists():
        return None, "未发现 Day6 baseline，因此本次仅生成 Day7 当前版本评估结果。"

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            rows = [normalize_day6_row(row) for row in csv.DictReader(file)]
    except OSError as exc:
        return None, f"Day6 baseline could not be read: {exc}"

    best = choose_best_f1(rows)
    if best is None:
        return None, "Day6 baseline file exists, but no usable threshold rows were found."
    return best, f"Loaded Day6 baseline from `{display_path(path)}`."


def current_best_metrics(result: dict[str, Any]) -> dict[str, Any] | None:
    return result.get("recommendations", {}).get("best_f1_threshold")


def image_scores_from_result(result: dict[str, Any]) -> list[ImageScore]:
    scores: list[ImageScore] = []
    for item in result.get("image_scores", []):
        scores.append(
            ImageScore(
                file_path=str(item.get("file_path", "")),
                ground_truth=str(item.get("ground_truth", "")),
                score=item.get("score"),
                status=str(item.get("status", "")),
                error_message=str(item.get("error_message", "")),
                inference_time_ms=safe_float(item.get("inference_time_ms")),
            )
        )
    return scores


def mistakes_at_threshold(scores: list[ImageScore], threshold: float) -> tuple[list[ImageScore], list[ImageScore]]:
    false_positives: list[ImageScore] = []
    false_negatives: list[ImageScore] = []
    for item in scores:
        if item.status != "success" or item.score is None:
            continue
        prediction = predicted_label(float(item.score), threshold)
        if item.ground_truth == "real" and prediction == "ai":
            false_positives.append(item)
        elif item.ground_truth == "ai" and prediction == "real":
            false_negatives.append(item)
    return false_positives, false_negatives


def format_metric(row: dict[str, Any] | None, field: str) -> str:
    if not row:
        return "N/A"
    value = row.get(field)
    if isinstance(value, int):
        return str(value)
    return f"{safe_float(value):.4f}"


def render_sample_table(title: str, rows: list[ImageScore], threshold: float) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["No samples.", ""])
        return lines

    lines.extend(["| File | Ground Truth | Score | Predicted Label |", "| --- | --- | ---: | --- |"])
    for item in rows:
        score = float(item.score) if item.score is not None else 0.0
        lines.append(
            f"| `{item.file_path}` | {item.ground_truth} | {score:.6f} | {predicted_label(score, threshold)} |"
        )
    lines.append("")
    return lines


def render_report(
    threshold_result: dict[str, Any],
    day6_best: dict[str, Any] | None,
    baseline_note: str,
    report_path: Path,
) -> str:
    current_best = current_best_metrics(threshold_result)
    threshold = safe_float(current_best.get("threshold") if current_best else None)
    scores = image_scores_from_result(threshold_result)
    false_positives, false_negatives = mistakes_at_threshold(scores, threshold)

    comparison_lines = [
        "| Metric | Day6 Baseline | Day7 Current | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in ("threshold", "accuracy", "precision", "recall", "f1", "false_positive", "false_negative"):
        day6_value = format_metric(day6_best, field)
        day7_value = format_metric(current_best, field)
        delta = "N/A"
        if day6_best and current_best:
            delta = f"{safe_float(current_best.get(field)) - safe_float(day6_best.get(field)):.4f}"
        comparison_lines.append(f"| {field} | {day6_value} | {day7_value} | {delta} |")

    dataset = threshold_result.get("dataset", {})
    lines = [
        "# Day7 Regression Evaluation Report",
        "",
        "## Goal",
        "",
        "This report reruns the current detector on the test set and compares the best-F1 operating point with the Day6 threshold baseline when that baseline is available.",
        "",
        "## Baseline Status",
        "",
        f"- {baseline_note}",
        "",
        "## Current Dataset",
        "",
        f"- Real images: {dataset.get('real_count', 0)}",
        f"- AI images: {dataset.get('ai_count', 0)}",
        f"- Total images: {dataset.get('total', 0)}",
        f"- Successful detections: {dataset.get('success_count', 0)}",
        f"- Detection errors: {dataset.get('error_count', 0)}",
        "",
        "## Current Best-F1 Metrics",
        "",
        f"- Recommended threshold: {format_metric(current_best, 'threshold')}",
        f"- Accuracy: {format_metric(current_best, 'accuracy')}",
        f"- Precision: {format_metric(current_best, 'precision')}",
        f"- Recall: {format_metric(current_best, 'recall')}",
        f"- F1: {format_metric(current_best, 'f1')}",
        f"- 真实图误判数量: {len(false_positives)}",
        f"- AI 图漏判数量: {len(false_negatives)}",
        "",
        "## Day6 vs Day7 Comparison",
        "",
        *comparison_lines,
        "",
        *render_sample_table("误判样本列表 Real Images Flagged as AI", false_positives, threshold),
        *render_sample_table("漏判样本列表 AI Images Marked as Real", false_negatives, threshold),
        "## Interpretation",
        "",
        "- This regression report checks score-to-label behavior only; it does not prove real-world detector quality.",
        "- If Day7 metrics match Day6, the current detector is stable relative to the existing small test set.",
        "- Any future detector or scoring change should regenerate this report and inspect false positives and false negatives before adoption.",
        "",
        "## Outputs",
        "",
        f"- `{display_path(report_path)}`",
        f"- `{display_path(Path(threshold_result['outputs']['csv']))}`",
        f"- `{display_path(Path(threshold_result['outputs']['json']))}`",
        f"- `{display_path(Path(threshold_result['outputs']['markdown_report']))}`",
        "",
        f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
        "",
    ]
    return "\n".join(lines)


def run(
    real_dir: Path,
    ai_dir: Path,
    output_dir: Path,
    day6_baseline: Path,
    start: str,
    end: str,
    step: str,
) -> Path:
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    threshold_result = run_threshold_sweep(real_dir, ai_dir, output_dir, start, end, step)
    day6_best, baseline_note = load_day6_baseline(day6_baseline)
    report_path = output_dir / "day7_regression_report.md"
    report_path.write_text(
        render_report(threshold_result, day6_best, baseline_note, report_path),
        encoding="utf-8",
    )
    return report_path


def main() -> int:
    args = parse_args()
    try:
        report_path = run(
            args.real_dir,
            args.ai_dir,
            args.output_dir,
            args.day6_baseline,
            args.start,
            args.end,
            args.step,
        )
    except ValueError as exc:
        print(f"Regression evaluation argument error: {exc}", file=sys.stderr)
        return 1

    print(f"Regression report: {display_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
