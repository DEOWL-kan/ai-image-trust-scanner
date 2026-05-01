from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_LABELS = {"real", "ai"}

CSV_FIELDS = [
    "threshold",
    "file_path",
    "ground_truth",
    "score",
    "predicted_label",
    "status",
    "error_message",
    "total",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "true_positive",
    "true_negative",
    "false_positive",
    "false_negative",
    "false_positive_rate",
    "false_negative_rate",
]


@dataclass(frozen=True)
class ImageScore:
    file_path: str
    ground_truth: str
    score: float | None
    status: str
    error_message: str
    inference_time_ms: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day7 threshold sweep for AI Image Trust Scanner.",
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
    parser.add_argument("--start", default="0.10", help="Threshold start. Default: 0.10")
    parser.add_argument("--end", default="0.90", help="Threshold end. Default: 0.90")
    parser.add_argument("--step", default="0.05", help="Threshold step. Default: 0.05")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def decimal_arg(value: str, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal number: {value}") from exc
    if number < 0 or number > 1:
        raise ValueError(f"{name} must be between 0 and 1: {value}")
    return number


def threshold_values(start: str, end: str, step: str) -> list[float]:
    start_value = decimal_arg(start, "--start")
    end_value = decimal_arg(end, "--end")
    step_value = decimal_arg(step, "--step")
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


def iter_images(directory: Path, ground_truth: str) -> list[tuple[Path, str]]:
    if not directory.exists():
        print(f"Warning: directory not found, skipped: {directory}", file=sys.stderr)
        return []
    if not directory.is_dir():
        print(f"Warning: path is not a directory, skipped: {directory}", file=sys.stderr)
        return []

    items: list[tuple[Path, str]] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            items.append((path, ground_truth))
    return items


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def detect_score(image_path: Path, ground_truth: str, image_report_dir: Path) -> ImageScore:
    started = time.perf_counter()
    try:
        report = run_pipeline(image_path, output_dir=image_report_dir)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        score = safe_float(report.get("final_result", {}).get("final_score"))
        if not report.get("ok") or score is None:
            image_info = report.get("image_info", {})
            return ImageScore(
                file_path=display_path(image_path),
                ground_truth=ground_truth,
                score=None,
                status="error",
                error_message=image_info.get("error") or "No final_score returned.",
                inference_time_ms=elapsed_ms,
            )

        return ImageScore(
            file_path=display_path(image_path),
            ground_truth=ground_truth,
            score=round(score, 6),
            status="success",
            error_message="",
            inference_time_ms=elapsed_ms,
        )
    except Exception as exc:  # Keep batch calibration from crashing on one file.
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return ImageScore(
            file_path=display_path(image_path),
            ground_truth=ground_truth,
            score=None,
            status="error",
            error_message=str(exc),
            inference_time_ms=elapsed_ms,
        )


def predicted_label(score: float, threshold: float) -> str:
    return "ai" if score >= threshold else "real"


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def metrics_at_threshold(scores: list[ImageScore], threshold: float) -> dict[str, Any]:
    usable = [
        item
        for item in scores
        if item.status == "success" and item.score is not None and item.ground_truth in VALID_LABELS
    ]
    tp = tn = fp = fn = 0
    for item in usable:
        prediction = predicted_label(float(item.score), threshold)
        if item.ground_truth == "ai" and prediction == "ai":
            tp += 1
        elif item.ground_truth == "real" and prediction == "real":
            tn += 1
        elif item.ground_truth == "real" and prediction == "ai":
            fp += 1
        elif item.ground_truth == "ai" and prediction == "real":
            fn += 1

    total = len(usable)
    accuracy_raw = (tp + tn) / total if total else 0.0
    precision_raw = tp / (tp + fp) if tp + fp else 0.0
    recall_raw = tp / (tp + fn) if tp + fn else 0.0
    f1_raw = 0.0
    if precision_raw + recall_raw > 0:
        f1_raw = 2 * precision_raw * recall_raw / (precision_raw + recall_raw)

    return {
        "threshold": round(threshold, 2),
        "total": total,
        "accuracy": round(accuracy_raw, 4),
        "precision": round(precision_raw, 4),
        "recall": round(recall_raw, 4),
        "f1": round(f1_raw, 4),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "false_positive_rate": safe_ratio(fp, fp + tn),
        "false_negative_rate": safe_ratio(fn, fn + tp),
    }


def per_image_rows(scores: list[ImageScore], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    threshold = float(metrics["threshold"])
    rows: list[dict[str, Any]] = []
    for item in scores:
        prediction = ""
        if item.status == "success" and item.score is not None:
            prediction = predicted_label(float(item.score), threshold)
        row = {
            "threshold": f"{threshold:.2f}",
            "file_path": item.file_path,
            "ground_truth": item.ground_truth,
            "score": "" if item.score is None else f"{item.score:.6f}",
            "predicted_label": prediction,
            "status": item.status,
            "error_message": item.error_message,
            **{key: metrics[key] for key in CSV_FIELDS if key in metrics},
        }
        rows.append(row)
    return rows


def choose_best_f1(metrics_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not metrics_rows:
        return None
    return sorted(
        metrics_rows,
        key=lambda row: (
            -float(row["f1"]),
            abs(int(row["false_positive"]) - int(row["false_negative"])),
            -float(row["accuracy"]),
            abs(float(row["threshold"]) - 0.5),
            float(row["threshold"]),
        ),
    )[0]


def choose_high_precision(metrics_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [row for row in metrics_rows if int(row["true_positive"]) + int(row["false_positive"]) > 0]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            -float(row["precision"]),
            -float(row["f1"]),
            -float(row["recall"]),
            int(row["false_positive"]),
            -float(row["threshold"]),
        ),
    )[0]


def reliable_high_precision(candidate: dict[str, Any] | None, minimum_precision: float = 0.80) -> dict[str, Any] | None:
    if not candidate:
        return None
    if float(candidate.get("precision", 0.0)) < minimum_precision:
        return None
    return candidate


def choose_high_recall(metrics_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not metrics_rows:
        return None
    return sorted(
        metrics_rows,
        key=lambda row: (
            -float(row["recall"]),
            -float(row["f1"]),
            -float(row["precision"]),
            int(row["false_negative"]),
            float(row["threshold"]),
        ),
    )[0]


def metric_line(row: dict[str, Any] | None) -> str:
    if not row:
        return "N/A"
    return (
        f"{float(row['threshold']):.2f} "
        f"(accuracy={float(row['accuracy']):.4f}, precision={float(row['precision']):.4f}, "
        f"recall={float(row['recall']):.4f}, f1={float(row['f1']):.4f}, "
        f"FP={int(row['false_positive'])}, FN={int(row['false_negative'])})"
    )


def render_markdown_report(
    real_dir: Path,
    ai_dir: Path,
    output_dir: Path,
    scores: list[ImageScore],
    metrics_rows: list[dict[str, Any]],
    recommendations: dict[str, Any],
    warnings: list[str],
) -> str:
    real_count = sum(1 for item in scores if item.ground_truth == "real")
    ai_count = sum(1 for item in scores if item.ground_truth == "ai")
    success_count = sum(1 for item in scores if item.status == "success")
    error_count = len(scores) - success_count

    table = [
        "| Threshold | Accuracy | Precision | Recall | F1 | TP | TN | FP | FN | FPR | FNR |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metrics_rows:
        table.append(
            f"| {float(row['threshold']):.2f} | {float(row['accuracy']):.4f} | "
            f"{float(row['precision']):.4f} | {float(row['recall']):.4f} | "
            f"{float(row['f1']):.4f} | {int(row['true_positive'])} | "
            f"{int(row['true_negative'])} | {int(row['false_positive'])} | "
            f"{int(row['false_negative'])} | {float(row['false_positive_rate']):.4f} | "
            f"{float(row['false_negative_rate']):.4f} |"
        )

    warning_lines = [f"- {warning}" for warning in warnings] or ["- No input warnings."]

    return "\n".join(
        [
            "# Day7 Threshold Calibration Report",
            "",
            "## Day7 Goal",
            "",
            "Day7 validates the current detector across multiple decision thresholds without changing the detector itself. The goal is to make the score-to-label tradeoff visible and choose stable operating modes for later regression checks.",
            "",
            "## Dataset",
            "",
            f"- Real directory: `{display_path(real_dir)}`",
            f"- AI directory: `{display_path(ai_dir)}`",
            f"- Real image count: {real_count}",
            f"- AI image count: {ai_count}",
            f"- Total image count: {len(scores)}",
            f"- Successful detections: {success_count}",
            f"- Detection errors: {error_count}",
            "",
            "## Input Warnings",
            "",
            *warning_lines,
            "",
            "## Threshold Sweep Results",
            "",
            *table,
            "",
            "## Recommended Thresholds",
            "",
            f"- best_f1_threshold: {metric_line(recommendations.get('best_f1_threshold'))}",
            (
                f"- high_precision_threshold: {metric_line(recommendations.get('high_precision_threshold'))}"
                if recommendations.get("high_precision_threshold")
                else "- no_reliable_high_precision_threshold_found: Current sweep did not find a threshold with precision >= 0.80."
            ),
            f"- high_recall_threshold: {metric_line(recommendations.get('high_recall_threshold'))}",
            f"- Recommended default threshold: `{recommendations.get('recommended_default_threshold', 'N/A')}`",
            "",
            "The recommended default threshold uses the best-F1 operating point for the current small test set. It is a calibration baseline, not a production guarantee.",
            "",
            "Current sweep did not find a truly high-precision operating point if `no_reliable_high_precision_threshold_found` appears above. In that case, the detector cannot currently reduce real-image false positives to a reliable level by threshold selection alone.",
            "",
            "## Current Model Strengths",
            "",
            "- The detector exposes a continuous `final_score`, so threshold calibration is possible.",
            "- Batch evaluation can be repeated without changing the core detector.",
            "- Reports keep weak evidence, score fusion, and limitations visible for review.",
            "",
            "## Current Model Limitations",
            "",
            "- The current system is heuristic and does not include a trained deep AI-image detector.",
            "- The dataset is small, so threshold recommendations are sensitive to sample changes.",
            "- Lower thresholds improve AI recall but can increase false positives on real images.",
            "- Missing metadata, screenshots, compression, and editing can affect real and AI images in similar ways.",
            "",
            "## Day8 Suggestions",
            "",
            "- Add more real-camera, screenshot, social-media, compressed, and generated samples.",
            "- Keep Day7 threshold outputs as a regression baseline before changing fusion weights.",
            "- Review false positives and false negatives separately before changing the default threshold.",
            "- Consider adding an uncertainty band so borderline images are routed to manual review.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(output_dir / 'day7_threshold_sweep.csv')}`",
            f"- `{display_path(output_dir / 'day7_threshold_sweep.json')}`",
            f"- `{display_path(output_dir / 'day7_threshold_report.md')}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run(
    real_dir: Path,
    ai_dir: Path,
    output_dir: Path,
    start: str,
    end: str,
    step: str,
) -> dict[str, Any]:
    real_dir = resolve_path(real_dir)
    ai_dir = resolve_path(ai_dir)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_report_dir = output_dir / "day7_image_reports"

    warnings: list[str] = []
    for label, directory in (("real", real_dir), ("ai", ai_dir)):
        if not directory.exists():
            warnings.append(f"{label} directory was not found: {directory}")
        elif not directory.is_dir():
            warnings.append(f"{label} path is not a directory: {directory}")

    image_items = iter_images(real_dir, "real") + iter_images(ai_dir, "ai")
    thresholds = threshold_values(start, end, step)
    scores = [detect_score(path, label, image_report_dir) for path, label in image_items]
    metrics_rows = [metrics_at_threshold(scores, threshold) for threshold in thresholds]

    high_precision_candidate = choose_high_precision(metrics_rows)
    high_precision_threshold = reliable_high_precision(high_precision_candidate)
    recommendations = {
        "best_f1_threshold": choose_best_f1(metrics_rows),
        "high_recall_threshold": choose_high_recall(metrics_rows),
    }
    if high_precision_threshold:
        recommendations["high_precision_threshold"] = high_precision_threshold
    else:
        recommendations["no_reliable_high_precision_threshold_found"] = {
            "minimum_precision": 0.80,
            "best_available_candidate": high_precision_candidate,
            "message": "Current sweep did not find a threshold with precision >= 0.80.",
        }
    best = recommendations["best_f1_threshold"]
    recommendations["recommended_default_threshold"] = None if best is None else round(float(best["threshold"]), 2)

    expanded_rows: list[dict[str, Any]] = []
    for metrics in metrics_rows:
        expanded_rows.extend(per_image_rows(scores, metrics))

    csv_path = output_dir / "day7_threshold_sweep.csv"
    json_path = output_dir / "day7_threshold_sweep.json"
    report_path = output_dir / "day7_threshold_report.md"

    write_csv(csv_path, expanded_rows)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "real_dir": str(real_dir),
        "ai_dir": str(ai_dir),
        "output_dir": str(output_dir),
        "thresholds": thresholds,
        "dataset": {
            "real_count": sum(1 for item in scores if item.ground_truth == "real"),
            "ai_count": sum(1 for item in scores if item.ground_truth == "ai"),
            "total": len(scores),
            "success_count": sum(1 for item in scores if item.status == "success"),
            "error_count": sum(1 for item in scores if item.status != "success"),
        },
        "image_scores": [asdict(item) for item in scores],
        "threshold_metrics": metrics_rows,
        "recommendations": recommendations,
        "warnings": warnings,
        "outputs": {
            "csv": str(csv_path),
            "json": str(json_path),
            "markdown_report": str(report_path),
            "image_reports": str(image_report_dir),
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        render_markdown_report(real_dir, ai_dir, output_dir, scores, metrics_rows, recommendations, warnings),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    args = parse_args()
    try:
        result = run(args.real_dir, args.ai_dir, args.output_dir, args.start, args.end, args.step)
    except ValueError as exc:
        print(f"Threshold sweep argument error: {exc}", file=sys.stderr)
        return 1

    dataset = result["dataset"]
    recommendation = result["recommendations"].get("recommended_default_threshold")
    print(f"Total images: {dataset['total']}")
    print(f"Successful detections: {dataset['success_count']}")
    print(f"Detection errors: {dataset['error_count']}")
    print(f"Recommended default threshold: {recommendation if recommendation is not None else 'N/A'}")
    print(f"Output: {display_path(Path(result['outputs']['markdown_report']))}")
    if dataset["total"] == 0:
        print("No supported images were found. Check --real-dir and --ai-dir.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
