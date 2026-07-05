from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.adapters.product_output_schema import build_product_output
from app.pipeline.forensic_analyzer import analyze_forensics
from app.pipeline.frequency_analyzer import analyze_frequency
from app.pipeline.image_loader import load_image
from app.pipeline.metadata_analyzer import analyze_metadata
from app.pipeline.model_detector import detect_with_model
from app.pipeline.report_generator import build_report, write_reports
from app.pipeline.score_fusion import fuse_scores


def _skipped_result(reason: str) -> dict[str, Any]:
    return {
        "checked": False,
        "error": reason,
    }


def run_pipeline(
    image_path: str | Path,
    output_dir: str | Path = "outputs/reports",
    write_output: bool = True,
    analysis_image_path: str | Path | None = None,
) -> dict[str, Any]:
    image_info = load_image(image_path)

    if image_info.get("ok"):
        metadata_result = analyze_metadata(image_info["image_path"])
        analysis_path = str(analysis_image_path or image_info["image_path"])
        forensic_result = analyze_forensics(analysis_path)
        frequency_result = analyze_frequency(analysis_path)
        model_result = detect_with_model(analysis_path)
        if analysis_image_path:
            forensic_result["analysis_image_path"] = analysis_path
            frequency_result["analysis_image_path"] = analysis_path
            model_result["analysis_image_path"] = analysis_path
    else:
        reason = image_info.get("error") or "Image could not be loaded."
        metadata_result = _skipped_result(reason)
        forensic_result = _skipped_result(reason)
        frequency_result = _skipped_result(reason)
        model_result = {
            "checked": False,
            "ai_probability": 0.5,
            "model_name": "v0.1-baseline-placeholder",
            "model_status": "placeholder",
            "error": reason,
        }

    final_result = fuse_scores(
        metadata_result=metadata_result,
        forensic_result=forensic_result,
        frequency_result=frequency_result,
        model_result=model_result,
    )
    report = build_report(
        image_info=image_info,
        metadata_result=metadata_result,
        forensic_result=forensic_result,
        frequency_result=frequency_result,
        model_result=model_result,
        final_result=final_result,
    )
    report_paths = write_reports(report, output_dir=output_dir) if write_output else {}
    report["report_paths"] = report_paths
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AI Image Trust Scanner V0.1 baseline CLI."
    )
    parser.add_argument("--image", required=True, help="Path to a jpg, jpeg, png, or webp image.")
    parser.add_argument(
        "--output-dir",
        default="outputs/reports",
        help="Directory for JSON and Markdown reports.",
    )
    parser.add_argument(
        "--product-output",
        action="store_true",
        help="Also emit the Day17 product-level JSON schema for this image.",
    )
    parser.add_argument(
        "--product-output-file",
        help="Optional product-level JSON output path. Defaults to <output-dir>/<image>_product.json.",
    )
    args = parser.parse_args(argv)

    report = run_pipeline(args.image, output_dir=args.output_dir)
    summary = {
        "ok": report.get("ok"),
        "final_result": report.get("final_result"),
        "report_paths": report.get("report_paths"),
    }
    if args.product_output:
        product_output = build_product_output(report, image_path=args.image, debug=True)
        product_path = (
            Path(args.product_output_file)
            if args.product_output_file
            else Path(args.output_dir) / f"{Path(args.image).stem or 'image'}_product.json"
        )
        product_path.parent.mkdir(parents=True, exist_ok=True)
        product_path.write_text(
            json.dumps(product_output, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        summary["product_output"] = product_output
        summary["product_output_path"] = str(product_path.resolve())
    if not report.get("ok"):
        summary["error"] = report.get("image_info", {}).get("error")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
