from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


REPORTS_DIR = PROJECT_ROOT / "reports" / "day8"
PREDICTIONS_CSV = REPORTS_DIR / "day8_predictions.csv"
SWEEP_CSV = REPORTS_DIR / "day8_threshold_sweep.csv"
SWEEP_SUMMARY_MD = REPORTS_DIR / "day8_threshold_sweep_summary.md"
SWEEP_CURVE_PNG = REPORTS_DIR / "day8_threshold_sweep_curve.png"
DAY7_THRESHOLD = 0.15
CSV_FIELDS = [
    "threshold",
    "total",
    "accuracy",
    "ai_precision",
    "ai_recall",
    "ai_f1",
    "real_precision",
    "real_recall",
    "real_f1",
    "macro_f1",
    "true_positive",
    "true_negative",
    "false_positive",
    "false_negative",
]


@dataclass(frozen=True)
class ScoreItem:
    filename: str
    class_label: str
    ground_truth: str
    ai_score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day8 threshold sweep based on reports/day8/day8_predictions.csv.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=PREDICTIONS_CSV,
        help="Day8 predictions CSV. Default: reports/day8/day8_predictions.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Day8 output directory. Default: reports/day8",
    )
    parser.add_argument("--start", default="0.05", help="Threshold start. Default: 0.05")
    parser.add_argument("--end", default="0.95", help="Threshold end. Default: 0.95")
    parser.add_argument("--step", default="0.01", help="Threshold step. Default: 0.01")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def threshold_values(start: str, end: str, step: str) -> list[float]:
    start_value = Decimal(start)
    end_value = Decimal(end)
    step_value = Decimal(step)
    if step_value <= 0:
        raise ValueError("--step must be greater than 0")
    if start_value > end_value:
        raise ValueError("--start must be less than or equal to --end")

    values: list[float] = []
    current = start_value
    while current <= end_value:
        values.append(float(current.quantize(Decimal("0.01"))))
        current += step_value
    return values


def ensure_predictions(predictions_csv: Path) -> None:
    if predictions_csv.exists():
        return
    from evaluate_day8 import run as run_day8_evaluation

    run_day8_evaluation(
        ai_dir=Path("data/test_images/ai"),
        real_dir=Path("data/test_images/real"),
        output_dir=REPORTS_DIR,
        threshold=DAY7_THRESHOLD,
    )


def load_scores(predictions_csv: Path) -> list[ScoreItem]:
    ensure_predictions(predictions_csv)
    with predictions_csv.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    required = {"filename", "class_label", "ground_truth", "ai_score"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        from evaluate_day8 import run as run_day8_evaluation

        run_day8_evaluation(
            ai_dir=Path("data/test_images/ai"),
            real_dir=Path("data/test_images/real"),
            output_dir=REPORTS_DIR,
            threshold=DAY7_THRESHOLD,
        )
        with predictions_csv.open("r", newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
        missing = required - set(rows[0].keys() if rows else [])
        if missing:
            raise ValueError(f"Predictions CSV is missing required fields: {', '.join(sorted(missing))}")

    items: list[ScoreItem] = []
    for row in rows:
        score_text = row.get("ai_score", "")
        if score_text == "":
            continue
        items.append(
            ScoreItem(
                filename=row["filename"],
                class_label=row.get("class_label", ""),
                ground_truth=row["ground_truth"],
                ai_score=float(score_text),
            )
        )
    if not items:
        raise ValueError("No usable Day8 prediction scores were found.")
    return items


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def metrics_at_threshold(items: list[ScoreItem], threshold: float) -> dict[str, Any]:
    tp = tn = fp = fn = 0
    for item in items:
        predicted = "AI-generated" if item.ai_score >= threshold else "Real"
        if item.ground_truth == "AI-generated" and predicted == "AI-generated":
            tp += 1
        elif item.ground_truth == "AI-generated" and predicted == "Real":
            fn += 1
        elif item.ground_truth == "Real" and predicted == "AI-generated":
            fp += 1
        elif item.ground_truth == "Real" and predicted == "Real":
            tn += 1

    total = tp + tn + fp + fn
    ai_precision = safe_ratio(tp, tp + fp)
    ai_recall = safe_ratio(tp, tp + fn)
    real_precision = safe_ratio(tn, tn + fn)
    real_recall = safe_ratio(tn, tn + fp)
    ai_f1 = f1(ai_precision, ai_recall)
    real_f1 = f1(real_precision, real_recall)
    return {
        "threshold": round(threshold, 2),
        "total": total,
        "accuracy": safe_ratio(tp + tn, total),
        "ai_precision": ai_precision,
        "ai_recall": ai_recall,
        "ai_f1": ai_f1,
        "real_precision": real_precision,
        "real_recall": real_recall,
        "real_f1": real_f1,
        "macro_f1": round((ai_f1 + real_f1) / 2, 4),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
    }


def write_sweep_csv(rows: list[dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def find_threshold_row(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    return min(rows, key=lambda row: abs(float(row["threshold"]) - threshold))


def choose_recommendations(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    balanced = sorted(
        rows,
        key=lambda row: (
            -float(row["macro_f1"]),
            int(row["false_positive"]),
            -float(row["accuracy"]),
            abs(float(row["threshold"]) - DAY7_THRESHOLD),
        ),
    )[0]

    # Avoid degenerate all-real/all-AI operating points by keeping choices near
    # the useful part of the curve while still prioritizing the requested class.
    useful_floor = float(balanced["macro_f1"]) * 0.80
    useful_rows = [row for row in rows if float(row["macro_f1"]) >= useful_floor] or rows

    conservative = sorted(
        useful_rows,
        key=lambda row: (
            int(row["false_positive"]),
            -float(row["real_recall"]),
            -float(row["macro_f1"]),
            int(row["false_negative"]),
            -float(row["threshold"]),
        ),
    )[0]
    strict = sorted(
        useful_rows,
        key=lambda row: (
            -float(row["ai_recall"]),
            int(row["false_negative"]),
            -float(row["macro_f1"]),
            int(row["false_positive"]),
            float(row["threshold"]),
        ),
    )[0]
    return {
        "balanced_threshold": balanced,
        "conservative_threshold": conservative,
        "strict_threshold": strict,
    }


def metric_line(name: str, row: dict[str, Any]) -> str:
    return (
        f"- {name}: threshold `{float(row['threshold']):.2f}`, accuracy {float(row['accuracy']):.4f}, "
        f"AI P/R/F1 {float(row['ai_precision']):.4f}/{float(row['ai_recall']):.4f}/{float(row['ai_f1']):.4f}, "
        f"Real P/R/F1 {float(row['real_precision']):.4f}/{float(row['real_recall']):.4f}/{float(row['real_f1']):.4f}, "
        f"macro F1 {float(row['macro_f1']):.4f}, FP {int(row['false_positive'])}, FN {int(row['false_negative'])}"
    )


def choose_day9_threshold(recommendations: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any], str]:
    balanced = recommendations["balanced_threshold"]
    conservative = recommendations["conservative_threshold"]
    if int(balanced["false_positive"]) > 0 and int(conservative["false_positive"]) < int(balanced["false_positive"]):
        return (
            "conservative_threshold",
            conservative,
            "Day8 shows many real images being flagged as AI, so the next regression baseline should reduce false positives while retaining a non-degenerate macro F1.",
        )
    return (
        "balanced_threshold",
        balanced,
        "The balanced threshold has the strongest macro F1 and is the best single-number baseline for mixed AI/real evaluation.",
    )


def render_summary(
    rows: list[dict[str, Any]],
    recommendations: dict[str, dict[str, Any]],
    output_md: Path,
) -> None:
    day7_row = find_threshold_row(rows, DAY7_THRESHOLD)
    day9_name, day9_row, day9_reason = choose_day9_threshold(recommendations)
    lines = [
        "# Day8 Threshold Sweep Summary",
        "",
        "## Scope",
        "",
        "- Source: `reports/day8/day8_predictions.csv`",
        "- Scan range: `0.05` to `0.95`",
        "- Step: `0.01`",
        "- The detector and image set were not modified; only score-to-label thresholds were rescored.",
        "",
        "## Threshold Performance",
        "",
        metric_line("Current Day7 threshold", day7_row),
        metric_line("Day8 balanced_threshold", recommendations["balanced_threshold"]),
        metric_line("Day8 conservative_threshold", recommendations["conservative_threshold"]),
        metric_line("Day8 strict_threshold", recommendations["strict_threshold"]),
        "",
        "## Recommendation for Day9",
        "",
        f"- Recommended Day9 threshold: `{float(day9_row['threshold']):.2f}` ({day9_name})",
        f"- Reason: {day9_reason}",
        "",
        "## Why Day7 Threshold May Have Failed on Day8",
        "",
        "- Day7 was calibrated on only 20 images, while Day8 expanded the test set to 60 images.",
        "- The added real images include harder cases, so the low Day7 threshold creates more real-image false positives.",
        "- The current score range is narrow and overlapping across AI and real samples, making a single threshold unstable.",
        "- The detector is still heuristic; metadata, compression, screenshots, and image processing can produce similar evidence for both classes.",
        "",
        "## Should We Enter Algorithm Optimization?",
        "",
        "- Yes. Threshold scanning improves operating-point selection, but it does not fix the overlap between AI and real scores.",
        "- Day9 should first lock a conservative regression threshold, then inspect false-positive and false-negative feature patterns before changing weights or adding new detector signals.",
        "",
        "## Output Files",
        "",
        f"- `{display_path(SWEEP_CSV)}`",
        f"- `{display_path(SWEEP_SUMMARY_MD)}`",
        f"- `{display_path(SWEEP_CURVE_PNG)}`",
        "",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines), encoding="utf-8")


def normalize_series(rows: list[dict[str, Any]], field: str) -> list[float]:
    values = [float(row[field]) for row in rows]
    maximum = max(values) if values else 1.0
    if maximum <= 0:
        maximum = 1.0
    return [value / maximum for value in values]


def draw_threshold_curve(rows: list[dict[str, Any]], output_png: Path) -> None:
    width, height = 1100, 700
    margin_left, margin_right = 90, 40
    margin_top, margin_bottom = 70, 95
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arial.ttf", 26)
        font = ImageFont.truetype("arial.ttf", 17)
        small = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        title_font = ImageFont.load_default()
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.text((margin_left, 25), "Day8 Threshold Sweep Curve", fill="#111827", font=title_font)
    x0, y0 = margin_left, margin_top
    x1, y1 = margin_left + plot_w, margin_top + plot_h
    draw.rectangle((x0, y0, x1, y1), outline="#111827", width=2)

    for i in range(6):
        y = y1 - i * plot_h / 5
        draw.line((x0, y, x1, y), fill="#e5e7eb", width=1)
        draw.text((20, y - 8), f"{i / 5:.1f}", fill="#374151", font=small)

    thresholds = [float(row["threshold"]) for row in rows]
    min_t, max_t = min(thresholds), max(thresholds)

    def points(values: list[float]) -> list[tuple[float, float]]:
        plotted: list[tuple[float, float]] = []
        for threshold, value in zip(thresholds, values):
            x = x0 + (threshold - min_t) / (max_t - min_t) * plot_w
            y = y1 - value * plot_h
            plotted.append((x, y))
        return plotted

    series = {
        "accuracy": ("#2563eb", [float(row["accuracy"]) for row in rows]),
        "macro F1": ("#16a34a", [float(row["macro_f1"]) for row in rows]),
        "false positives (scaled)": ("#dc2626", normalize_series(rows, "false_positive")),
        "false negatives (scaled)": ("#9333ea", normalize_series(rows, "false_negative")),
    }
    for label, (color, values) in series.items():
        line_points = points(values)
        if len(line_points) >= 2:
            draw.line(line_points, fill=color, width=3)

    legend_x, legend_y = margin_left + 30, height - 68
    for index, (label, (color, _)) in enumerate(series.items()):
        x = legend_x + index * 245
        draw.line((x, legend_y, x + 35, legend_y), fill=color, width=4)
        draw.text((x + 45, legend_y - 9), label, fill="#111827", font=small)

    draw.text((margin_left + plot_w / 2 - 55, height - 38), "threshold", fill="#374151", font=font)
    draw.text((15, margin_top + plot_h / 2 - 10), "metric", fill="#374151", font=font)
    draw.text((x0 - 10, y1 + 12), f"{min_t:.2f}", fill="#374151", font=small)
    draw.text((x1 - 35, y1 + 12), f"{max_t:.2f}", fill="#374151", font=small)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png)


def run(predictions_csv: Path, output_dir: Path, start: str, end: str, step: str) -> dict[str, Any]:
    predictions_csv = resolve_path(predictions_csv)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    items = load_scores(predictions_csv)
    rows = [metrics_at_threshold(items, threshold) for threshold in threshold_values(start, end, step)]
    recommendations = choose_recommendations(rows)
    write_sweep_csv(rows, output_dir / SWEEP_CSV.name)
    render_summary(rows, recommendations, output_dir / SWEEP_SUMMARY_MD.name)
    draw_threshold_curve(rows, output_dir / SWEEP_CURVE_PNG.name)
    day9_name, day9_row, day9_reason = choose_day9_threshold(recommendations)
    return {
        "rows": rows,
        "recommendations": recommendations,
        "day9_name": day9_name,
        "day9_row": day9_row,
        "day9_reason": day9_reason,
    }


def main() -> int:
    args = parse_args()
    try:
        result = run(args.predictions, args.output_dir, args.start, args.end, args.step)
    except (OSError, ValueError) as exc:
        print(f"Day8 threshold sweep failed: {exc}", file=sys.stderr)
        return 1

    recommendations = result["recommendations"]
    print(metric_line("balanced_threshold", recommendations["balanced_threshold"]))
    print(metric_line("conservative_threshold", recommendations["conservative_threshold"]))
    print(metric_line("strict_threshold", recommendations["strict_threshold"]))
    print(
        f"Recommended Day9 threshold: {float(result['day9_row']['threshold']):.2f} "
        f"({result['day9_name']})"
    )
    print(f"Reason: {result['day9_reason']}")
    print(f"Sweep CSV: {display_path(resolve_path(args.output_dir) / SWEEP_CSV.name)}")
    print(f"Summary: {display_path(resolve_path(args.output_dir) / SWEEP_SUMMARY_MD.name)}")
    print(f"Curve: {display_path(resolve_path(args.output_dir) / SWEEP_CURVE_PNG.name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
