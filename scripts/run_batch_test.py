from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
INPUT_ROOT = PROJECT_ROOT / "data" / "test_images"
OUTPUT_CSV = PROJECT_ROOT / "data" / "outputs" / "results.csv"
REPORT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "reports"
CSV_FIELDS = [
    "image_path",
    "true_label",
    "pred_label",
    "confidence",
    "width",
    "height",
    "inference_time_ms",
    "status",
    "error_message",
]


def iter_labeled_images(input_root: Path) -> list[tuple[Path, str]]:
    images: list[tuple[Path, str]] = []
    for true_label in ("real", "ai"):
        label_dir = input_root / true_label
        if not label_dir.exists():
            continue
        for image_path in sorted(label_dir.rglob("*")):
            if image_path.is_file() and image_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append((image_path, true_label))
    return images


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _prediction_from_report(report: dict[str, Any]) -> tuple[str, float]:
    final_score = float(report.get("final_result", {}).get("final_score", 0.5))
    pred_label = "ai" if final_score >= 0.5 else "real"
    confidence = final_score if pred_label == "ai" else 1.0 - final_score
    return pred_label, round(confidence, 4)


def detect_image_for_batch(image_path: Path, true_label: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        report = run_pipeline(image_path, output_dir=REPORT_OUTPUT_DIR)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        image_info = report.get("image_info", {})

        if not report.get("ok"):
            return {
                "image_path": _display_path(image_path),
                "true_label": true_label,
                "pred_label": "",
                "confidence": "",
                "width": image_info.get("width") or "",
                "height": image_info.get("height") or "",
                "inference_time_ms": elapsed_ms,
                "status": "error",
                "error_message": image_info.get("error") or "Image could not be processed.",
            }

        pred_label, confidence = _prediction_from_report(report)
        return {
            "image_path": _display_path(image_path),
            "true_label": true_label,
            "pred_label": pred_label,
            "confidence": confidence,
            "width": image_info.get("width") or "",
            "height": image_info.get("height") or "",
            "inference_time_ms": elapsed_ms,
            "status": "success",
            "error_message": "",
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "image_path": _display_path(image_path),
            "true_label": true_label,
            "pred_label": "",
            "confidence": "",
            "width": "",
            "height": "",
            "inference_time_ms": elapsed_ms,
            "status": "error",
            "error_message": str(exc),
        }


def write_results(rows: list[dict[str, object]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    image_items = iter_labeled_images(INPUT_ROOT)
    rows = [detect_image_for_batch(image_path, true_label) for image_path, true_label in image_items]
    write_results(rows, OUTPUT_CSV)

    success_count = sum(1 for row in rows if row["status"] == "success")
    error_count = len(rows) - success_count
    print(f"Total: {len(rows)}")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Results: {_display_path(OUTPUT_CSV)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
