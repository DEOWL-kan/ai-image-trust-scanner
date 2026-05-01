from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


RESULTS_CSV = PROJECT_ROOT / "data" / "outputs" / "results.csv"
SUMMARY_JSON = PROJECT_ROOT / "data" / "outputs" / "summary.json"
VALID_LABELS = {"real", "ai"}


def _safe_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def read_results(results_csv: Path) -> list[dict[str, str]]:
    if not results_csv.exists():
        raise FileNotFoundError(f"Results CSV not found: {results_csv}")
    with results_csv.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def calculate_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    success_rows = [row for row in rows if row.get("status") == "success"]
    labeled_rows = [
        row
        for row in success_rows
        if row.get("true_label") in VALID_LABELS and row.get("pred_label") in VALID_LABELS
    ]

    accuracy = None
    if labeled_rows:
        correct_count = sum(1 for row in labeled_rows if row["true_label"] == row["pred_label"])
        accuracy = round(correct_count / len(labeled_rows), 4)

    confidences = [
        value
        for value in (_safe_float(row.get("confidence")) for row in success_rows)
        if value is not None
    ]
    inference_times = [
        value
        for value in (_safe_float(row.get("inference_time_ms")) for row in success_rows)
        if value is not None
    ]

    true_labels = [row.get("true_label", "") for row in success_rows]
    pred_labels = [row.get("pred_label", "") for row in success_rows]
    real_count = sum(1 for label in true_labels if label == "real")
    ai_count = sum(1 for label in true_labels if label == "ai")
    predicted_real_count = sum(1 for label in pred_labels if label == "real")
    predicted_ai_count = sum(1 for label in pred_labels if label == "ai")
    true_real_pred_real = sum(
        1
        for row in labeled_rows
        if row["true_label"] == "real" and row["pred_label"] == "real"
    )
    true_real_pred_ai = sum(
        1
        for row in labeled_rows
        if row["true_label"] == "real" and row["pred_label"] == "ai"
    )
    true_ai_pred_real = sum(
        1
        for row in labeled_rows
        if row["true_label"] == "ai" and row["pred_label"] == "real"
    )
    true_ai_pred_ai = sum(
        1
        for row in labeled_rows
        if row["true_label"] == "ai" and row["pred_label"] == "ai"
    )
    real_recall = _safe_ratio(true_real_pred_real, real_count)
    ai_recall = _safe_ratio(true_ai_pred_ai, ai_count)
    real_precision = _safe_ratio(true_real_pred_real, predicted_real_count)
    ai_precision = _safe_ratio(true_ai_pred_ai, predicted_ai_count)
    balanced_accuracy = None
    if real_recall is not None and ai_recall is not None:
        balanced_accuracy = round((real_recall + ai_recall) / 2, 4)

    return {
        "total_images": len(rows),
        "success_count": len(success_rows),
        "error_count": len(rows) - len(success_rows),
        "accuracy": accuracy,
        "real_count": real_count,
        "ai_count": ai_count,
        "predicted_real_count": predicted_real_count,
        "predicted_ai_count": predicted_ai_count,
        "average_confidence": _average(confidences),
        "average_inference_time_ms": _average(inference_times),
        "true_real_pred_real": true_real_pred_real,
        "true_real_pred_ai": true_real_pred_ai,
        "true_ai_pred_real": true_ai_pred_real,
        "true_ai_pred_ai": true_ai_pred_ai,
        "real_recall": real_recall,
        "ai_recall": ai_recall,
        "real_precision": real_precision,
        "ai_precision": ai_precision,
        "balanced_accuracy": balanced_accuracy,
    }


def write_summary(summary: dict[str, Any], summary_json: Path) -> None:
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _format_metric(value: object, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.4g}{suffix}"


def main() -> int:
    try:
        rows = read_results(RESULTS_CSV)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    summary = calculate_summary(rows)
    write_summary(summary, SUMMARY_JSON)

    print(f"Total: {summary['total_images']}")
    print(f"Success: {summary['success_count']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Accuracy: {_format_metric(summary['accuracy'])}")
    print("Confusion Matrix:")
    print(f"Real -> Real: {summary['true_real_pred_real']}")
    print(f"Real -> AI: {summary['true_real_pred_ai']}")
    print(f"AI -> Real: {summary['true_ai_pred_real']}")
    print(f"AI -> AI: {summary['true_ai_pred_ai']}")
    print(f"AI Recall: {_format_metric(summary['ai_recall'])}")
    print(f"Balanced Accuracy: {_format_metric(summary['balanced_accuracy'])}")
    print(f"Avg Confidence: {_format_metric(summary['average_confidence'])}")
    print(f"Avg Inference Time: {_format_metric(summary['average_inference_time_ms'], ' ms')}")
    print(f"Summary: {SUMMARY_JSON.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
