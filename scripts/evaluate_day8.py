from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import DEFAULT_UNCERTAINTY_MARGIN, decide_final_label  # noqa: E402
from main import run_pipeline  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
REPORTS_DIR = PROJECT_ROOT / "reports" / "day8"
PREDICTIONS_CSV = REPORTS_DIR / "day8_predictions.csv"
SUMMARY_MD = REPORTS_DIR / "day8_eval_summary.md"
CONFUSION_MATRIX_PNG = REPORTS_DIR / "day8_confusion_matrix.png"
DAY7_JSON = PROJECT_ROOT / "reports" / "day7_threshold_sweep.json"
DAY7_REPORT = PROJECT_ROOT / "reports" / "day7_threshold_report.md"
CSV_FIELDS = [
    "filename",
    "class_label",
    "ground_truth",
    "ai_score",
    "predicted_label",
    "threshold",
    "is_correct",
    "error_type",
    "final_label",
    "decision_status",
    "uncertainty_margin",
    "confidence_distance",
    "decision_reason",
]


@dataclass(frozen=True)
class Prediction:
    filename: str
    class_label: str
    ground_truth: str
    ai_score: float | None
    predicted_label: str
    threshold: float
    is_correct: bool
    error_type: str
    final_label: str
    decision_status: str
    uncertainty_margin: float | None
    confidence_distance: float | None
    decision_reason: str
    path: Path
    status: str
    error_message: str
    inference_time_ms: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day8 evaluation with Day7 calibrated threshold.")
    parser.add_argument(
        "--ai-dir",
        type=Path,
        default=Path("data/test_images/ai"),
        help="AI test-image directory. Default: data/test_images/ai",
    )
    parser.add_argument(
        "--real-dir",
        type=Path,
        default=Path("data/test_images/real"),
        help="Real test-image directory. Default: data/test_images/real",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Day8 report directory. Default: reports/day8",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override threshold. Default: read Day7 recommended threshold.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def image_files(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=natural_key,
    )


def load_day7_threshold() -> tuple[float, str]:
    if DAY7_JSON.exists():
        try:
            payload = json.loads(DAY7_JSON.read_text(encoding="utf-8"))
            value = payload.get("recommendations", {}).get("recommended_default_threshold")
            if value is not None:
                return float(value), f"Loaded from `{display_path(DAY7_JSON)}` recommendations.recommended_default_threshold."
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if DAY7_REPORT.exists():
        text = DAY7_REPORT.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"Recommended default threshold:\s*`?([0-9.]+)`?", text)
        if match:
            return float(match.group(1)), f"Loaded from `{display_path(DAY7_REPORT)}` Markdown report."

    return 0.5, "No explicit Day7 threshold file was readable; fell back to the detector script default threshold 0.50."


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def label_for_score(score: float, threshold: float) -> str:
    return "AI-generated" if score >= threshold else "Real"


def classify_error(ground_truth: str, predicted_label: str, status: str) -> tuple[bool, str]:
    if status != "success":
        return False, "detection_error"
    if ground_truth == predicted_label:
        return True, "correct"
    if ground_truth == "Real" and predicted_label == "AI-generated":
        return False, "false_positive"
    if ground_truth == "AI-generated" and predicted_label == "Real":
        return False, "false_negative"
    return False, "misclassified"


def detect_one(path: Path, class_label: str, threshold: float, image_report_dir: Path) -> Prediction:
    ground_truth = "AI-generated" if class_label == "ai" else "Real"
    started = time.perf_counter()
    try:
        report = run_pipeline(path, output_dir=image_report_dir)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        score = safe_float(report.get("final_result", {}).get("final_score"))
        final_result = report.get("final_result", {})
        if not report.get("ok") or score is None:
            error_message = report.get("image_info", {}).get("error") or "No final_score returned."
            is_correct, error_type = classify_error(ground_truth, "", "error")
            return Prediction(
                filename=path.name,
                class_label=class_label,
                ground_truth=ground_truth,
                ai_score=None,
                predicted_label="",
                threshold=threshold,
                is_correct=is_correct,
                error_type=error_type,
                final_label="",
                decision_status="",
                uncertainty_margin=None,
                confidence_distance=None,
                decision_reason="",
                path=path,
                status="error",
                error_message=error_message,
                inference_time_ms=elapsed_ms,
            )

        predicted_label = label_for_score(score, threshold)
        decision = decide_final_label(
            score,
            threshold=threshold,
            uncertainty_margin=safe_float(
                final_result.get("uncertainty_margin"),
                DEFAULT_UNCERTAINTY_MARGIN,
            ) or DEFAULT_UNCERTAINTY_MARGIN,
        )
        is_correct, error_type = classify_error(ground_truth, predicted_label, "success")
        return Prediction(
            filename=path.name,
            class_label=class_label,
            ground_truth=ground_truth,
            ai_score=round(score, 6),
            predicted_label=predicted_label,
            threshold=threshold,
            is_correct=is_correct,
            error_type=error_type,
            final_label=str(decision["final_label"]),
            decision_status=str(decision["decision_status"]),
            uncertainty_margin=safe_float(decision.get("uncertainty_margin")),
            confidence_distance=safe_float(decision.get("confidence_distance")),
            decision_reason=str(decision["decision_reason"]),
            path=path,
            status="success",
            error_message="",
            inference_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        is_correct, error_type = classify_error(ground_truth, "", "error")
        return Prediction(
            filename=path.name,
            class_label=class_label,
            ground_truth=ground_truth,
            ai_score=None,
            predicted_label="",
            threshold=threshold,
            is_correct=is_correct,
            error_type=error_type,
            final_label="",
            decision_status="",
            uncertainty_margin=None,
            confidence_distance=None,
            decision_reason="",
            path=path,
            status="error",
            error_message=str(exc),
            inference_time_ms=elapsed_ms,
        )


def collect_predictions(ai_dir: Path, real_dir: Path, threshold: float, image_report_dir: Path) -> list[Prediction]:
    items = [(path, "ai") for path in image_files(ai_dir)] + [
        (path, "real") for path in image_files(real_dir)
    ]
    return [detect_one(path, class_label, threshold, image_report_dir) for path, class_label in items]


def write_predictions(predictions: list[Prediction], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in predictions:
            writer.writerow(
                {
                    "filename": item.filename,
                    "class_label": item.class_label,
                    "ground_truth": item.ground_truth,
                    "ai_score": "" if item.ai_score is None else f"{item.ai_score:.6f}",
                    "predicted_label": item.predicted_label,
                    "threshold": f"{item.threshold:.4f}",
                    "is_correct": "yes" if item.is_correct else "no",
                    "error_type": item.error_type,
                    "final_label": item.final_label,
                    "decision_status": item.decision_status,
                    "uncertainty_margin": "" if item.uncertainty_margin is None else f"{item.uncertainty_margin:.6f}",
                    "confidence_distance": "" if item.confidence_distance is None else f"{item.confidence_distance:.6f}",
                    "decision_reason": item.decision_reason,
                }
            )


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def metrics(predictions: list[Prediction]) -> dict[str, Any]:
    usable = [item for item in predictions if item.status == "success"]
    tp = sum(1 for item in usable if item.ground_truth == "AI-generated" and item.predicted_label == "AI-generated")
    tn = sum(1 for item in usable if item.ground_truth == "Real" and item.predicted_label == "Real")
    fp = sum(1 for item in usable if item.ground_truth == "Real" and item.predicted_label == "AI-generated")
    fn = sum(1 for item in usable if item.ground_truth == "AI-generated" and item.predicted_label == "Real")
    total = len(usable)

    ai_precision = safe_ratio(tp, tp + fp)
    ai_recall = safe_ratio(tp, tp + fn)
    real_precision = safe_ratio(tn, tn + fn)
    real_recall = safe_ratio(tn, tn + fp)
    return {
        "total": len(predictions),
        "success_count": total,
        "error_count": len(predictions) - total,
        "ai_count": sum(1 for item in predictions if item.class_label == "ai"),
        "real_count": sum(1 for item in predictions if item.class_label == "real"),
        "accuracy": safe_ratio(tp + tn, total),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "ai_precision": ai_precision,
        "ai_recall": ai_recall,
        "ai_f1": f1(ai_precision, ai_recall),
        "real_precision": real_precision,
        "real_recall": real_recall,
        "real_f1": f1(real_precision, real_recall),
    }


def load_day7_comparison() -> str:
    if DAY7_JSON.exists():
        try:
            payload = json.loads(DAY7_JSON.read_text(encoding="utf-8"))
            best = payload.get("recommendations", {}).get("best_f1_threshold", {})
            dataset = payload.get("dataset", {})
            if best:
                return (
                    f"Day7 used {dataset.get('total', 'N/A')} images and recommended threshold "
                    f"{float(best.get('threshold', 0.0)):.2f} with accuracy "
                    f"{float(best.get('accuracy', 0.0)):.4f}, AI precision "
                    f"{float(best.get('precision', 0.0)):.4f}, AI recall "
                    f"{float(best.get('recall', 0.0)):.4f}, and AI F1 "
                    f"{float(best.get('f1', 0.0)):.4f}."
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return "Day7 comparison source was not readable; Day8 still reports the threshold source used above."


def mistake_lines(predictions: list[Prediction], limit: int = 12) -> list[str]:
    mistakes = [item for item in predictions if item.status == "success" and not item.is_correct]
    if not mistakes:
        return ["- No misclassified samples at the selected threshold."]
    lines: list[str] = []
    for item in sorted(mistakes, key=lambda row: abs((row.ai_score or 0.0) - row.threshold))[:limit]:
        score_text = "N/A" if item.ai_score is None else f"{item.ai_score:.6f}"
        lines.append(
            f"- `{display_path(item.path)}`: ground truth {item.ground_truth}, predicted {item.predicted_label}, score {score_text}, {item.error_type}"
        )
    return lines


def render_confusion_matrix_png(summary: dict[str, Any], output_png: Path) -> None:
    width, height = 760, 520
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        small = ImageFont.truetype("arial.ttf", 18)
        large = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
        large = ImageFont.load_default()

    draw.text((40, 30), "Day8 Confusion Matrix", fill="#111827", font=font)
    x0, y0 = 220, 120
    cell_w, cell_h = 220, 140
    headers = ["Pred: AI-generated", "Pred: Real"]
    rows = ["Actual: AI-generated", "Actual: Real"]
    values = [
        [summary["true_positive"], summary["false_negative"]],
        [summary["false_positive"], summary["true_negative"]],
    ]
    fills = [["#dbeafe", "#fee2e2"], ["#fee2e2", "#dcfce7"]]

    for col, header in enumerate(headers):
        draw.text((x0 + col * cell_w + 20, y0 - 38), header, fill="#374151", font=small)
    for row, row_header in enumerate(rows):
        draw.text((40, y0 + row * cell_h + 55), row_header, fill="#374151", font=small)
        for col in range(2):
            left = x0 + col * cell_w
            top = y0 + row * cell_h
            draw.rectangle((left, top, left + cell_w, top + cell_h), fill=fills[row][col], outline="#111827", width=2)
            value = str(values[row][col])
            draw.text((left + 95, top + 48), value, fill="#111827", font=large)

    draw.text((40, 450), f"Threshold: {summary['threshold']:.4f}    Accuracy: {summary['accuracy']:.4f}", fill="#111827", font=small)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png)


def write_summary(
    predictions: list[Prediction],
    summary: dict[str, Any],
    threshold_note: str,
    output_md: Path,
) -> None:
    lines = [
        "# Day8 Evaluation Summary",
        "",
        "## Dataset Scale",
        "",
        f"- AI images: {summary['ai_count']}",
        f"- Real images: {summary['real_count']}",
        f"- Total images: {summary['total']}",
        f"- Successful detections: {summary['success_count']}",
        f"- Detection errors: {summary['error_count']}",
        "",
        "## Threshold",
        "",
        f"- Used threshold: `{summary['threshold']:.4f}`",
        f"- Threshold source: {threshold_note}",
        "",
        "## Metrics",
        "",
        f"- Overall accuracy: {summary['accuracy']:.4f}",
        f"- AI precision / recall / F1: {summary['ai_precision']:.4f} / {summary['ai_recall']:.4f} / {summary['ai_f1']:.4f}",
        f"- Real precision / recall / F1: {summary['real_precision']:.4f} / {summary['real_recall']:.4f} / {summary['real_f1']:.4f}",
        f"- False positives: {summary['false_positive']}",
        f"- False negatives: {summary['false_negative']}",
        "",
        "## Confusion Matrix",
        "",
        "| Actual \\ Predicted | AI-generated | Real |",
        "| --- | ---: | ---: |",
        f"| AI-generated | {summary['true_positive']} | {summary['false_negative']} |",
        f"| Real | {summary['false_positive']} | {summary['true_negative']} |",
        "",
        "## Typical Misclassified Samples",
        "",
        *mistake_lines(predictions),
        "",
        "## Day7 Comparison",
        "",
        f"- {load_day7_comparison()}",
        f"- Day8 reran the same detector on the expanded and normalized test set with threshold {summary['threshold']:.2f}.",
        "",
        "## Day9 Optimization Suggestions",
        "",
        "- Review false positives and false negatives separately before changing feature weights.",
        "- Add a score uncertainty band around the Day7 threshold for manual-review cases.",
        "- Expand real-image coverage across camera photos, screenshots, compressed social-media images, and edited images.",
        "- Add a trained detector only after the heuristic baseline keeps stable regression reports.",
        "",
        "## Output Files",
        "",
        f"- `{display_path(PREDICTIONS_CSV)}`",
        f"- `{display_path(SUMMARY_MD)}`",
        f"- `{display_path(CONFUSION_MATRIX_PNG)}`",
        f"- `{display_path(REPORTS_DIR / 'image_reports')}`",
        "",
        f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
        "",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines), encoding="utf-8")


def run(ai_dir: Path, real_dir: Path, output_dir: Path, threshold: float | None) -> dict[str, Any]:
    ai_dir = resolve_path(ai_dir)
    real_dir = resolve_path(real_dir)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    threshold_value, threshold_note = (threshold, "Provided by --threshold override.") if threshold is not None else load_day7_threshold()
    image_report_dir = output_dir / "image_reports"

    predictions = collect_predictions(ai_dir, real_dir, float(threshold_value), image_report_dir)
    summary = metrics(predictions)
    summary["threshold"] = float(threshold_value)
    write_predictions(predictions, output_dir / PREDICTIONS_CSV.name)
    render_confusion_matrix_png(summary, output_dir / CONFUSION_MATRIX_PNG.name)
    write_summary(predictions, summary, threshold_note, output_dir / SUMMARY_MD.name)
    return summary


def main() -> int:
    args = parse_args()
    summary = run(args.ai_dir, args.real_dir, args.output_dir, args.threshold)
    print(f"Total images: {summary['total']}")
    print(f"Successful detections: {summary['success_count']}")
    print(f"Detection errors: {summary['error_count']}")
    print(f"Threshold: {summary['threshold']:.4f}")
    print(f"Accuracy: {summary['accuracy']:.4f}")
    print(f"False positives: {summary['false_positive']}")
    print(f"False negatives: {summary['false_negative']}")
    print(f"Predictions: {display_path(resolve_path(args.output_dir) / PREDICTIONS_CSV.name)}")
    print(f"Summary: {display_path(resolve_path(args.output_dir) / SUMMARY_MD.name)}")
    print(f"Confusion matrix: {display_path(resolve_path(args.output_dir) / CONFUSION_MATRIX_PNG.name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
