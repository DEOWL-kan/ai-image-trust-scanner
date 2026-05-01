from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.explainable import classify_features
from src.features import SUPPORTED_EXTENSIONS, ImageScanResult, extract_image_features, scan_supported_images


SUMMARY_FIELDS = [
    "image_path",
    "true_label",
    "file_name",
    "format",
    "width",
    "height",
    "aspect_ratio",
    "file_size_bytes",
    "has_exif",
    "camera_model",
    "software",
    "datetime",
    "sharpness_score",
    "edge_density",
    "rgb_mean_r",
    "rgb_mean_g",
    "rgb_mean_b",
    "rgb_std_r",
    "rgb_std_g",
    "rgb_std_b",
    "color_entropy",
    "noise_score",
    "local_variance_score",
    "jpeg_quality_estimate",
    "compression_artifact_score",
    "compression_artifact_method",
    "risk_score",
    "prediction",
    "confidence",
    "status",
    "error_message",
]


def infer_label(path: Path) -> str:
    label = path.parent.name.lower()
    return label if label in {"real", "ai"} else ""


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_image(path: Path, project_root: Path) -> dict[str, Any]:
    try:
        features = extract_image_features(path)
        features["image_path"] = _display_path(path, project_root)
        explanation = classify_features(features)
        return {
            "status": "success",
            "true_label": infer_label(path),
            "features": features,
            "explanation": explanation,
            "error_message": "",
        }
    except Exception as exc:
        return {
            "status": "error",
            "true_label": infer_label(path),
            "features": {
                "image_path": _display_path(path, project_root),
                "file_name": path.name,
            },
            "explanation": {
                "risk_score": None,
                "prediction": "uncertain",
                "confidence": "low",
                "reasons": ["Image could not be processed, so no feature-based judgment was made."],
            },
            "error_message": str(exc),
        }


def flatten_result(result: dict[str, Any]) -> dict[str, Any]:
    features = result["features"]
    explanation = result["explanation"]
    row = {field: "" for field in SUMMARY_FIELDS}
    for key in features:
        if key in row and key != "metadata_time_fields":
            row[key] = features[key]
    row["true_label"] = result.get("true_label", "")
    row["risk_score"] = explanation.get("risk_score", "")
    row["prediction"] = explanation.get("prediction", "uncertain")
    row["confidence"] = explanation.get("confidence", "low")
    row["status"] = result.get("status", "")
    row["error_message"] = result.get("error_message", "")
    return row


def write_jsonl(results: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")


def write_summary_csv(results: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(flatten_result(result) for result in results)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def build_metrics(
    input_root: Path,
    output_dir: Path,
    results: list[dict[str, Any]],
    scan_result: ImageScanResult,
    generated_at: str,
) -> dict[str, Any]:
    success_results = [result for result in results if result.get("status") == "success"]
    risk_scores = [
        float(result["explanation"]["risk_score"])
        for result in success_results
        if result["explanation"].get("risk_score") is not None
    ]
    predictions = [result["explanation"].get("prediction") for result in success_results]

    return {
        "generated_at": generated_at,
        "input_path": str(input_root),
        "input_directory_scanned": str(scan_result.input_path),
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "found_image_count": len(scan_result.image_paths),
        "skipped_file_count": len(scan_result.skipped_files),
        "output_path": str(output_dir),
        "total_images": len(results),
        "processed_count": len(success_results),
        "error_count": len(results) - len(success_results),
        "likely_real_count": predictions.count("likely_real"),
        "uncertain_count": predictions.count("uncertain"),
        "likely_ai_count": predictions.count("likely_ai"),
        "average_risk_score": average(risk_scores),
        "outputs": {
            "feature_report_jsonl": str(output_dir / "feature_report.jsonl"),
            "feature_summary_csv": str(output_dir / "feature_summary.csv"),
            "explainable_report_md": str(output_dir / "explainable_report.md"),
            "day5_metrics_json": str(output_dir / "day5_metrics.json"),
            "calibration_analysis_md": str(output_dir / "calibration_analysis.md"),
        },
    }


def write_metrics(metrics: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_markdown_report(results: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    lines = [
        "# Day5 Explainable Image Feature Report",
        "",
        "This report provides feature-based signals that can assist AI image detection. It is not an absolute authenticity judgment.",
        "",
        "## Summary",
        "",
        f"- Generated at: {metrics['generated_at']}",
        f"- Input path: `{metrics['input_path']}`",
        f"- Output path: `{metrics['output_path']}`",
        f"- Total supported images: {metrics['total_images']}",
        f"- Processed images: {metrics['processed_count']}",
        f"- Errors: {metrics['error_count']}",
        f"- Average risk score: {metrics['average_risk_score'] if metrics['average_risk_score'] is not None else 'N/A'}",
        f"- Likely real: {metrics['likely_real_count']}",
        f"- Uncertain: {metrics['uncertain_count']}",
        f"- Likely AI: {metrics['likely_ai_count']}",
        "",
        "## Scan Details",
        "",
        f"- Input directory scanned: `{metrics['input_directory_scanned']}`",
        f"- Supported extensions: {', '.join(metrics['supported_extensions'])}",
        f"- Found image count: {metrics['found_image_count']}",
        f"- Skipped file count: {metrics['skipped_file_count']}",
        f"- Error count: {metrics['error_count']}",
        "",
        "## Output Files",
        "",
        "- `feature_report.jsonl`: one detailed JSON object per processed image.",
        "- `feature_summary.csv`: flat table of features, score, prediction, and confidence.",
        "- `explainable_report.md`: this human-readable report.",
        "- `day5_metrics.json`: aggregate run metrics.",
        "- `calibration_analysis.md`: label-group calibration notes derived from `feature_summary.csv`.",
        "",
        "## Feature Guide",
        "",
        "- Metadata features check EXIF, camera model, software, and timestamp fields.",
        "- Sharpness score estimates local detail with a Laplacian-style variance calculation.",
        "- Edge density measures how many neighboring pixels have strong transitions.",
        "- RGB mean and standard deviation summarize brightness and color spread per channel.",
        "- Color entropy measures how diverse the color distribution is.",
        "- Noise score and local variance estimate fine texture after light smoothing.",
        "- Compression artifacts use JPEG quantization when available, otherwise an 8x8 blockiness fallback.",
        "",
        "## Image Results",
        "",
    ]

    success_results = [result for result in results if result.get("status") == "success"]
    if not success_results:
        if metrics["found_image_count"] == 0:
            lines.extend(["No supported image files found under input path.", ""])
        else:
            lines.extend(["No supported images were processed successfully.", ""])
    else:
        lines.extend(
            [
                "| Image | Label | Risk | Prediction | Confidence | Key Reasons |",
                "| --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for result in success_results:
            features = result["features"]
            explanation = result["explanation"]
            reasons = "; ".join(explanation.get("reasons", [])[:3])
            lines.append(
                f"| `{features.get('image_path', '')}` | {result.get('true_label') or 'N/A'} | "
                f"{explanation.get('risk_score', 'N/A')} | {explanation.get('prediction', 'uncertain')} | "
                f"{explanation.get('confidence', 'low')} | {reasons} |"
            )
        lines.append("")

    error_results = [result for result in results if result.get("status") != "success"]
    if error_results:
        lines.extend(["## Processing Errors", "", "| Image | Error |", "| --- | --- |"])
        for result in error_results:
            features = result["features"]
            lines.append(f"| `{features.get('image_path', '')}` | {result.get('error_message', '')} |")
        lines.append("")

    lines.extend(
        [
            "## Interpretation Notes",
            "",
            "- A high risk score means the available explainable signals resemble patterns often seen in generated or heavily processed images.",
            "- A low risk score means the available signals contain more camera-like or compression-history evidence.",
            "- The score should be reviewed together with model output, source context, and provenance metadata.",
            "",
        ]
    )
    return "\n".join(lines)


def _format(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_safe_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return average(clean)


def _min(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_safe_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return round(min(clean), 4) if clean else None


def _max(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_safe_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return round(max(clean), 4) if clean else None


def build_calibration_analysis(results: list[dict[str, Any]]) -> str:
    rows = [flatten_result(result) for result in results if result.get("status") == "success"]
    groups: dict[str, list[dict[str, Any]]] = {
        label: [row for row in rows if row.get("true_label") == label]
        for label in ("ai", "real")
    }

    lines = [
        "# Day5 Calibration Analysis",
        "",
        "Generated from `reports/day5/feature_summary.csv`.",
        "",
        "This analysis is a calibration note for the current explainable heuristics. It does not change the scoring logic and should not be treated as a final detector evaluation.",
        "",
        "## Dataset Summary",
        "",
        "| true_label | count | avg risk_score | min risk_score | max risk_score | avg sharpness_score | avg edge_density | avg color_entropy | avg noise_score | has_exif ratio | avg jpeg_quality_estimate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for label in ("ai", "real"):
        group = groups[label]
        exif_ratio = (sum(1 for row in group if str(row.get("has_exif")) == "True") / len(group)) if group else 0.0
        lines.append(
            f"| {label} | {len(group)} | {_format(_avg(group, 'risk_score'))} | {_format(_min(group, 'risk_score'))} | "
            f"{_format(_max(group, 'risk_score'))} | {_format(_avg(group, 'sharpness_score'))} | "
            f"{_format(_avg(group, 'edge_density'))} | {_format(_avg(group, 'color_entropy'))} | "
            f"{_format(_avg(group, 'noise_score'))} | {exif_ratio:.4f} | {_format(_avg(group, 'jpeg_quality_estimate'))} |"
        )

    likely_counts = {}
    for label in ("ai", "real"):
        group = groups[label]
        likely_counts[label] = {
            "likely_real": sum(1 for row in group if row.get("prediction") == "likely_real"),
            "uncertain": sum(1 for row in group if row.get("prediction") == "uncertain"),
            "likely_ai": sum(1 for row in group if row.get("prediction") == "likely_ai"),
        }

    misjudged_real = [row for row in groups["real"] if row.get("prediction") == "likely_ai"]
    low_risk_ai = [row for row in groups["ai"] if (_safe_float(row.get("risk_score")) or 0.0) < 50]
    low_risk_ai = sorted(low_risk_ai, key=lambda row: _safe_float(row.get("risk_score")) or 0.0)[:5]

    lines.extend(
        [
            "",
            "## Prediction Distribution",
            "",
            "| true_label | likely_real | uncertain | likely_ai |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for label in ("ai", "real"):
        counts = likely_counts[label]
        lines.append(f"| {label} | {counts['likely_real']} | {counts['uncertain']} | {counts['likely_ai']} |")

    lines.extend(
        [
            "",
            "## Calibration Notes",
            "",
            "- Risk score has weak separation on the current small test set.",
            "- Sharpness, edge density, color entropy, and noise score show some separation, but this dataset has AI images with higher averages than Real images.",
            "- Missing EXIF is weak as a standalone signal because Real images can also lack EXIF after phone, web, or platform processing.",
            "- JPEG quality is only available for JPEG files here, while AI samples are PNG, so it should be treated as source context rather than general AI evidence.",
            "- Current thresholds are conservative; lowering the likely-AI threshold before recalibrating feature weights would likely increase real-image false positives.",
            "",
            "## Misjudged Real Images",
            "",
        ]
    )
    if misjudged_real:
        lines.extend(["| file_name | risk_score | prediction | sharpness_score | edge_density | color_entropy | noise_score | has_exif | jpeg_quality_estimate |", "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |"])
        for row in misjudged_real:
            lines.append(
                f"| {row['file_name']} | {_format(_safe_float(row['risk_score']))} | {row['prediction']} | "
                f"{_format(_safe_float(row['sharpness_score']))} | {_format(_safe_float(row['edge_density']))} | "
                f"{_format(_safe_float(row['color_entropy']))} | {_format(_safe_float(row['noise_score']))} | "
                f"{row['has_exif']} | {_format(_safe_float(row['jpeg_quality_estimate']))} |"
            )
    else:
        lines.append("No Real images were classified as likely_ai.")

    lines.extend(["", "## Low-Risk AI Images", ""])
    if low_risk_ai:
        lines.extend(["| file_name | risk_score | sharpness_score | edge_density | color_entropy | noise_score |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for row in low_risk_ai:
            lines.append(
                f"| {row['file_name']} | {_format(_safe_float(row['risk_score']))} | "
                f"{_format(_safe_float(row['sharpness_score']))} | {_format(_safe_float(row['edge_density']))} | "
                f"{_format(_safe_float(row['color_entropy']))} | {_format(_safe_float(row['noise_score']))} |"
            )
    else:
        lines.append("No AI images have risk scores below 50.")

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "- Keep scoring weights unchanged for Day5 closeout; this file is analysis only.",
            "- Recalibrate detail-feature direction before changing the likely-AI threshold.",
            "- Reduce reliance on missing EXIF as a standalone risk signal in future tuning.",
            "- Treat JPEG quality and file format as collection-context notes, not direct authenticity proof.",
            "- Add more diverse real and AI samples before using risk_score as a stronger decision aid.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(report: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def run_day5_analysis(input_root: Path, output_dir: Path, project_root: Path | None = None) -> dict[str, Any]:
    project_root = project_root or Path.cwd()
    input_root = input_root if input_root.is_absolute() else (project_root / input_root)
    output_dir = output_dir if output_dir.is_absolute() else (project_root / output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    scan_result = scan_supported_images(input_root)
    results = [analyze_image(path, project_root) for path in scan_result.image_paths]

    feature_report = output_dir / "feature_report.jsonl"
    feature_summary = output_dir / "feature_summary.csv"
    report_md = output_dir / "explainable_report.md"
    metrics_json = output_dir / "day5_metrics.json"
    calibration_md = output_dir / "calibration_analysis.md"

    metrics = build_metrics(input_root, output_dir, results, scan_result, generated_at)
    write_jsonl(results, feature_report)
    write_summary_csv(results, feature_summary)
    write_markdown_report(build_markdown_report(results, metrics), report_md)
    write_metrics(metrics, metrics_json)
    write_markdown_report(build_calibration_analysis(results), calibration_md)

    return {
        "results": results,
        "metrics": metrics,
        "feature_report_jsonl": feature_report,
        "feature_summary_csv": feature_summary,
        "explainable_report_md": report_md,
        "day5_metrics_json": metrics_json,
        "calibration_analysis_md": calibration_md,
    }
