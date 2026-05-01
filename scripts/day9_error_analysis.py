from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.score_fusion import load_detector_weight_config  # noqa: E402


DAY8_DIR = PROJECT_ROOT / "reports" / "day8"
DAY9_DIR = PROJECT_ROOT / "reports" / "day9"
PREDICTIONS_CSV = DAY8_DIR / "day8_predictions.csv"
IMAGE_REPORT_DIR = DAY8_DIR / "image_reports"
WEIGHTS_CONFIG = PROJECT_ROOT / "configs" / "detector_weights.json"

DEFAULT_THRESHOLDS = {
    "balanced": 0.15,
    "conservative": 0.18,
}
DEFAULT_LOW_CONFIDENCE_MARGIN = 0.03

MISCLASSIFICATION_FIELDS = [
    "threshold_mode",
    "threshold",
    "filename",
    "class_label",
    "ground_truth",
    "predicted_label",
    "final_label",
    "confidence_level",
    "strategy_reason",
    "error_type",
    "ai_score",
    "margin_to_threshold",
    "scene_tag",
    "scenario",
    "attribution_bucket",
    "dominant_component",
    "metadata_score",
    "forensic_score",
    "frequency_score",
    "model_score",
    "metadata_contribution",
    "forensic_contribution",
    "frequency_contribution",
    "model_contribution",
    "high_frequency_energy_ratio",
    "edge_density",
    "laplacian_variance",
    "noise_estimate",
    "brightness_std",
    "format",
    "width",
    "height",
    "file_size_kb",
    "has_exif",
    "software",
    "evidence_notes",
]

SUMMARY_FIELDS = [
    "group",
    "count",
    "avg_ai_score",
    "avg_margin_abs",
    "avg_metadata_score",
    "avg_forensic_score",
    "avg_frequency_score",
    "avg_metadata_contribution",
    "avg_forensic_contribution",
    "avg_frequency_contribution",
    "avg_high_frequency_energy_ratio",
    "avg_edge_density",
    "avg_laplacian_variance",
    "avg_noise_estimate",
    "avg_brightness_std",
    "exif_ratio",
    "jpeg_count",
    "png_count",
    "webp_count",
]

SCENE_STATS_FIELDS = [
    "scene_tag",
    "sample_count",
    "false_positive",
    "false_negative",
    "accuracy",
    "avg_ai_score",
    "recommended_threshold_mode",
    "recommended_action",
]


@dataclass(frozen=True)
class PredictionRow:
    filename: str
    class_label: str
    ground_truth: str
    ai_score: float


@dataclass(frozen=True)
class AnalyzedSample:
    filename: str
    class_label: str
    ground_truth: str
    ai_score: float
    report: dict[str, Any]
    component_scores: dict[str, float]
    component_weights: dict[str, float]
    contributions: dict[str, float]
    scenario: str
    scene_tag: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day9 misclassification attribution and scenario strategy report.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=PREDICTIONS_CSV,
        help="Day8 predictions CSV. Default: reports/day8/day8_predictions.csv",
    )
    parser.add_argument(
        "--image-report-dir",
        type=Path,
        default=IMAGE_REPORT_DIR,
        help="Day8 per-image report directory. Default: reports/day8/image_reports",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DAY9_DIR,
        help="Day9 output directory. Default: reports/day9",
    )
    parser.add_argument(
        "--balanced-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["balanced"],
        help="Balanced threshold to analyze. Default: 0.15",
    )
    parser.add_argument(
        "--conservative-threshold",
        type=float,
        default=DEFAULT_THRESHOLDS["conservative"],
        help="Conservative threshold to analyze. Default: 0.18",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_predictions(predictions_csv: Path) -> list[PredictionRow]:
    if not predictions_csv.exists():
        raise FileNotFoundError(f"Day8 predictions CSV not found: {predictions_csv}")

    with predictions_csv.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    predictions: list[PredictionRow] = []
    for row in rows:
        score_text = row.get("ai_score", "")
        if not score_text:
            continue
        predictions.append(
            PredictionRow(
                filename=row["filename"],
                class_label=row.get("class_label", ""),
                ground_truth=row.get("ground_truth", ""),
                ai_score=float(score_text),
            )
        )
    if not predictions:
        raise ValueError("No usable rows with ai_score were found in Day8 predictions.")
    return predictions


def report_path_for(image_report_dir: Path, prediction: PredictionRow) -> Path:
    return image_report_dir / f"{Path(prediction.filename).stem}_report.json"


def load_or_create_report(image_report_dir: Path, prediction: PredictionRow) -> dict[str, Any]:
    path = report_path_for(image_report_dir, prediction)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    image_path = PROJECT_ROOT / "data" / "test_images" / prediction.class_label / prediction.filename
    if not image_path.exists():
        raise FileNotFoundError(f"Missing image report and source image: {path}")

    from main import run_pipeline

    return run_pipeline(image_path, output_dir=image_report_dir)


def normalize_component_scores(final_result: dict[str, Any]) -> dict[str, float]:
    raw_scores = final_result.get("component_scores", {})
    return {
        "metadata": safe_float(raw_scores.get("metadata_score")),
        "forensic": safe_float(raw_scores.get("forensic_score")),
        "frequency": safe_float(raw_scores.get("frequency_score")),
        "model": safe_float(raw_scores.get("model_score")),
    }


def normalize_component_weights(final_result: dict[str, Any]) -> dict[str, float]:
    raw_weights = final_result.get("component_weights", {})
    return {
        "metadata": safe_float(raw_weights.get("metadata"), 0.0),
        "forensic": safe_float(raw_weights.get("forensic"), 0.0),
        "frequency": safe_float(raw_weights.get("frequency"), 0.0),
        "model": safe_float(raw_weights.get("model"), 0.0),
    }


def component_contributions(scores: dict[str, float], weights: dict[str, float]) -> dict[str, float]:
    active_weight = sum(weights.values()) or 1.0
    return {
        key: round((scores.get(key, 0.0) * weights.get(key, 0.0)) / active_weight, 6)
        for key in ("metadata", "forensic", "frequency", "model")
    }


def low_confidence_margin() -> float:
    config = load_detector_weight_config(WEIGHTS_CONFIG)
    profile_name = str(config.get("default_profile") or "baseline")
    profile = config.get("profiles", {}).get(profile_name, {})
    return safe_float(
        profile.get("experiment_weights", {}).get("low_confidence_margin"),
        DEFAULT_LOW_CONFIDENCE_MARGIN,
    )


def classify_scenario(report: dict[str, Any]) -> str:
    image_info = report.get("image_info", {})
    metadata = report.get("metadata_result", {})
    image_format = str(image_info.get("format") or "").upper()
    has_exif = bool(metadata.get("has_exif"))
    camera_model = str(metadata.get("camera_model") or "").strip()
    software = str(metadata.get("software") or "").strip().lower()

    if any(term in software for term in ("midjourney", "stable diffusion", "dall", "comfyui", "firefly")):
        return "ai_tool_metadata"
    if image_format in {"JPEG", "JPG"} and (has_exif or camera_model):
        return "camera_photo_with_exif"
    if image_format in {"JPEG", "JPG"} and not has_exif:
        return "web_or_social_jpeg_no_exif"
    if image_format == "PNG" and not has_exif:
        return "png_export_no_exif"
    if image_format == "WEBP":
        return "webp_platform_export"
    if not has_exif:
        return "metadata_stripped_export"
    return "generic_image"


def keyword_scene_tag(filename: str) -> str | None:
    text = filename.lower().replace("-", "_").replace(" ", "_")
    keyword_map = [
        ("window_rain", ("window_rain", "rain", "wet_window")),
        ("vehicle", ("vehicle", "car", "truck", "bus", "bike", "motorcycle")),
        ("road", ("road", "street", "highway", "traffic")),
        ("food", ("food", "meal", "dish", "plate", "restaurant")),
        ("shelf", ("shelf", "store", "aisle", "rack")),
        ("landscape", ("landscape", "mountain", "beach", "forest", "sky")),
        ("indoor", ("indoor", "room", "kitchen", "office", "home")),
        ("outdoor", ("outdoor", "park", "garden", "city")),
        ("closeup_object", ("closeup", "object", "product")),
    ]
    for scene_tag, keywords in keyword_map:
        if any(keyword in text for keyword in keywords):
            return scene_tag
    return None


def classify_scene_tag(filename: str, report: dict[str, Any]) -> str:
    keyword_tag = keyword_scene_tag(filename)
    if keyword_tag:
        return keyword_tag

    image_info = report.get("image_info", {})
    metadata = report.get("metadata_result", {})
    forensic = report.get("forensic_result", {})
    image_format = str(image_info.get("format") or "").upper()
    width = safe_float(image_info.get("width"))
    height = safe_float(image_info.get("height"))
    aspect_ratio = (width / height) if height else 1.0
    brightness_mean = safe_float(forensic.get("brightness_mean"))
    brightness_std = safe_float(forensic.get("brightness_std"))
    edge_density = safe_float(forensic.get("edge_density"))
    laplacian = safe_float(forensic.get("laplacian_variance"))
    noise = safe_float(forensic.get("noise_estimate"))
    has_exif = bool(metadata.get("has_exif"))

    if brightness_mean < 80 or (brightness_mean < 105 and brightness_std < 35):
        return "low_light"
    if edge_density < 0.035 or laplacian < 180:
        return "closeup_object"
    if aspect_ratio >= 1.55 and edge_density < 0.08 and brightness_mean >= 95:
        return "landscape"
    if aspect_ratio >= 1.15 and edge_density >= 0.12 and brightness_mean >= 95:
        return "road"
    if edge_density >= 0.10 and laplacian >= 900:
        return "shelf"
    if image_format in {"JPEG", "JPG"} and has_exif and brightness_mean >= 95 and noise >= 3.0:
        return "outdoor"
    if image_format in {"JPEG", "JPG"} and brightness_mean < 130:
        return "indoor"
    return "unknown"


def analyze_samples(predictions: list[PredictionRow], image_report_dir: Path) -> list[AnalyzedSample]:
    samples: list[AnalyzedSample] = []
    for prediction in predictions:
        report = load_or_create_report(image_report_dir, prediction)
        final_result = report.get("final_result", {})
        scores = normalize_component_scores(final_result)
        weights = normalize_component_weights(final_result)
        samples.append(
            AnalyzedSample(
                filename=prediction.filename,
                class_label=prediction.class_label,
                ground_truth=prediction.ground_truth,
                ai_score=prediction.ai_score,
                report=report,
                component_scores=scores,
                component_weights=weights,
                contributions=component_contributions(scores, weights),
                scenario=classify_scenario(report),
                scene_tag=classify_scene_tag(prediction.filename, report),
            )
        )
    return samples


def predicted_label(score: float, threshold: float) -> str:
    return "AI-generated" if score >= threshold else "Real"


def error_type(sample: AnalyzedSample, threshold: float) -> str:
    prediction = predicted_label(sample.ai_score, threshold)
    if prediction == sample.ground_truth:
        return "correct"
    if sample.ground_truth == "Real" and prediction == "AI-generated":
        return "false_positive"
    if sample.ground_truth == "AI-generated" and prediction == "Real":
        return "false_negative"
    return "misclassified"


def is_low_light_blur_or_compressed(sample: AnalyzedSample) -> bool:
    image_info = sample.report.get("image_info", {})
    forensic = sample.report.get("forensic_result", {})
    metadata = sample.report.get("metadata_result", {})
    image_format = str(image_info.get("format") or "").upper()
    brightness = feature_value(sample, "forensic_result", "brightness_mean")
    laplacian = feature_value(sample, "forensic_result", "laplacian_variance")
    edge_density = feature_value(sample, "forensic_result", "edge_density")
    file_size_kb = safe_float(image_info.get("file_size_kb"))
    no_exif_jpeg = image_format in {"JPEG", "JPG"} and not metadata.get("has_exif")
    low_light = sample.scene_tag == "low_light" or brightness < 80
    blur_like = laplacian < 180 or edge_density < 0.025
    compressed_like = no_exif_jpeg and file_size_kb < 450
    return low_light or blur_like or compressed_like


def has_natural_real_features(sample: AnalyzedSample) -> bool:
    metadata = sample.report.get("metadata_result", {})
    forensic = sample.report.get("forensic_result", {})
    has_exif = bool(metadata.get("has_exif"))
    noise = safe_float(forensic.get("noise_estimate"))
    laplacian = safe_float(forensic.get("laplacian_variance"))
    brightness_std = safe_float(forensic.get("brightness_std"))
    edge_density = safe_float(forensic.get("edge_density"))
    return (
        has_exif
        or (noise >= 4.0 and laplacian >= 350 and brightness_std >= 35 and 0.035 <= edge_density <= 0.22)
    )


def has_synthetic_texture_flags(sample: AnalyzedSample) -> bool:
    forensic = sample.report.get("forensic_result", {})
    frequency = sample.report.get("frequency_result", {})
    edge_density = safe_float(forensic.get("edge_density"))
    laplacian = safe_float(forensic.get("laplacian_variance"))
    noise = safe_float(forensic.get("noise_estimate"))
    frequency_score = safe_float(frequency.get("frequency_score"))
    smooth_texture = laplacian < 260 and noise < 3.5
    uniform_edges = edge_density < 0.04 or edge_density > 0.24
    return smooth_texture and uniform_edges and frequency_score >= 0.28


def scene_strategy_label(sample: AnalyzedSample, threshold: float, margin: float) -> dict[str, str]:
    binary_label = predicted_label(sample.ai_score, threshold)
    distance = sample.ai_score - threshold
    abs_distance = abs(distance)

    if abs_distance <= margin:
        return {
            "final_label": "uncertain",
            "confidence_level": "low",
            "strategy_reason": (
                f"score is within threshold +/- low_confidence_margin ({margin:.2f})"
            ),
        }

    if is_low_light_blur_or_compressed(sample):
        return {
            "final_label": "uncertain",
            "confidence_level": "low",
            "strategy_reason": "image is low-light, blur-like, or strongly compressed, so binary output is protected",
        }

    if binary_label == "AI-generated" and has_natural_real_features(sample):
        return {
            "final_label": "uncertain",
            "confidence_level": "medium",
            "strategy_reason": "binary AI result conflicts with EXIF or natural noise/detail features",
        }

    if binary_label == "Real" and has_synthetic_texture_flags(sample):
        return {
            "final_label": "uncertain",
            "confidence_level": "medium",
            "strategy_reason": "binary Real result conflicts with smooth texture, uniform edges, and low local noise",
        }

    if binary_label == "AI-generated" and has_synthetic_texture_flags(sample):
        return {
            "final_label": "AI-generated",
            "confidence_level": "medium" if abs_distance < margin * 2 else "high",
            "strategy_reason": "AI score is supported by smooth texture, uniform edges, and local-noise consistency",
        }

    if binary_label == "Real" and has_natural_real_features(sample):
        return {
            "final_label": "Real",
            "confidence_level": "medium" if abs_distance < margin * 2 else "high",
            "strategy_reason": "Real result is supported by EXIF or natural noise/detail features",
        }

    return {
        "final_label": binary_label,
        "confidence_level": "medium" if abs_distance < margin * 2 else "high",
        "strategy_reason": "scene-aware rules found no strong reason to override the binary label",
    }


def dominant_component(contributions: dict[str, float]) -> str:
    return max(("metadata", "forensic", "frequency", "model"), key=lambda key: contributions.get(key, 0.0))


def attribution_bucket(sample: AnalyzedSample, threshold: float) -> str:
    kind = error_type(sample, threshold)
    margin = abs(sample.ai_score - threshold)
    scores = sample.component_scores
    contributions = sample.contributions
    final_score = max(sample.ai_score, 0.000001)
    frequency_share = contributions["frequency"] / final_score

    if kind == "false_positive":
        if margin <= 0.02:
            return "borderline_false_positive"
        if scores["forensic"] <= 0.02 and frequency_share >= 0.70:
            return "frequency_dominated_real_image"
        if scores["forensic"] >= 0.10:
            return "forensic_triggered_real_image"
        if scores["metadata"] > 0 and scores["frequency"] >= 0.35:
            return "missing_exif_plus_frequency"
        return "mixed_weak_signals_real_image"

    if kind == "false_negative":
        if margin <= 0.02:
            return "borderline_false_negative"
        if scores["forensic"] <= 0.02 and scores["frequency"] < 0.45:
            return "low_forensic_low_frequency_ai_image"
        if scores["forensic"] <= 0.02:
            return "forensic_silent_ai_image"
        return "mixed_weak_signals_ai_image"

    return "correct"


def feature_value(sample: AnalyzedSample, section: str, key: str) -> float:
    return safe_float(sample.report.get(section, {}).get(key), 0.0)


def format_float(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def build_misclassification_rows(
    samples: list[AnalyzedSample],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    margin_value = low_confidence_margin()
    for mode, threshold in thresholds.items():
        for sample in samples:
            kind = error_type(sample, threshold)
            if kind == "correct":
                continue
            report = sample.report
            image_info = report.get("image_info", {})
            metadata = report.get("metadata_result", {})
            forensic = report.get("forensic_result", {})
            frequency = report.get("frequency_result", {})
            evidence = report.get("evidence_summary", [])
            strategy = scene_strategy_label(sample, threshold, margin_value)
            rows.append(
                {
                    "threshold_mode": mode,
                    "threshold": f"{threshold:.2f}",
                    "filename": sample.filename,
                    "class_label": sample.class_label,
                    "ground_truth": sample.ground_truth,
                    "predicted_label": predicted_label(sample.ai_score, threshold),
                    "final_label": strategy["final_label"],
                    "confidence_level": strategy["confidence_level"],
                    "strategy_reason": strategy["strategy_reason"],
                    "error_type": kind,
                    "ai_score": format_float(sample.ai_score),
                    "margin_to_threshold": format_float(sample.ai_score - threshold),
                    "scene_tag": sample.scene_tag,
                    "scenario": sample.scenario,
                    "attribution_bucket": attribution_bucket(sample, threshold),
                    "dominant_component": dominant_component(sample.contributions),
                    "metadata_score": format_float(sample.component_scores["metadata"]),
                    "forensic_score": format_float(sample.component_scores["forensic"]),
                    "frequency_score": format_float(sample.component_scores["frequency"]),
                    "model_score": format_float(sample.component_scores["model"]),
                    "metadata_contribution": format_float(sample.contributions["metadata"]),
                    "forensic_contribution": format_float(sample.contributions["forensic"]),
                    "frequency_contribution": format_float(sample.contributions["frequency"]),
                    "model_contribution": format_float(sample.contributions["model"]),
                    "high_frequency_energy_ratio": format_float(
                        safe_float(frequency.get("high_frequency_energy_ratio"))
                    ),
                    "edge_density": format_float(safe_float(forensic.get("edge_density"))),
                    "laplacian_variance": format_float(safe_float(forensic.get("laplacian_variance"))),
                    "noise_estimate": format_float(safe_float(forensic.get("noise_estimate"))),
                    "brightness_std": format_float(safe_float(forensic.get("brightness_std"))),
                    "format": image_info.get("format") or "",
                    "width": image_info.get("width") or "",
                    "height": image_info.get("height") or "",
                    "file_size_kb": image_info.get("file_size_kb") or "",
                    "has_exif": str(bool(metadata.get("has_exif"))),
                    "software": metadata.get("software") or "",
                    "evidence_notes": " | ".join(str(item) for item in evidence),
                }
            )
    return rows


def avg(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(mean(clean), 6) if clean else None


def summarize_group(group_name: str, samples: list[AnalyzedSample], threshold: float) -> dict[str, Any]:
    formats = [str(sample.report.get("image_info", {}).get("format") or "").upper() for sample in samples]
    exif_values = [bool(sample.report.get("metadata_result", {}).get("has_exif")) for sample in samples]
    margins = [abs(sample.ai_score - threshold) for sample in samples]
    return {
        "group": group_name,
        "count": len(samples),
        "avg_ai_score": format_float(avg([sample.ai_score for sample in samples])),
        "avg_margin_abs": format_float(avg(margins)),
        "avg_metadata_score": format_float(avg([sample.component_scores["metadata"] for sample in samples])),
        "avg_forensic_score": format_float(avg([sample.component_scores["forensic"] for sample in samples])),
        "avg_frequency_score": format_float(avg([sample.component_scores["frequency"] for sample in samples])),
        "avg_metadata_contribution": format_float(avg([sample.contributions["metadata"] for sample in samples])),
        "avg_forensic_contribution": format_float(avg([sample.contributions["forensic"] for sample in samples])),
        "avg_frequency_contribution": format_float(avg([sample.contributions["frequency"] for sample in samples])),
        "avg_high_frequency_energy_ratio": format_float(
            avg([feature_value(sample, "frequency_result", "high_frequency_energy_ratio") for sample in samples])
        ),
        "avg_edge_density": format_float(
            avg([feature_value(sample, "forensic_result", "edge_density") for sample in samples])
        ),
        "avg_laplacian_variance": format_float(
            avg([feature_value(sample, "forensic_result", "laplacian_variance") for sample in samples])
        ),
        "avg_noise_estimate": format_float(
            avg([feature_value(sample, "forensic_result", "noise_estimate") for sample in samples])
        ),
        "avg_brightness_std": format_float(
            avg([feature_value(sample, "forensic_result", "brightness_std") for sample in samples])
        ),
        "exif_ratio": format_float(sum(exif_values) / len(exif_values) if exif_values else 0.0),
        "jpeg_count": sum(1 for value in formats if value in {"JPEG", "JPG"}),
        "png_count": sum(1 for value in formats if value == "PNG"),
        "webp_count": sum(1 for value in formats if value == "WEBP"),
    }


def build_summary_rows(samples: list[AnalyzedSample], threshold: float) -> list[dict[str, Any]]:
    groups: list[tuple[str, list[AnalyzedSample]]] = [
        ("all", samples),
        ("ground_truth_ai", [sample for sample in samples if sample.ground_truth == "AI-generated"]),
        ("ground_truth_real", [sample for sample in samples if sample.ground_truth == "Real"]),
        ("balanced_correct", [sample for sample in samples if error_type(sample, threshold) == "correct"]),
        ("balanced_false_positive", [sample for sample in samples if error_type(sample, threshold) == "false_positive"]),
        ("balanced_false_negative", [sample for sample in samples if error_type(sample, threshold) == "false_negative"]),
    ]
    return [summarize_group(name, group, threshold) for name, group in groups]


def metric_counts(samples: list[AnalyzedSample], threshold: float) -> dict[str, Any]:
    counts = {
        "threshold": threshold,
        "total": len(samples),
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
    }
    for sample in samples:
        kind = error_type(sample, threshold)
        if sample.ground_truth == "AI-generated" and kind == "correct":
            counts["true_positive"] += 1
        elif sample.ground_truth == "Real" and kind == "correct":
            counts["true_negative"] += 1
        elif kind == "false_positive":
            counts["false_positive"] += 1
        elif kind == "false_negative":
            counts["false_negative"] += 1
    correct = counts["true_positive"] + counts["true_negative"]
    counts["accuracy"] = round(correct / len(samples), 4) if samples else 0.0
    return counts


def bucket_counts(rows: list[dict[str, Any]], threshold_mode: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row["threshold_mode"] != threshold_mode:
            continue
        bucket = str(row["attribution_bucket"])
        counts[bucket] = counts.get(bucket, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def scenario_counts(samples: list[AnalyzedSample], threshold: float) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for sample in samples:
        scenario = sample.scenario
        result.setdefault(scenario, {"total": 0, "false_positive": 0, "false_negative": 0, "correct": 0})
        result[scenario]["total"] += 1
        result[scenario][error_type(sample, threshold)] += 1
    return dict(sorted(result.items(), key=lambda item: (-item[1]["total"], item[0])))


def scene_recommendation(total: int, fp: int, fn: int, uncertain_count: int) -> tuple[str, str]:
    if total == 0:
        return "balanced", "No samples for this scene."
    fp_rate = fp / total
    fn_rate = fn / total
    uncertain_rate = uncertain_count / total
    if fp_rate >= 0.45 and fp > fn:
        return "conservative", "Use a more conservative threshold because false positives are high for this scene."
    if fn_rate >= 0.25 and fn > fp:
        return "aggressive", "Use a more aggressive threshold because false negatives are high for this scene."
    if fp > 0 and fn > 0:
        return "uncertain_protection", "Use uncertain output because both false positives and false negatives appear in this scene."
    if uncertain_rate >= 0.50:
        return "uncertain_protection", "Use uncertain output because many samples are low-confidence or protected by scene rules."
    if fp_rate >= 0.30 and fp > fn:
        return "conservative", "Use a more conservative threshold because false positives are elevated for this scene."
    if fn_rate >= 0.18 and fn >= fp:
        return "aggressive", "Use a more aggressive threshold because false negatives are elevated for this scene."
    if fp or fn:
        return "balanced_with_uncertain_band", "Keep balanced threshold but route near-threshold samples to uncertain."
    return "balanced", "Balanced threshold is acceptable for this small scene slice."


def scene_statistics(samples: list[AnalyzedSample], threshold: float, margin: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scene_tags = sorted({sample.scene_tag for sample in samples})
    for scene_tag in scene_tags:
        group = [sample for sample in samples if sample.scene_tag == scene_tag]
        total = len(group)
        fp = sum(1 for sample in group if error_type(sample, threshold) == "false_positive")
        fn = sum(1 for sample in group if error_type(sample, threshold) == "false_negative")
        correct = sum(1 for sample in group if error_type(sample, threshold) == "correct")
        uncertain_count = sum(
            1
            for sample in group
            if scene_strategy_label(sample, threshold, margin)["final_label"] == "uncertain"
        )
        threshold_mode, action = scene_recommendation(total, fp, fn, uncertain_count)
        rows.append(
            {
                "scene_tag": scene_tag,
                "sample_count": total,
                "false_positive": fp,
                "false_negative": fn,
                "accuracy": format_float(correct / total if total else 0.0, 4),
                "avg_ai_score": format_float(avg([sample.ai_score for sample in group])),
                "recommended_threshold_mode": threshold_mode,
                "recommended_action": action,
            }
        )
    return sorted(rows, key=lambda row: (-int(row["sample_count"]), row["scene_tag"]))


def render_scene_strategy_summary(scene_rows: list[dict[str, Any]], output_dir: Path) -> str:
    high_fp = [row for row in scene_rows if int(row["false_positive"]) > 0]
    high_fp = sorted(high_fp, key=lambda row: (-int(row["false_positive"]), row["scene_tag"]))
    high_fn = [row for row in scene_rows if int(row["false_negative"]) > 0]
    high_fn = sorted(high_fn, key=lambda row: (-int(row["false_negative"]), row["scene_tag"]))
    conservative = [row for row in scene_rows if row["recommended_threshold_mode"] == "conservative"]
    aggressive = [row for row in scene_rows if row["recommended_threshold_mode"] == "aggressive"]
    uncertain = [
        row
        for row in scene_rows
        if row["recommended_threshold_mode"] in {"uncertain_protection", "balanced_with_uncertain_band"}
    ]

    lines = [
        "# Day9 Scene-Aware Strategy Summary",
        "",
        "## Scope",
        "",
        "- Scene tags are weak engineering rules based on filename keywords, EXIF, dimensions, brightness, edge density, blur/detail, noise, and format context.",
        "- Binary output is preserved as `predicted_label`; scene-aware strategy may add `final_label=uncertain` with a reason.",
        "- This is a small-scale 60-image Day9 strategy report, not production-grade scene detection.",
        "",
        "## Scene Statistics",
        "",
        "| scene_tag | samples | FP | FN | accuracy | avg ai_score | mode |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in scene_rows:
        lines.append(
            f"| {row['scene_tag']} | {row['sample_count']} | {row['false_positive']} | "
            f"{row['false_negative']} | {row['accuracy']} | {row['avg_ai_score']} | "
            f"{row['recommended_threshold_mode']} |"
        )

    lines.extend(["", "## High-FP Scenes", ""])
    lines.extend(
        [f"- {row['scene_tag']}: FP {row['false_positive']} / samples {row['sample_count']}." for row in high_fp]
        or ["- No scene has false positives at the balanced threshold."]
    )
    lines.extend(["", "## High-FN Scenes", ""])
    lines.extend(
        [f"- {row['scene_tag']}: FN {row['false_negative']} / samples {row['sample_count']}." for row in high_fn]
        or ["- No scene has false negatives at the balanced threshold."]
    )
    lines.extend(["", "## Threshold Strategy", ""])
    lines.extend(
        [f"- Conservative threshold candidate: {row['scene_tag']} ({row['recommended_action']})" for row in conservative]
        or ["- No scene clearly asks for a conservative threshold from this small slice."]
    )
    lines.extend(
        [f"- Aggressive threshold candidate: {row['scene_tag']} ({row['recommended_action']})" for row in aggressive]
        or ["- No scene clearly asks for an aggressive threshold from this small slice."]
    )
    lines.extend(
        [f"- Uncertain-protection candidate: {row['scene_tag']} ({row['recommended_action']})" for row in uncertain]
        or ["- No scene clearly needs uncertain protection beyond the global low-confidence margin."]
    )
    lines.extend(
        [
            "",
            "## Initial Scene-Aware Rules",
            "",
            "- If the image is low-light, blur-like, or heavily compressed, route it into an uncertain protection zone.",
            "- If an image has no EXIF but natural real-image features are strong, avoid directly strengthening the AI label.",
            "- If texture is over-smooth, edges are unusually uniform, and local noise is consistently low, raise AI suspicion.",
            "- If phone/camera metadata, natural noise, and plausible detail are present, lower false-positive risk.",
            "- If the score is within threshold +/- low_confidence_margin, output `final_label=uncertain` while preserving the binary `predicted_label`.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(output_dir / 'day9_scene_strategy_summary.md')}`",
            f"- `{display_path(output_dir / 'day9_misclassification_attribution.csv')}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )
    return "\n".join(lines)


def component_gap(samples: list[AnalyzedSample], key: str) -> float:
    ai_values = [sample.component_scores[key] for sample in samples if sample.ground_truth == "AI-generated"]
    real_values = [sample.component_scores[key] for sample in samples if sample.ground_truth == "Real"]
    if not ai_values or not real_values:
        return 0.0
    return round(mean(ai_values) - mean(real_values), 6)


def build_weight_suggestions(samples: list[AnalyzedSample]) -> list[str]:
    suggestions: list[str] = []
    frequency_gap = component_gap(samples, "frequency")
    forensic_gap = component_gap(samples, "forensic")
    metadata_gap = component_gap(samples, "metadata")

    if frequency_gap <= 0:
        suggestions.append(
            "frequency is supporting signal only, not a primary decision signal. In this dataset, frequency is not higher on AI samples than real samples, so increasing it would amplify false-positive risk."
        )
    else:
        suggestions.append(
            "frequency is supporting signal only; it separates AI from real only weakly and must be validated per source scenario before increasing its weight."
        )

    if forensic_gap <= 0.02:
        suggestions.append(
            "forensic/compression signals need independent corroboration before increasing AI suspicion. The current forensic rules are too sparse for AI recall."
        )
    else:
        suggestions.append(
            "Forensic features show some useful direction; tune them with per-feature bands instead of a single large weight jump."
        )

    if abs(metadata_gap) <= 0.02:
        suggestions.append(
            "missing EXIF is weak provenance evidence only. It does not separate the current AI and real sets enough to justify a larger metadata weight."
        )
    else:
        suggestions.append(
            "Metadata should remain contextual: AI software keywords can be strong, but missing EXIF alone should stay weak."
        )

    suggestions.append(
        "model_weight must stay 0 until real detector is active; the placeholder probability must not affect calibration."
    )
    return suggestions


def build_strategy_notes(scenarios: dict[str, dict[str, int]]) -> list[str]:
    notes: list[str] = []
    for scenario, counts in scenarios.items():
        fp = counts.get("false_positive", 0)
        fn = counts.get("false_negative", 0)
        total = counts.get("total", 0)
        if scenario == "web_or_social_jpeg_no_exif":
            notes.append(
                f"For {scenario}, route high-frequency-only hits to manual review or a conservative threshold; current FP/FN/total = {fp}/{fn}/{total}."
            )
        elif scenario == "png_export_no_exif":
            notes.append(
                f"For {scenario}, missing EXIF is expected, so rely more on texture and future model evidence; current FP/FN/total = {fp}/{fn}/{total}."
            )
        elif scenario == "camera_photo_with_exif":
            notes.append(
                f"For {scenario}, camera metadata should lower suspicion unless AI-tool metadata is present; current FP/FN/total = {fp}/{fn}/{total}."
            )
        else:
            notes.append(
                f"For {scenario}, keep the output as uncertain when signals conflict; current FP/FN/total = {fp}/{fn}/{total}."
            )
    return notes


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def render_report(
    samples: list[AnalyzedSample],
    misclassification_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    thresholds: dict[str, float],
    output_dir: Path,
) -> str:
    balanced = metric_counts(samples, thresholds["balanced"])
    conservative = metric_counts(samples, thresholds["conservative"])
    balanced_buckets = bucket_counts(misclassification_rows, "balanced")
    scenarios = scenario_counts(samples, thresholds["balanced"])
    weight_suggestions = build_weight_suggestions(samples)
    strategy_notes = build_strategy_notes(scenarios)

    top_fp = [
        row
        for row in misclassification_rows
        if row["threshold_mode"] == "balanced" and row["error_type"] == "false_positive"
    ]
    top_fp = sorted(top_fp, key=lambda row: abs(safe_float(row["margin_to_threshold"])), reverse=True)[:8]
    top_fn = [
        row
        for row in misclassification_rows
        if row["threshold_mode"] == "balanced" and row["error_type"] == "false_negative"
    ]
    top_fn = sorted(top_fn, key=lambda row: abs(safe_float(row["margin_to_threshold"])), reverse=True)[:8]

    lines = [
        "# Day9 Error Attribution and Strategy Report",
        "",
        "## Scope",
        "",
        "- Day9 does not change the detector, feature code, score weights, or global thresholds.",
        "- It reads Day8 predictions and per-image JSON reports, then explains where current errors come from.",
        "- Single-image entry point: `main.py` -> `run_pipeline(...)`.",
        "- Batch evaluation entry point: `scripts/evaluate_day8.py`.",
        "- Threshold scan entry point: `scripts/sweep_threshold_day8.py`.",
        "- Report output directories: single-image `outputs/reports/`, Day8 `reports/day8/`, Day9 `reports/day9/`.",
        "",
        "## Day8 Operating Points",
        "",
        "| Mode | Threshold | Accuracy | TP | TN | FP | FN |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| balanced | {balanced['threshold']:.2f} | {balanced['accuracy']:.4f} | "
            f"{balanced['true_positive']} | {balanced['true_negative']} | "
            f"{balanced['false_positive']} | {balanced['false_negative']} |"
        ),
        (
            f"| conservative | {conservative['threshold']:.2f} | {conservative['accuracy']:.4f} | "
            f"{conservative['true_positive']} | {conservative['true_negative']} | "
            f"{conservative['false_positive']} | {conservative['false_negative']} |"
        ),
        "",
        "## Misclassification Attribution",
        "",
        "Balanced-threshold error buckets:",
        "",
    ]
    if balanced_buckets:
        lines.extend(f"- {bucket}: {count}" for bucket, count in balanced_buckets.items())
    else:
        lines.append("- No balanced-threshold misclassifications found.")

    lines.extend(["", "Top balanced false positives:", ""])
    if top_fp:
        lines.extend(
            markdown_table(
                ["file", "score", "scene", "bucket", "scenario", "dominant"],
                [
                    [
                        row["filename"],
                        row["ai_score"],
                        row["scene_tag"],
                        row["attribution_bucket"],
                        row["scenario"],
                        row["dominant_component"],
                    ]
                    for row in top_fp
                ],
            )
        )
    else:
        lines.append("No false positives at the balanced threshold.")

    lines.extend(["", "Top balanced false negatives:", ""])
    if top_fn:
        lines.extend(
            markdown_table(
                ["file", "score", "scene", "bucket", "scenario", "dominant"],
                [
                    [
                        row["filename"],
                        row["ai_score"],
                        row["scene_tag"],
                        row["attribution_bucket"],
                        row["scenario"],
                        row["dominant_component"],
                    ]
                    for row in top_fn
                ],
            )
        )
    else:
        lines.append("No false negatives at the balanced threshold.")

    lines.extend(
        [
            "",
            "## Feature Summary",
            "",
            "| Group | Count | Avg score | Avg metadata | Avg forensic | Avg frequency | EXIF ratio | JPEG | PNG |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['group']} | {row['count']} | {row['avg_ai_score']} | "
            f"{row['avg_metadata_score']} | {row['avg_forensic_score']} | "
            f"{row['avg_frequency_score']} | {row['exif_ratio']} | "
            f"{row['jpeg_count']} | {row['png_count']} |"
        )

    lines.extend(
        [
            "",
            "## Dataset Bias / Format Confound Warning",
            "",
            "- Current AI samples are PNG exports without EXIF.",
            "- Current real samples are JPEG images, some with EXIF.",
            "- Current threshold and weight conclusions may partly reflect file format, compression, and provenance differences rather than pure AI-vs-real visual differences.",
            "- Therefore, Day9 results are diagnostic evidence only and should not be used as production calibration.",
        ]
    )
    lines.extend(["", "## Weight Optimization Suggestions", ""])
    lines.extend(f"- {item}" for item in weight_suggestions)
    lines.extend(["", "## Scenario Strategy", ""])
    lines.extend(f"- {item}" for item in strategy_notes)
    lines.extend(
        [
            "",
            "## Follow-Up Validation Notes",
            "",
            "- Add scenario-aware review labels such as `likely_ai`, `likely_real`, and `needs_review` without replacing the raw score.",
            "- Add per-feature calibration tables for frequency, edge density, noise, and Laplacian variance by image source type.",
            "- Keep the current single-image and batch entry points stable while testing any candidate weight changes behind a separate analysis script.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(output_dir / 'day9_misclassification_attribution.csv')}`",
            f"- `{display_path(output_dir / 'day9_feature_summary_by_group.csv')}`",
            f"- `{display_path(output_dir / 'day9_analysis.json')}`",
            f"- `{display_path(output_dir / 'day9_report.md')}`",
            f"- `{display_path(output_dir / 'day9_scene_strategy_summary.md')}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(
    predictions_csv: Path,
    image_report_dir: Path,
    output_dir: Path,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    predictions_csv = resolve_path(predictions_csv)
    image_report_dir = resolve_path(image_report_dir)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions = read_predictions(predictions_csv)
    samples = analyze_samples(predictions, image_report_dir)
    misclassification_rows = build_misclassification_rows(samples, thresholds)
    summary_rows = build_summary_rows(samples, thresholds["balanced"])
    margin_value = low_confidence_margin()
    scene_rows = scene_statistics(samples, thresholds["balanced"], margin_value)

    attribution_csv = output_dir / "day9_misclassification_attribution.csv"
    summary_csv = output_dir / "day9_feature_summary_by_group.csv"
    analysis_json = output_dir / "day9_analysis.json"
    report_md = output_dir / "day9_report.md"
    scene_report_md = output_dir / "day9_scene_strategy_summary.md"

    write_csv(attribution_csv, misclassification_rows, MISCLASSIFICATION_FIELDS)
    write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "inputs": {
            "predictions_csv": str(predictions_csv),
            "image_report_dir": str(image_report_dir),
        },
        "thresholds": thresholds,
        "metrics": {name: metric_counts(samples, threshold) for name, threshold in thresholds.items()},
        "balanced_error_buckets": bucket_counts(misclassification_rows, "balanced"),
        "balanced_scenarios": scenario_counts(samples, thresholds["balanced"]),
        "scene_statistics": scene_rows,
        "low_confidence_margin": margin_value,
        "weight_suggestions": build_weight_suggestions(samples),
        "summary_rows": summary_rows,
        "outputs": {
            "misclassification_attribution_csv": str(attribution_csv),
            "feature_summary_csv": str(summary_csv),
            "analysis_json": str(analysis_json),
            "markdown_report": str(report_md),
            "scene_strategy_summary": str(scene_report_md),
        },
    }
    analysis_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_md.write_text(
        render_report(samples, misclassification_rows, summary_rows, thresholds, output_dir),
        encoding="utf-8",
    )
    scene_report_md.write_text(render_scene_strategy_summary(scene_rows, output_dir), encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    thresholds = {
        "balanced": args.balanced_threshold,
        "conservative": args.conservative_threshold,
    }
    try:
        result = run(args.predictions, args.image_report_dir, args.output_dir, thresholds)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Day9 analysis failed: {exc}", file=sys.stderr)
        return 1

    balanced = result["metrics"]["balanced"]
    conservative = result["metrics"]["conservative"]
    print(
        f"Balanced threshold {balanced['threshold']:.2f}: accuracy={balanced['accuracy']:.4f}, "
        f"FP={balanced['false_positive']}, FN={balanced['false_negative']}"
    )
    print(
        f"Conservative threshold {conservative['threshold']:.2f}: accuracy={conservative['accuracy']:.4f}, "
        f"FP={conservative['false_positive']}, FN={conservative['false_negative']}"
    )
    print(f"Report: {display_path(Path(result['outputs']['markdown_report']))}")
    print(f"Scene strategy: {display_path(Path(result['outputs']['scene_strategy_summary']))}")
    print(f"Attribution CSV: {display_path(Path(result['outputs']['misclassification_attribution_csv']))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
