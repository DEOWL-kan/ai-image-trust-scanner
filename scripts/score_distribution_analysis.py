from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze Day7 final_score distributions as a Day8 preparation step.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/day7_threshold_sweep.json"),
        help="Day7 threshold sweep JSON. Default: reports/day7_threshold_sweep.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/day8_score_distribution_preview.md"),
        help="Markdown output path. Default: reports/day8_score_distribution_preview.md",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of high-real and low-AI samples to list. Default: 5",
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
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input JSON not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input JSON is not valid JSON: {path}") from exc


def grouped_scores(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups = {"real": [], "ai": []}
    for item in payload.get("image_scores", []):
        label = str(item.get("ground_truth", "")).strip().lower()
        score = safe_float(item.get("score"))
        status = str(item.get("status", "")).strip().lower()
        if label in groups and status == "success" and score is not None:
            groups[label].append(
                {
                    "file_path": str(item.get("file_path", "")),
                    "ground_truth": label,
                    "score": score,
                }
            )
    return groups


def stats_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row["score"]) for row in rows]
    if not scores:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
        }
    return {
        "count": len(scores),
        "min": min(scores),
        "max": max(scores),
        "mean": mean(scores),
        "median": median(scores),
        "std": pstdev(scores) if len(scores) > 1 else 0.0,
    }


def fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.6f}"


def score_overlap(real_stats: dict[str, Any], ai_stats: dict[str, Any]) -> dict[str, Any]:
    if real_stats["count"] == 0 or ai_stats["count"] == 0:
        return {"exists": False, "low": None, "high": None, "width": 0.0}
    low = max(float(real_stats["min"]), float(ai_stats["min"]))
    high = min(float(real_stats["max"]), float(ai_stats["max"]))
    exists = low <= high
    return {
        "exists": exists,
        "low": low if exists else None,
        "high": high if exists else None,
        "width": round(high - low, 6) if exists else 0.0,
    }


def find_metric(payload: dict[str, Any], threshold: float) -> dict[str, Any] | None:
    for row in payload.get("threshold_metrics", []):
        value = safe_float(row.get("threshold"))
        if value is not None and abs(value - threshold) < 1e-9:
            return row
    return None


def metric_text(row: dict[str, Any] | None) -> str:
    if not row:
        return "N/A"
    return (
        f"accuracy={float(row.get('accuracy', 0)):.4f}, "
        f"precision={float(row.get('precision', 0)):.4f}, "
        f"recall={float(row.get('recall', 0)):.4f}, "
        f"f1={float(row.get('f1', 0)):.4f}, "
        f"FP={int(row.get('false_positive', 0))}, "
        f"FN={int(row.get('false_negative', 0))}"
    )


def separability_label(real_stats: dict[str, Any], ai_stats: dict[str, Any], overlap: dict[str, Any]) -> str:
    if real_stats["count"] == 0 or ai_stats["count"] == 0:
        return "insufficient_data"
    if overlap["exists"]:
        real_min = float(real_stats["min"])
        real_max = float(real_stats["max"])
        ai_min = float(ai_stats["min"])
        ai_max = float(ai_stats["max"])
        combined_span = max(real_max, ai_max) - min(real_min, ai_min)
        overlap_ratio = overlap["width"] / combined_span if combined_span > 0 else 1.0
        mean_gap = abs(float(ai_stats["mean"]) - float(real_stats["mean"]))
        pooled_std = (float(ai_stats["std"]) + float(real_stats["std"])) / 2
        if overlap_ratio > 0.50 or mean_gap <= pooled_std:
            return "poorly_separable"
        return "partially_separable"
    return "separable_on_current_dataset"


def sample_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No samples."]
    lines = ["| File | Score |", "| --- | ---: |"]
    for row in rows:
        lines.append(f"| `{row['file_path']}` | {float(row['score']):.6f} |")
    return lines


def render_report(
    input_path: Path,
    payload: dict[str, Any],
    real_rows: list[dict[str, Any]],
    ai_rows: list[dict[str, Any]],
    top_n: int,
) -> str:
    real_stats = stats_for(real_rows)
    ai_stats = stats_for(ai_rows)
    overlap = score_overlap(real_stats, ai_stats)
    separability = separability_label(real_stats, ai_stats, overlap)
    highest_real = sorted(real_rows, key=lambda row: float(row["score"]), reverse=True)[:top_n]
    lowest_ai = sorted(ai_rows, key=lambda row: float(row["score"]))[:top_n]

    recommendations = payload.get("recommendations", {})
    best = recommendations.get("best_f1_threshold") or {}
    best_threshold = safe_float(best.get("threshold"))
    threshold_015 = find_metric(payload, 0.15)
    threshold_020 = find_metric(payload, 0.20)

    overlap_text = (
        f"{fmt(overlap['low'])} to {fmt(overlap['high'])} (width {fmt(overlap['width'])})"
        if overlap["exists"]
        else "No numeric overlap on the current dataset."
    )

    lines = [
        "# Day8 Score Distribution Preview",
        "",
        "## Purpose",
        "",
        "This Day8 preparation report analyzes the Day7 `final_score` distribution without changing the detector. It explains why threshold tuning is currently fragile and where optimization should focus next.",
        "",
        "## Inputs",
        "",
        f"- Source JSON: `{display_path(input_path)}`",
        f"- Generated at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## Real Score Distribution",
        "",
        "| Count | Min | Max | Mean | Median | Std |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {real_stats['count']} | {fmt(real_stats['min'])} | {fmt(real_stats['max'])} | {fmt(real_stats['mean'])} | {fmt(real_stats['median'])} | {fmt(real_stats['std'])} |",
        "",
        "## AI Score Distribution",
        "",
        "| Count | Min | Max | Mean | Median | Std |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {ai_stats['count']} | {fmt(ai_stats['min'])} | {fmt(ai_stats['max'])} | {fmt(ai_stats['mean'])} | {fmt(ai_stats['median'])} | {fmt(ai_stats['std'])} |",
        "",
        "## Score Overlap",
        "",
        f"- Overlap interval: {overlap_text}",
        f"- Separability judgment: `{separability}`",
        "",
        "The current real and AI score ranges overlap strongly. This means a single threshold cannot cleanly separate both classes on the current dataset.",
        "",
        "## Highest-Scoring Real Samples",
        "",
        *sample_table(highest_real),
        "",
        "These are the real images most likely to become false positives when the threshold is lowered.",
        "",
        "## Lowest-Scoring AI Samples",
        "",
        *sample_table(lowest_ai),
        "",
        "These are the AI images most likely to become false negatives when the threshold is raised.",
        "",
        "## Why 0.15 Is Currently Best",
        "",
        f"- Best-F1 threshold from Day7: `{fmt(best_threshold)}`",
        f"- Metrics at 0.15: {metric_text(threshold_015)}",
        "",
        "The 0.15 threshold catches most AI samples while still preserving some true negatives. It is not a clean boundary; it is simply the least-bad point among the scanned thresholds for this small dataset.",
        "",
        "## Why Performance Drops After 0.20",
        "",
        f"- Metrics at 0.20: {metric_text(threshold_020)}",
        "",
        "Most AI samples have scores below or near 0.20, so raising the threshold quickly turns many AI images into false negatives. At the same time, several real images sit above 0.15, so lowering the threshold produces many false positives.",
        "",
        "## Main Problems in Current final_score",
        "",
        "- The score is compressed into a narrow low range rather than spreading real and AI images apart.",
        "- Frequency features dominate many examples, but they do not consistently separate real and AI images.",
        "- Metadata and forensic heuristics are intentionally weak, so they provide limited class separation.",
        "- The placeholder model score is excluded from fusion, so there is no trained detector signal.",
        "- Day5 and Day6 analysis improves explainability and calibration, but does not change `final_score`.",
        "",
        "## Next Optimization Suggestions",
        "",
        "- Before changing weights, compare component scores for the highest-real and lowest-AI samples.",
        "- Add a component-level diagnostic report that lists metadata, forensic, frequency, and model scores per image.",
        "- Consider an uncertainty band around 0.15 instead of forcing a binary label for overlapping scores.",
        "- For Day8, optimize score separation first, then recalibrate thresholds afterward.",
        "- Keep Day7 and this Day8 preview as regression baselines for future changes.",
        "",
    ]
    return "\n".join(lines)


def run(input_path: Path, output_path: Path, top_n: int) -> Path:
    input_path = resolve_path(input_path)
    output_path = resolve_path(output_path)
    payload = load_payload(input_path)
    groups = grouped_scores(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_report(input_path, payload, groups["real"], groups["ai"], max(top_n, 1)),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    args = parse_args()
    try:
        output_path = run(args.input, args.output, args.top_n)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Score distribution analysis error: {exc}", file=sys.stderr)
        return 1

    print(f"Score distribution report: {display_path(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
