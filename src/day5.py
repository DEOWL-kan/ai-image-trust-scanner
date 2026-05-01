from __future__ import annotations

import argparse
from pathlib import Path

from src.day5_reports import run_day5_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract explainable image features and write Day5 reports.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "test_images",
        help="Input image file or dataset directory. Default: data/test_images",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "day5",
        help="Output directory for Day5 reports. Default: reports/day5",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_day5_analysis(args.input, args.output, project_root=PROJECT_ROOT)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    metrics = result["metrics"]
    print(f"Input: {metrics['input_path']}")
    print(f"Input directory scanned: {metrics['input_directory_scanned']}")
    print(f"Supported extensions: {', '.join(metrics['supported_extensions'])}")
    print(f"Found image count: {metrics['found_image_count']}")
    print(f"Skipped file count: {metrics['skipped_file_count']}")
    print(f"Total supported images: {metrics['total_images']}")
    print(f"Processed: {metrics['processed_count']}")
    print(f"Errors: {metrics['error_count']}")
    print(f"Likely real: {metrics['likely_real_count']}")
    print(f"Uncertain: {metrics['uncertain_count']}")
    print(f"Likely AI: {metrics['likely_ai_count']}")
    print(f"Feature JSONL: {result['feature_report_jsonl']}")
    print(f"Feature CSV: {result['feature_summary_csv']}")
    print(f"Markdown report: {result['explainable_report_md']}")
    print(f"Metrics: {result['day5_metrics_json']}")
    print(f"Calibration: {result['calibration_analysis_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
