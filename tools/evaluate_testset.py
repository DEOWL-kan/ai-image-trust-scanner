from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VALID_LABELS = {"real", "ai"}
PREDICTION_FIELDS = [
    "image_path",
    "true_label",
    "predicted_label",
    "confidence",
    "score",
    "raw_result",
]
THRESHOLD_FIELDS = [
    "threshold",
    "accuracy",
    "precision_ai",
    "recall_ai",
    "f1_ai",
    "false_positive",
    "false_negative",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate AI Image Trust Scanner on data/test_images."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/test_images"),
        help="Dataset root containing real/ and ai/ folders. Default: data/test_images",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/day4_eval"),
        help="Output directory. Default: reports/day4_eval",
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


def iter_labeled_images(dataset_root: Path) -> list[tuple[Path, str]]:
    images: list[tuple[Path, str]] = []
    for true_label in ("real", "ai"):
        label_dir = dataset_root / true_label
        if not label_dir.exists():
            continue
        for image_path in sorted(label_dir.rglob("*")):
            if image_path.is_file() and image_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append((image_path, true_label))
    return images


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_divide(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def prediction_from_score(score: float) -> str:
    return "ai" if score >= 0.5 else "real"


def confidence_from_score(score: float, predicted_label: str) -> float:
    return round(score if predicted_label == "ai" else 1.0 - score, 4)


def summarize_raw_result(report: dict[str, Any]) -> str:
    summary = {
        "ok": report.get("ok"),
        "final_result": report.get("final_result"),
        "image_info": {
            "filename": report.get("image_info", {}).get("filename"),
            "width": report.get("image_info", {}).get("width"),
            "height": report.get("image_info", {}).get("height"),
        },
    }
    return json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)


def evaluate_one(image_path: Path, true_label: str, image_report_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        report = run_pipeline(image_path, output_dir=image_report_dir)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        image_info = report.get("image_info", {})
        final_result = report.get("final_result", {})
        score = safe_float(final_result.get("final_score"))

        if not report.get("ok") or score is None:
            return {
                "image_path": display_path(image_path),
                "true_label": true_label,
                "predicted_label": "",
                "confidence": "",
                "score": "",
                "raw_result": summarize_raw_result(report),
                "status": "error",
                "error_message": image_info.get("error") or "No final_score returned.",
                "inference_time_ms": elapsed_ms,
            }

        predicted_label = prediction_from_score(score)
        confidence = confidence_from_score(score, predicted_label)
        return {
            "image_path": display_path(image_path),
            "true_label": true_label,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "score": round(score, 4),
            "raw_result": summarize_raw_result(report),
            "status": "success",
            "error_message": "",
            "inference_time_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "image_path": display_path(image_path),
            "true_label": true_label,
            "predicted_label": "",
            "confidence": "",
            "score": "",
            "raw_result": "",
            "status": "error",
            "error_message": str(exc),
            "inference_time_ms": elapsed_ms,
        }


def confusion_counts(rows: list[dict[str, Any]], prediction_key: str = "predicted_label") -> dict[str, int]:
    counts = {
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
    }
    for row in rows:
        true_label = row.get("true_label")
        predicted_label = row.get(prediction_key)
        if true_label == "ai" and predicted_label == "ai":
            counts["true_positive"] += 1
        elif true_label == "real" and predicted_label == "real":
            counts["true_negative"] += 1
        elif true_label == "real" and predicted_label == "ai":
            counts["false_positive"] += 1
        elif true_label == "ai" and predicted_label == "real":
            counts["false_negative"] += 1
    return counts


def calculate_metrics(rows: list[dict[str, Any]], prediction_key: str = "predicted_label") -> dict[str, Any]:
    labeled_rows = [
        row
        for row in rows
        if row.get("true_label") in VALID_LABELS and row.get(prediction_key) in VALID_LABELS
    ]
    counts = confusion_counts(labeled_rows, prediction_key=prediction_key)
    total = len(labeled_rows)
    correct = counts["true_positive"] + counts["true_negative"]
    predicted_ai = counts["true_positive"] + counts["false_positive"]
    predicted_real = counts["true_negative"] + counts["false_negative"]
    actual_ai = counts["true_positive"] + counts["false_negative"]
    precision_ai = safe_divide(counts["true_positive"], predicted_ai)
    if precision_ai is None:
        precision_ai = 0.0
    recall_ai = safe_divide(counts["true_positive"], actual_ai)
    if recall_ai is None:
        recall_ai = 0.0
    f1_ai = 0.0
    if precision_ai > 0 and recall_ai > 0:
        f1_ai = round(2 * precision_ai * recall_ai / (precision_ai + recall_ai), 4)

    return {
        "total": total,
        "correct": correct,
        "accuracy": safe_divide(correct, total),
        "predicted_ai_count": predicted_ai,
        "predicted_real_count": predicted_real,
        "precision_ai": precision_ai,
        "recall_ai": recall_ai,
        "f1_ai": f1_ai,
        "ai_precision": precision_ai,
        "ai_recall": recall_ai,
        "ai_f1": f1_ai,
        **counts,
    }


def write_predictions(rows: list[dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PREDICTION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PREDICTION_FIELDS})


def write_summary(summary: dict[str, Any], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def threshold_scan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored_rows = [
        row
        for row in rows
        if row.get("status") == "success"
        and row.get("true_label") in VALID_LABELS
        and safe_float(row.get("score")) is not None
    ]
    scan_rows: list[dict[str, Any]] = []
    for index in range(1, 10):
        threshold = round(index / 10, 1)
        threshold_rows = []
        for row in scored_rows:
            score = safe_float(row.get("score"))
            threshold_rows.append(
                {
                    **row,
                    "threshold_predicted_label": "ai" if score is not None and score >= threshold else "real",
                }
            )
        metrics = calculate_metrics(threshold_rows, prediction_key="threshold_predicted_label")
        scan_rows.append(
            {
                "threshold": threshold,
                "accuracy": metrics["accuracy"],
                "precision_ai": metrics["precision_ai"],
                "recall_ai": metrics["recall_ai"],
                "f1_ai": metrics["f1_ai"],
                "false_positive": metrics["false_positive"],
                "false_negative": metrics["false_negative"],
            }
        )
    return scan_rows


def write_threshold_scan(scan_rows: list[dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=THRESHOLD_FIELDS)
        writer.writeheader()
        writer.writerows(scan_rows)


def metric_text(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.4f}"


def render_report(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    scan_rows: list[dict[str, Any]],
    dataset_root: Path,
) -> str:
    mistakes = [
        row
        for row in rows
        if row.get("status") == "success"
        and row.get("true_label") in VALID_LABELS
        and row.get("predicted_label") in VALID_LABELS
        and row.get("true_label") != row.get("predicted_label")
    ]

    lines = [
        "# Day4 Evaluation Report",
        "",
        f"- Evaluation time: {summary['evaluation_time']}",
        f"- Test set path: `{dataset_root}`",
        f"- Real image count: {summary['real_count']}",
        f"- AI image count: {summary['ai_count']}",
        f"- Total image count: {summary['total']}",
        "",
        "## Metrics",
        "",
        f"- Accuracy: {metric_text(summary['accuracy'])}",
        f"- Precision (AI): {metric_text(summary['precision_ai'])}",
        f"- Recall (AI): {metric_text(summary['recall_ai'])}",
        f"- F1 (AI): {metric_text(summary['f1_ai'])}",
        "",
        "## Confusion Matrix",
        "",
        "| True \\ Predicted | AI | Real |",
        "| --- | ---: | ---: |",
        f"| AI | {summary['true_positive']} | {summary['false_negative']} |",
        f"| Real | {summary['false_positive']} | {summary['true_negative']} |",
        "",
        "## Misclassified Samples",
        "",
    ]
    if summary.get("predicted_ai_count") == 0:
        matrix_index = lines.index("## Confusion Matrix")
        lines[matrix_index:matrix_index] = [
            "- 当前模型没有预测出任何 AI 样本，因此 AI Precision 按 0 处理。",
            "",
        ]

    if mistakes:
        lines.extend(["| Image | True Label | Predicted Label | Confidence | Score |", "| --- | --- | --- | ---: | ---: |"])
        for row in mistakes:
            lines.append(
                f"| `{row['image_path']}` | {row['true_label']} | {row['predicted_label']} | "
                f"{row.get('confidence') or 'N/A'} | {row.get('score') or 'N/A'} |"
            )
    else:
        lines.append("No misclassified samples.")

    lines.extend(
        [
            "",
            "## Threshold Scan",
            "",
        ]
    )
    if scan_rows:
        lines.append("Current detector provides `final_score`, so threshold scanning was completed from 0.1 to 0.9.")
    else:
        lines.append("当前检测器没有稳定的数值置信度输出，因此 Day4 暂不进行阈值扫描。")

    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            (
                f"Current baseline accuracy is {metric_text(summary['accuracy'])}, "
                f"with AI precision {metric_text(summary['precision_ai'])}, "
                f"AI recall {metric_text(summary['recall_ai'])}, "
                f"and AI F1 {metric_text(summary['f1_ai'])}."
            ),
            "",
            "## Next Optimization Suggestions",
            "",
            "- Keep this script as the fixed Day4 evaluation baseline.",
            "- Expand the test set while keeping real and AI samples balanced.",
            "- Compare future detector changes with the same dataset and output metrics.",
            "- Use threshold_scan.csv to choose a threshold based on false positive and false negative tradeoffs.",
            "",
        ]
    )
    return "\n".join(lines)


def run(dataset: Path, output: Path) -> dict[str, Any]:
    dataset_root = resolve_path(dataset)
    output_dir = resolve_path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_report_dir = output_dir / "image_reports"
    image_items = iter_labeled_images(dataset_root)
    rows = [evaluate_one(image_path, true_label, image_report_dir) for image_path, true_label in image_items]
    success_rows = [row for row in rows if row.get("status") == "success"]
    metrics = calculate_metrics(success_rows)
    scan_rows = threshold_scan(rows)

    summary = {
        "evaluation_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_path": str(dataset_root),
        "real_count": sum(1 for _, label in image_items if label == "real"),
        "ai_count": sum(1 for _, label in image_items if label == "ai"),
        "success_count": len(success_rows),
        "error_count": len(rows) - len(success_rows),
        **metrics,
    }

    write_predictions(rows, output_dir / "predictions.csv")
    write_summary(summary, output_dir / "summary.json")
    write_threshold_scan(scan_rows, output_dir / "threshold_scan.csv")
    (output_dir / "report.md").write_text(
        render_report(summary, rows, scan_rows, dataset_root),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    summary = run(args.dataset, args.output)
    print(f"Total: {summary['total']}")
    print(f"Correct: {summary['correct']}")
    print(f"Accuracy: {metric_text(summary['accuracy'])}")
    print(f"Precision AI: {metric_text(summary['precision_ai'])}")
    print(f"Recall AI: {metric_text(summary['recall_ai'])}")
    print(f"F1 AI: {metric_text(summary['f1_ai'])}")
    print(f"Output: {display_path(resolve_path(args.output))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
