from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_LABELS = {"real", "ai"}

IMAGE_PATH_FIELDS = ("image_path", "path", "file", "filename")
TRUE_LABEL_FIELDS = ("true_label", "label", "ground_truth", "actual")
SCORE_FIELDS = ("ai_score", "score", "probability", "confidence", "ai_probability")
PREDICTED_LABEL_FIELDS = ("predicted_label", "pred_label", "prediction")

THRESHOLD_FIELDS = [
    "threshold",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "tp",
    "tn",
    "fp",
    "fn",
    "false_positive_rate",
    "false_negative_rate",
]
ERROR_FIELDS = [
    "image_path",
    "true_label",
    "predicted_label_at_best_threshold",
    "ai_score",
    "error_type",
    "distance_to_threshold",
    "explanation_if_available",
]
BORDERLINE_FIELDS = [
    "image_path",
    "true_label",
    "ai_score",
    "predicted_label_at_best_threshold",
    "distance_to_threshold",
    "explanation_if_available",
]
THRESHOLD_CURVE_FILENAME = "threshold_curve.png"


@dataclass(frozen=True)
class NormalizedRow:
    image_path: str
    true_label: str
    ai_score: float
    source_predicted_label: str
    explanation: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day6 threshold calibration, error analysis, and borderline sample analysis.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "reports" / "day4_eval" / "predictions.csv",
        help="Day4 prediction CSV. Default: reports/day4_eval/predictions.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "day6",
        help="Output directory. Default: outputs/day6",
    )
    parser.add_argument(
        "--explanations",
        type=Path,
        default=PROJECT_ROOT / "reports" / "day5" / "feature_report.jsonl",
        help="Optional Day5 feature_report.jsonl. Missing files are skipped.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def normalize_path_key(value: str) -> str:
    return value.strip().replace("/", "\\").lower()


def first_present_field(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    field_lookup = {field.lower(): field for field in fieldnames}
    for candidate in candidates:
        if candidate.lower() in field_lookup:
            return field_lookup[candidate.lower()]
    return None


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if 1.0 < number <= 100.0:
        number = number / 100.0
    if number < 0.0 or number > 1.0:
        return None
    return number


def normalize_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "real": "real",
        "authentic": "real",
        "human": "real",
        "camera": "real",
        "ai": "ai",
        "fake": "ai",
        "generated": "ai",
        "synthetic": "ai",
        "likely_ai": "ai",
    }
    return aliases.get(text, text)


def prediction_from_score(score: float, threshold: float) -> str:
    return "ai" if score >= threshold else "real"


def ai_score_from_row(row: dict[str, str], score_field: str, predicted_label_field: str | None) -> float | None:
    score = safe_float(row.get(score_field))
    if score is None:
        return None

    if score_field.lower() == "confidence" and predicted_label_field:
        predicted_label = normalize_label(row.get(predicted_label_field))
        if predicted_label == "real":
            return round(1.0 - score, 6)
    return score


def read_prediction_rows(input_csv: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")
    with input_csv.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        return list(reader), fieldnames


def extract_evidence_from_raw_result(raw_result: str) -> str:
    if not raw_result:
        return ""
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError:
        return ""
    evidence = payload.get("final_result", {}).get("evidence_summary")
    if isinstance(evidence, list):
        return " | ".join(str(item) for item in evidence if item)
    return ""


def load_day5_explanations(path: Path) -> dict[str, str]:
    explanations: dict[str, str] = {}
    if not path.exists():
        return explanations

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            features = payload.get("features", {})
            image_path = str(features.get("image_path") or "")
            if not image_path:
                continue
            explanation = payload.get("explanation", {})
            reasons = explanation.get("reasons")
            if isinstance(reasons, list):
                reason_text = " | ".join(str(reason) for reason in reasons if reason)
            else:
                reason_text = ""

            extras = []
            if explanation.get("risk_score") is not None:
                extras.append(f"risk_score={explanation.get('risk_score')}")
            if explanation.get("prediction"):
                extras.append(f"day5_prediction={explanation.get('prediction')}")
            if explanation.get("confidence"):
                extras.append(f"day5_confidence={explanation.get('confidence')}")

            full_text = " | ".join(part for part in [reason_text, "; ".join(extras)] if part)
            explanations[normalize_path_key(image_path)] = full_text
    return explanations


def normalize_rows(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    day5_explanations: dict[str, str],
) -> tuple[list[NormalizedRow], list[str]]:
    path_field = first_present_field(fieldnames, IMAGE_PATH_FIELDS)
    true_label_field = first_present_field(fieldnames, TRUE_LABEL_FIELDS)
    score_field = first_present_field(fieldnames, SCORE_FIELDS)
    predicted_label_field = first_present_field(fieldnames, PREDICTED_LABEL_FIELDS)

    missing = []
    if path_field is None:
        missing.append(f"image path field candidates: {', '.join(IMAGE_PATH_FIELDS)}")
    if true_label_field is None:
        missing.append(f"true label field candidates: {', '.join(TRUE_LABEL_FIELDS)}")
    if score_field is None:
        missing.append(f"AI score field candidates: {', '.join(SCORE_FIELDS)}")
    if missing:
        raise ValueError(
            "Required fields are missing.\n"
            + "\n".join(f"- {item}" for item in missing)
            + "\nActual fields: "
            + ", ".join(fieldnames)
        )

    normalized: list[NormalizedRow] = []
    skipped_reasons: list[str] = []
    for index, row in enumerate(rows, start=2):
        image_path = str(row.get(path_field, "")).strip()
        true_label = normalize_label(row.get(true_label_field))
        ai_score = ai_score_from_row(row, score_field, predicted_label_field)
        source_predicted_label = normalize_label(row.get(predicted_label_field)) if predicted_label_field else ""

        if not image_path:
            skipped_reasons.append(f"row {index}: empty image path")
            continue
        if true_label not in VALID_LABELS:
            skipped_reasons.append(f"row {index}: unsupported true label {row.get(true_label_field)!r}")
            continue
        if ai_score is None:
            skipped_reasons.append(f"row {index}: invalid AI score {row.get(score_field)!r}")
            continue

        explanation = day5_explanations.get(normalize_path_key(image_path), "")
        if not explanation:
            explanation = extract_evidence_from_raw_result(row.get("raw_result", ""))

        normalized.append(
            NormalizedRow(
                image_path=image_path,
                true_label=true_label,
                ai_score=round(ai_score, 6),
                source_predicted_label=source_predicted_label,
                explanation=explanation,
            )
        )
    return normalized, skipped_reasons


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def metrics_at_threshold(rows: list[NormalizedRow], threshold: float) -> dict[str, Any]:
    tp = tn = fp = fn = 0
    for row in rows:
        predicted = prediction_from_score(row.ai_score, threshold)
        if row.true_label == "ai" and predicted == "ai":
            tp += 1
        elif row.true_label == "real" and predicted == "real":
            tn += 1
        elif row.true_label == "real" and predicted == "ai":
            fp += 1
        elif row.true_label == "ai" and predicted == "real":
            fn += 1

    total = len(rows)
    accuracy_raw = (tp + tn) / total if total else 0.0
    precision_raw = tp / (tp + fp) if tp + fp else 0.0
    recall_raw = tp / (tp + fn) if tp + fn else 0.0
    f1_raw = 0.0
    if precision_raw + recall_raw > 0:
        f1_raw = 2 * precision_raw * recall_raw / (precision_raw + recall_raw)

    return {
        "threshold": round(threshold, 2),
        "accuracy": round(accuracy_raw, 4),
        "precision": round(precision_raw, 4),
        "recall": round(recall_raw, 4),
        "f1": round(f1_raw, 4),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "false_positive_rate": safe_ratio(fp, fp + tn),
        "false_negative_rate": safe_ratio(fn, fn + tp),
    }


def threshold_values() -> list[float]:
    return [round(value / 100, 2) for value in range(10, 91, 5)]


def choose_best_threshold(scan_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not scan_rows:
        raise ValueError("No threshold rows were generated.")
    return sorted(
        scan_rows,
        key=lambda row: (
            -float(row["f1"]),
            abs(int(row["fp"]) - int(row["fn"])),
            -float(row["accuracy"]),
            abs(float(row["threshold"]) - 0.5),
            float(row["threshold"]),
        ),
    )[0]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_threshold_curve_with_pillow(scan_rows: list[dict[str, Any]], output_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1200, 760
    margin_left, margin_top, margin_right, margin_bottom = 105, 80, 60, 105
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    colors = {
        "accuracy": (37, 99, 235),
        "precision": (220, 38, 38),
        "recall": (22, 163, 74),
        "f1": (147, 51, 234),
    }

    thresholds = [float(row["threshold"]) for row in scan_rows]
    series = {
        "accuracy": [float(row["accuracy"]) for row in scan_rows],
        "precision": [float(row["precision"]) for row in scan_rows],
        "recall": [float(row["recall"]) for row in scan_rows],
        "f1": [float(row["f1"]) for row in scan_rows],
    }

    def x_pos(threshold: float) -> int:
        return int(margin_left + ((threshold - 0.1) / 0.8) * plot_width)

    def y_pos(value: float) -> int:
        return int(margin_top + (1.0 - value) * plot_height)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 18)
        title_font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    axis_color = (31, 41, 55)
    grid_color = (229, 231, 235)
    text_color = (17, 24, 39)

    draw.text((margin_left, 25), "Day6 Threshold Calibration Curve", fill=text_color, font=title_font)
    for index in range(0, 11):
        value = index / 10
        y = y_pos(value)
        draw.line((margin_left, y, width - margin_right, y), fill=grid_color, width=1)
        draw.text((35, y - 10), f"{value:.1f}", fill=text_color, font=small_font)

    draw.line((margin_left, margin_top, margin_left, height - margin_bottom), fill=axis_color, width=2)
    draw.line((margin_left, height - margin_bottom, width - margin_right, height - margin_bottom), fill=axis_color, width=2)

    for threshold in thresholds:
        x = x_pos(threshold)
        draw.line((x, height - margin_bottom, x, height - margin_bottom + 8), fill=axis_color, width=1)
        draw.text((x - 18, height - margin_bottom + 16), f"{threshold:.2f}", fill=text_color, font=small_font)

    draw.text((width // 2 - 55, height - 45), "Threshold", fill=text_color, font=font)

    for name, values in series.items():
        points = [(x_pos(threshold), y_pos(value)) for threshold, value in zip(thresholds, values)]
        draw.line(points, fill=colors[name], width=4)
        for point in points:
            x, y = point
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=colors[name])

    legend_x = width - margin_right - 240
    legend_y = margin_top
    for offset, name in enumerate(series):
        y = legend_y + offset * 32
        draw.line((legend_x, y + 10, legend_x + 35, y + 10), fill=colors[name], width=4)
        draw.text((legend_x + 48, y), name, fill=text_color, font=small_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def write_threshold_curve(scan_rows: list[dict[str, Any]], output_path: Path) -> tuple[bool, str | None]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        try:
            _write_threshold_curve_with_pillow(scan_rows, output_path)
        except ImportError:
            return False, "matplotlib is not installed; Pillow is also unavailable, so skipped threshold_curve.png."
        return True, "matplotlib is not installed; generated threshold_curve.png with Pillow fallback."

    thresholds = [float(row["threshold"]) for row in scan_rows]
    series = {
        "accuracy": [float(row["accuracy"]) for row in scan_rows],
        "precision": [float(row["precision"]) for row in scan_rows],
        "recall": [float(row["recall"]) for row in scan_rows],
        "f1": [float(row["f1"]) for row in scan_rows],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5.5))
    for name, values in series.items():
        plt.plot(thresholds, values, marker="o", linewidth=2, label=name)

    plt.title("Day6 Threshold Calibration Curve")
    plt.xlabel("Threshold")
    plt.ylabel("Metric")
    plt.xlim(0.1, 0.9)
    plt.ylim(0.0, 1.05)
    plt.xticks(thresholds, rotation=45)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()
    return True, None


def error_cases(rows: list[NormalizedRow], threshold: float) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row in rows:
        predicted = prediction_from_score(row.ai_score, threshold)
        if predicted == row.true_label:
            continue
        error_type = (
            "false_positive_real_as_ai"
            if row.true_label == "real" and predicted == "ai"
            else "false_negative_ai_as_real"
        )
        cases.append(
            {
                "image_path": row.image_path,
                "true_label": row.true_label,
                "predicted_label_at_best_threshold": predicted,
                "ai_score": f"{row.ai_score:.4f}",
                "error_type": error_type,
                "distance_to_threshold": f"{abs(row.ai_score - threshold):.4f}",
                "explanation_if_available": row.explanation,
            }
        )
    return sorted(cases, key=lambda item: (item["error_type"], float(item["distance_to_threshold"])))


def borderline_cases(rows: list[NormalizedRow], threshold: float) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row in rows:
        distance = abs(row.ai_score - threshold)
        if distance > 0.10:
            continue
        cases.append(
            {
                "image_path": row.image_path,
                "true_label": row.true_label,
                "ai_score": f"{row.ai_score:.4f}",
                "predicted_label_at_best_threshold": prediction_from_score(row.ai_score, threshold),
                "distance_to_threshold": f"{distance:.4f}",
                "explanation_if_available": row.explanation,
            }
        )
    return sorted(cases, key=lambda item: float(item["distance_to_threshold"]))


def interpret_bias(best: dict[str, Any], default_threshold_metrics: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    fp = int(best["fp"])
    fn = int(best["fn"])
    threshold = float(best["threshold"])

    if fp > fn:
        lines.append("- Bias: at the recommended threshold, the system is more likely to mark real images as AI than to miss AI images.")
    elif fn > fp:
        lines.append("- Bias: at the recommended threshold, the system is more likely to let AI images pass as real than to accuse real images.")
    else:
        lines.append("- Bias: at the recommended threshold, false positives and false negatives are balanced.")

    if default_threshold_metrics:
        default_fn = int(default_threshold_metrics["fn"])
        default_fp = int(default_threshold_metrics["fp"])
        if default_fn > default_fp:
            lines.append("- Default threshold behavior: 0.50 is too strict for the current score distribution, so many AI images fall below the AI cutoff.")
        elif default_fp > default_fn:
            lines.append("- Default threshold behavior: 0.50 is too loose for the current score distribution, so real images are too easily flagged as AI.")
        else:
            lines.append("- Default threshold behavior: 0.50 has balanced error types on this dataset.")

    if threshold < 0.5:
        lines.append("- Threshold strictness: the recommended threshold is below 0.50, which means the current detector scores are generally low and need a looser AI cutoff to recover AI samples.")
    elif threshold > 0.5:
        lines.append("- Threshold strictness: the recommended threshold is above 0.50, which means the current detector would need a stricter AI cutoff to reduce real-image false positives.")
    else:
        lines.append("- Threshold strictness: the recommended threshold matches the current default cutoff.")

    return lines


def render_summary(
    input_csv: Path,
    explanations_path: Path,
    output_dir: Path,
    threshold_curve_path: Path,
    rows: list[NormalizedRow],
    scan_rows: list[dict[str, Any]],
    best: dict[str, Any],
    errors: list[dict[str, Any]],
    borderlines: list[dict[str, Any]],
    skipped_reasons: list[str],
    explanations_loaded: bool,
    plot_generated: bool,
    plot_note: str | None,
) -> str:
    real_count = sum(1 for row in rows if row.true_label == "real")
    ai_count = sum(1 for row in rows if row.true_label == "ai")
    best_threshold = float(best["threshold"])
    default_metrics = next((row for row in scan_rows if float(row["threshold"]) == 0.5), None)
    fp_count = int(best["fp"])
    fn_count = int(best["fn"])
    same_f1_count = sum(1 for row in scan_rows if row["f1"] == best["f1"])

    lines = [
        "# Day6 Threshold Calibration and Error Analysis",
        "",
        "## Day6 Goal",
        "",
        "Combine Day4 prediction scores with optional Day5 explanations to calibrate the AI-score threshold, inspect misclassified samples, and identify borderline samples without modifying the detector or source images.",
        "",
        "## Inputs",
        "",
        f"- Day4 predictions: `{display_path(input_csv)}`",
        f"- Day5 explanations: `{display_path(explanations_path)}` ({'loaded' if explanations_loaded else 'not found or skipped'})",
        f"- Output directory: `{display_path(output_dir)}`",
        "",
        "## Dataset",
        "",
        f"- Total usable samples: {len(rows)}",
        f"- Real samples: {real_count}",
        f"- AI samples: {ai_count}",
        f"- Skipped rows: {len(skipped_reasons)}",
        "",
        "## Recommended Threshold",
        "",
        f"- Best threshold: `{best_threshold:.2f}`",
        f"- Accuracy: {best['accuracy']:.4f}",
        f"- Precision: {best['precision']:.4f}",
        f"- Recall: {best['recall']:.4f}",
        f"- F1: {best['f1']:.4f}",
        "",
        "The recommended threshold is selected by highest F1-score. When multiple thresholds share the same F1-score, the script chooses the threshold with the most balanced FP/FN counts, then higher accuracy, then the value closest to 0.50 for deterministic stability.",
        f"In this run, {same_f1_count} threshold point(s) shared the winning F1-score; the selected threshold has FP={fp_count} and FN={fn_count}.",
        "",
        "## Confusion Matrix at Recommended Threshold",
        "",
        "| True \\ Predicted | AI | Real |",
        "| --- | ---: | ---: |",
        f"| AI | {best['tp']} | {best['fn']} |",
        f"| Real | {best['fp']} | {best['tn']} |",
        "",
        "## Error and Borderline Counts",
        "",
        f"- False positives: {fp_count}",
        f"- False negatives: {fn_count}",
        f"- Error cases: {len(errors)}",
        f"- Borderline cases (`abs(ai_score - threshold) <= 0.10`): {len(borderlines)}",
        "",
        "## Threshold Curve",
        "",
        f"- Curve file: `{display_path(threshold_curve_path)}`",
        "- The curve plots threshold against accuracy, precision, recall, and F1 to make the tradeoff visible.",
    ]
    if plot_note:
        lines.append(f"- Plot note: {plot_note}")
    if plot_generated:
        lines.extend(["", f"![Threshold calibration curve]({THRESHOLD_CURVE_FILENAME})"])
    else:
        lines.append("- The curve image was not generated because no plotting backend is available.")

    lines.extend(
        [
            "",
        "## Current System Interpretation",
        "",
        *interpret_bias(best, default_metrics),
        "",
        "## Outputs",
        "",
        "- `threshold_calibration.csv`: metric scan from threshold 0.10 to 0.90 in 0.05 increments.",
        "- `threshold_curve.png`: visual threshold curve for accuracy, precision, recall, and F1.",
        "- `error_cases.csv`: all samples misclassified at the recommended threshold, with optional Day5 explanations.",
        "- `borderline_cases.csv`: samples within 0.10 of the recommended threshold.",
        "- `day6_summary.md`: this summary report.",
        "",
        "## Day7 Suggestions",
        "",
        "- Compare Day4 `score` with Day5 `risk_score` to see whether a simple calibrated blend improves separation.",
        "- Review false positives and false negatives separately before changing any core detector weights.",
        "- Add more real-camera, screenshot, compressed, and generated-image samples before locking a threshold.",
        "- Consider reporting an uncertainty band around the threshold instead of forcing binary labels for borderline samples.",
        ]
    )

    if skipped_reasons:
        lines.extend(["", "## Skipped Rows", ""])
        for reason in skipped_reasons[:20]:
            lines.append(f"- {reason}")
        if len(skipped_reasons) > 20:
            lines.append(f"- ... {len(skipped_reasons) - 20} more skipped rows")

    lines.extend(["", f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._", ""])
    return "\n".join(lines)


def run(input_csv: Path, output_dir: Path, explanations_path: Path) -> dict[str, Any]:
    input_csv = resolve_path(input_csv)
    output_dir = resolve_path(output_dir)
    explanations_path = resolve_path(explanations_path)

    rows, fieldnames = read_prediction_rows(input_csv)
    day5_explanations = load_day5_explanations(explanations_path)
    normalized_rows, skipped_reasons = normalize_rows(rows, fieldnames, day5_explanations)
    if not normalized_rows:
        raise ValueError(
            "No usable prediction rows were found after normalization.\n"
            f"Actual fields: {', '.join(fieldnames)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    scan_rows = [metrics_at_threshold(normalized_rows, threshold) for threshold in threshold_values()]
    best = choose_best_threshold(scan_rows)
    best_threshold = float(best["threshold"])
    errors = error_cases(normalized_rows, best_threshold)
    borderlines = borderline_cases(normalized_rows, best_threshold)
    threshold_curve_path = output_dir / THRESHOLD_CURVE_FILENAME
    plot_generated, plot_note = write_threshold_curve(scan_rows, threshold_curve_path)
    if plot_note:
        print(f"Day6 plot note: {plot_note}", file=sys.stderr)

    write_csv(output_dir / "threshold_calibration.csv", THRESHOLD_FIELDS, scan_rows)
    write_csv(output_dir / "error_cases.csv", ERROR_FIELDS, errors)
    write_csv(output_dir / "borderline_cases.csv", BORDERLINE_FIELDS, borderlines)
    (output_dir / "day6_summary.md").write_text(
        render_summary(
            input_csv=input_csv,
            explanations_path=explanations_path,
            output_dir=output_dir,
            threshold_curve_path=threshold_curve_path,
            rows=normalized_rows,
            scan_rows=scan_rows,
            best=best,
            errors=errors,
            borderlines=borderlines,
            skipped_reasons=skipped_reasons,
            explanations_loaded=bool(day5_explanations),
            plot_generated=plot_generated,
            plot_note=plot_note,
        ),
        encoding="utf-8",
    )
    return {
        "output_dir": output_dir,
        "best_threshold": best_threshold,
        "best_metrics": best,
        "error_count": len(errors),
        "borderline_count": len(borderlines),
        "plot_generated": plot_generated,
    }


def main() -> int:
    args = parse_args()
    try:
        result = run(args.input, args.out, args.explanations)
    except FileNotFoundError as exc:
        print(f"Day6 input error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Day6 field/data error: {exc}", file=sys.stderr)
        return 1

    best = result["best_metrics"]
    print(f"Output: {display_path(result['output_dir'])}")
    print(f"Best threshold: {result['best_threshold']:.2f}")
    print(
        "Best metrics: "
        f"accuracy={best['accuracy']:.4f}, "
        f"precision={best['precision']:.4f}, "
        f"recall={best['recall']:.4f}, "
        f"f1={best['f1']:.4f}"
    )
    print(f"Error cases: {result['error_count']}")
    print(f"Borderline cases: {result['borderline_count']}")
    if result["plot_generated"]:
        print(f"Threshold curve: {display_path(result['output_dir'] / THRESHOLD_CURVE_FILENAME)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
