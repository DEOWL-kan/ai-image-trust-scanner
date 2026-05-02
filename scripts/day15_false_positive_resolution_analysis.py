from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from PIL import Image, ImageOps, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import binary_label_at_threshold, load_decision_policy  # noqa: E402
from core.forensic_analyzer import analyze_forensics  # noqa: E402
from core.frequency_analyzer import analyze_frequency  # noqa: E402
from core.metadata_analyzer import analyze_metadata  # noqa: E402
from core.model_detector import detect_with_model  # noqa: E402
from core.score_fusion import fuse_scores, load_detector_weight_config  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VALID_LABELS = {"ai", "real"}
VARIANT_TARGETS = (512, 768, 1024)
MAIN_DATASET_ROLES = {"raw_source", "paired_format", "legacy"}
SEMANTIC_CATEGORIES = [
    "food_retail",
    "indoor_home",
    "lowlight_weather",
    "nature_travel",
    "object_closeup",
    "outdoor_street",
    "people_partial",
]

DEFAULT_TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_TMP_ROOT = PROJECT_ROOT / ".tmp" / "day15_resolution_variants"

ALL_PREDICTIONS_CSV = "day15_all_predictions.csv"
FALSE_POSITIVE_SAMPLES_CSV = "day15_false_positive_samples.csv"
FALSE_POSITIVE_CLUSTER_SUMMARY_CSV = "day15_false_positive_cluster_summary.csv"
RESOLUTION_VARIANT_PREDICTIONS_CSV = "day15_resolution_variant_predictions.csv"
RESOLUTION_FLIP_SAMPLES_CSV = "day15_resolution_flip_samples.csv"
RESOLUTION_FLIP_SUMMARY_CSV = "day15_resolution_flip_summary.csv"
FP_RESOLUTION_INTERSECTION_CSV = "day15_fp_resolution_intersection.csv"
REPORT_MD = "day15_false_positive_resolution_report.md"
RESOLUTION_CONTROL_APPENDIX_CSV = "day15_resolution_control_appendix.csv"

ALL_PREDICTION_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "dataset_role",
    "semantic_category",
    "transform_group",
    "is_main_dataset",
    "base_id",
    "filename",
    "extension",
    "file_size_kb",
    "width",
    "height",
    "aspect_ratio",
    "megapixels",
    "image_mode",
    "has_exif",
    "difficulty",
    "score",
    "predicted_label",
    "final_label",
    "is_uncertain",
    "threshold_used",
    "detector_config_name",
    "raw_false_positive",
    "final_false_positive",
    "false_positive",
    "status",
    "error_message",
]

FP_SAMPLE_FIELDS = [
    "image_path",
    "category",
    "semantic_category",
    "transform_group",
    "dataset_role",
    "extension",
    "width",
    "height",
    "has_exif",
    "score",
    "predicted_label",
    "final_label",
    "raw_false_positive",
    "final_false_positive",
    "difficulty",
    "resolution_bucket",
    "score_bucket",
]

FP_CLUSTER_FIELDS = [
    "analysis_type",
    "group",
    "total_real",
    "false_positive_count",
    "false_positive_rate",
    "raw_false_positive_count",
    "raw_false_positive_rate",
    "final_false_positive_count",
    "final_false_positive_rate",
    "avg_score",
    "median_score",
    "max_score",
]

VARIANT_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "dataset_role",
    "semantic_category",
    "transform_group",
    "extension",
    "original_width",
    "original_height",
    "variant_name",
    "variant_width",
    "variant_height",
    "score",
    "predicted_label",
    "final_label",
    "is_uncertain",
    "threshold_used",
    "status",
    "error_message",
    "variant_path",
]

FLIP_SAMPLE_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "dataset_role",
    "semantic_category",
    "transform_group",
    "extension",
    "original_size",
    "original_label",
    "resized_512_label",
    "resized_768_label",
    "resized_1024_label",
    "score_original",
    "score_512",
    "score_768",
    "score_1024",
    "score_min",
    "score_max",
    "score_delta",
    "flip_type",
    "original_resolution_bucket",
]

FLIP_SUMMARY_FIELDS = [
    "analysis_type",
    "group",
    "total_count",
    "flip_count",
    "flip_rate",
    "avg_score_delta",
    "median_score_delta",
    "max_score_delta",
]

INTERSECTION_FIELDS = [
    "category",
    "real_total",
    "real_fp_count",
    "real_fp_rate",
    "real_flip_count",
    "real_flip_rate",
    "fp_and_flip_count",
    "fp_and_flip_rate",
    "avg_score_delta_all_real",
    "avg_score_delta_fp_real",
    "avg_score_delta_non_fp_real",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day15 false-positive cluster and resolution-flip root cause analysis."
    )
    parser.add_argument(
        "--test-root",
        type=Path,
        default=DEFAULT_TEST_ROOT,
        help="Root recursively scanned for test images. Default: data/test_images",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory for Day15 outputs. Default: reports",
    )
    parser.add_argument(
        "--tmp-root",
        type=Path,
        default=DEFAULT_TMP_ROOT,
        help="Temporary directory for resized variants. Default: .tmp/day15_resolution_variants",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def normalized_path_key(value: str | Path) -> str:
    return str(value).replace("\\", "/").lower()


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def fmt_float(value: Any, digits: int = 6) -> str:
    number = safe_float(value)
    return "" if number is None else f"{number:.{digits}f}"


def bool_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "true" if value else "false"


def normalized_extension(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error):
        return []


def label_from_folder_name(folder_name: str) -> str | None:
    lowered = folder_name.lower()
    if lowered.startswith("ai_") or lowered.endswith("_ai"):
        return "ai"
    if lowered.startswith("real_") or lowered.endswith("_real"):
        return "real"
    return None


def label_from_filename(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.startswith("ai_"):
        return "ai"
    if lowered.startswith("real_"):
        return "real"
    return None


def dataset_role_for(image_path: Path, test_root: Path) -> str:
    try:
        parts = [part.lower() for part in image_path.relative_to(test_root).parts]
    except ValueError:
        parts = [part.lower() for part in image_path.parts]

    joined = "/".join(parts)
    if "day14_expansion/raw" in joined:
        return "raw_source"
    if "day14_expansion/paired_format" in joined:
        return "paired_format"
    if "day14_expansion/resolution_control" in joined:
        return "resolution_control"
    if "legacy" in parts:
        return "legacy"
    return "other"


def semantic_category_for(image_path: Path, test_root: Path) -> str:
    try:
        relative_parts = image_path.relative_to(test_root).parts
    except ValueError:
        relative_parts = image_path.parts
    lowered_parts = [part.lower() for part in relative_parts]

    for label in ("ai", "real"):
        marker = ("raw", label)
        for index in range(0, max(0, len(lowered_parts) - 2)):
            if tuple(lowered_parts[index:index + 2]) == marker and index + 2 < len(relative_parts) - 1:
                category = lowered_parts[index + 2]
                if category in SEMANTIC_CATEGORIES:
                    return category

    filename_text = image_path.stem.lower()
    path_text = "/".join(lowered_parts)
    for category in SEMANTIC_CATEGORIES:
        if category in filename_text:
            return category
    for category in SEMANTIC_CATEGORIES:
        if f"/{category}/" in f"/{path_text}/":
            return category
    return "unknown"


def transform_group_for(image_path: Path, test_root: Path, dataset_role: str) -> str:
    try:
        relative_parts = image_path.relative_to(test_root).parts
    except ValueError:
        relative_parts = image_path.parts
    lowered_parts = [part.lower() for part in relative_parts]
    stem = image_path.stem.lower()

    if dataset_role == "raw_source":
        return "raw"
    if dataset_role == "legacy":
        return "legacy"
    if dataset_role == "paired_format":
        for part in lowered_parts:
            if part in {"ai_jpg", "ai_png", "real_jpg", "real_png"}:
                return part
    if dataset_role == "resolution_control":
        for part in lowered_parts:
            if part in {"long_512", "long_768", "long_1024"}:
                return part
        for target in (512, 768, 1024):
            if f"long{target}" in stem or f"long_{target}" in stem:
                return f"long_{target}"
    return "other"


def base_id_for(image_path: Path) -> str:
    stem = image_path.stem.lower()
    stem = re.sub(r"^(ai|real)_", "", stem)
    stem = re.sub(r"_(jpg_q95|png)(_long_?\d+)?$", "", stem)
    stem = re.sub(r"_(jpg_q95|png)$", "", stem)
    stem = re.sub(r"_native$", "", stem)
    stem = re.sub(r"_long_?(512|768|1024)$", "", stem)
    return stem


def infer_label_and_category(image_path: Path, test_root: Path) -> tuple[str, str]:
    try:
        relative_parts = image_path.relative_to(test_root).parts
    except ValueError:
        relative_parts = image_path.parts

    lowered_parts = [part.lower() for part in relative_parts]
    label_index = next(
        (index for index, part in enumerate(lowered_parts) if part in VALID_LABELS),
        None,
    )
    if label_index is not None:
        true_label = lowered_parts[label_index]
        if label_index + 1 < len(relative_parts) - 1:
            category = relative_parts[label_index + 1]
        elif label_index - 1 >= 0:
            category = relative_parts[label_index - 1]
        else:
            category = "unknown"
        return true_label, category

    parent_parts = relative_parts[:-1]
    for folder_name in parent_parts:
        inferred = label_from_folder_name(folder_name)
        if inferred:
            return inferred, image_path.parent.name

    filename_label = label_from_filename(image_path.name)
    if filename_label:
        return filename_label, image_path.parent.name

    return "unknown", image_path.parent.name or "unknown"


def collect_images(test_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not test_root.exists():
        return items

    for path in sorted(test_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        true_label, category = infer_label_and_category(path, test_root)
        dataset_role = dataset_role_for(path, test_root)
        semantic_category = semantic_category_for(path, test_root)
        transform_group = transform_group_for(path, test_root, dataset_role)
        items.append(
            {
                "path": path,
                "true_label": true_label,
                "category": category,
                "dataset_role": dataset_role,
                "semantic_category": semantic_category,
                "transform_group": transform_group,
                "is_main_dataset": dataset_role in MAIN_DATASET_ROLES,
                "base_id": base_id_for(path),
            }
        )
    return items


def print_directory_tree(root: Path, max_depth: int = 3, max_entries: int = 200) -> None:
    print(f"Directory tree under {display_path(root)} (first {max_depth} levels):")
    if not root.exists():
        print("  <missing>")
        return

    printed = 0
    for path in sorted(root.rglob("*")):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        depth = len(relative.parts)
        if depth > max_depth:
            continue
        indent = "  " * depth
        marker = "/" if path.is_dir() else ""
        print(f"{indent}{path.name}{marker}")
        printed += 1
        if printed >= max_entries:
            print(f"  ... truncated after {max_entries} entries")
            break


def print_scan_debug(project_root: Path, test_root: Path, images: list[dict[str, Any]]) -> None:
    print(f"project_root: {project_root}")
    print(f"test_root: {test_root}")
    print(f"test_root exists: {test_root.exists()}")
    print(f"scanned image count: {len(images)}")
    print("first 10 image paths:")
    for item in images[:10]:
        print(f"  {display_path(item['path'])}")
    if not images:
        print("  <none>")
    print(f"true_label distribution: {dict(sorted(Counter(item['true_label'] for item in images).items()))}")
    print(f"dataset_role distribution: {dict(sorted(Counter(item['dataset_role'] for item in images).items()))}")
    print(
        "category distribution top 10: "
        f"{dict(Counter(item['category'] for item in images).most_common(10))}"
    )
    print(
        "semantic_category distribution top 10: "
        f"{dict(Counter(item['semantic_category'] for item in images).most_common(10))}"
    )


def load_difficulty_lookup(test_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    difficulty_by_path: dict[str, str] = {}
    difficulty_by_filename: dict[str, str] = {}
    difficulty_columns = [
        "difficulty",
        "source_difficulty",
        "variant_difficulty",
        "label_difficulty",
        "manual_difficulty",
    ]
    path_columns = [
        "image_path",
        "source_path",
        "path",
        "current_path",
        "original_path",
        "variant_path",
    ]
    filename_columns = [
        "filename",
        "file_name",
        "current_filename",
        "original_file",
        "image_file",
    ]

    for csv_path in sorted(test_root.rglob("*.csv")):
        for row in read_csv(csv_path):
            difficulty = ""
            for column in difficulty_columns:
                value = str(row.get(column, "")).strip().lower()
                if value in {"easy", "medium", "hard"}:
                    difficulty = value
                    break
            if not difficulty:
                continue
            for column in path_columns:
                value = str(row.get(column, "")).strip()
                if value:
                    difficulty_by_path[normalized_path_key(value)] = difficulty
                    difficulty_by_path[normalized_path_key(PROJECT_ROOT / value)] = difficulty
            for column in filename_columns:
                value = str(row.get(column, "")).strip()
                if value:
                    difficulty_by_filename[value.lower()] = difficulty

    return difficulty_by_path, difficulty_by_filename


def difficulty_from_text(path: Path, category: str) -> str:
    text = " ".join([path.stem, category, *[part for part in path.parts]])
    tokens = {
        token.lower()
        for token in "".join(char if char.isalnum() else " " for char in text).split()
    }
    for difficulty in ("easy", "medium", "hard"):
        if difficulty in tokens:
            return difficulty
    return "unknown"


def difficulty_for(
    path: Path,
    category: str,
    difficulty_by_path: dict[str, str],
    difficulty_by_filename: dict[str, str],
) -> str:
    keys = [
        normalized_path_key(path),
        normalized_path_key(path.resolve()),
        normalized_path_key(display_path(path)),
    ]
    for key in keys:
        if key in difficulty_by_path:
            return difficulty_by_path[key]
    filename = path.name.lower()
    if filename in difficulty_by_filename:
        return difficulty_by_filename[filename]
    return difficulty_from_text(path, category)


def image_basic_info(path: Path) -> dict[str, Any]:
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = None

    try:
        with Image.open(path) as opened:
            exif = opened.getexif()
            has_exif: bool | None = bool(exif)
            image = ImageOps.exif_transpose(opened)
            width, height = image.size
            mode = image.mode
    except (UnidentifiedImageError, OSError, ValueError):
        return {
            "file_size_kb": "" if file_size is None else round(file_size / 1024, 2),
            "width": "",
            "height": "",
            "aspect_ratio": "",
            "megapixels": "",
            "image_mode": "",
            "has_exif": "unknown",
            "open_error": "image_open_failed",
        }
    except Exception as exc:
        return {
            "file_size_kb": "" if file_size is None else round(file_size / 1024, 2),
            "width": "",
            "height": "",
            "aspect_ratio": "",
            "megapixels": "",
            "image_mode": "",
            "has_exif": "unknown",
            "open_error": str(exc),
        }

    aspect_ratio = round(width / height, 6) if height else ""
    megapixels = round((width * height) / 1_000_000, 6) if width and height else ""
    return {
        "file_size_kb": "" if file_size is None else round(file_size / 1024, 2),
        "width": int(width),
        "height": int(height),
        "aspect_ratio": aspect_ratio,
        "megapixels": megapixels,
        "image_mode": mode,
        "has_exif": bool_text(has_exif),
        "open_error": "",
    }


def resolution_bucket(width: Any, height: Any) -> str:
    w = safe_float(width)
    h = safe_float(height)
    if w is None or h is None:
        return "unknown"
    max_side = max(w, h)
    if max_side < 768:
        return "small"
    if max_side < 1280:
        return "medium"
    if max_side < 2048:
        return "large"
    return "xlarge"


def score_bucket(score: Any) -> str:
    value = safe_float(score)
    if value is None:
        return "unknown"
    if value < 0.10:
        return "below_0.10"
    if value < 0.15:
        return "0.10_0.15"
    if value < 0.18:
        return "0.15_0.18"
    if value < 0.25:
        return "0.18_0.25"
    return "above_0.25"


def exif_group(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"true", "has_exif", "yes", "1"}:
        return "has_exif"
    if text in {"false", "no_exif", "no", "0"}:
        return "no_exif"
    return "unknown_exif"


def run_detector(path: Path, threshold: float, detector_config_name: str) -> dict[str, Any]:
    try:
        metadata_result = analyze_metadata(path)
        forensic_result = analyze_forensics(path)
        frequency_result = analyze_frequency(path)
        model_result = detect_with_model(path)
        final_result = fuse_scores(
            metadata_result=metadata_result,
            forensic_result=forensic_result,
            frequency_result=frequency_result,
            model_result=model_result,
        )
    except Exception as exc:
        return {
            "score": "",
            "predicted_label": "",
            "final_label": "",
            "is_uncertain": "unknown",
            "threshold_used": fmt_float(threshold),
            "detector_config_name": detector_config_name,
            "status": "error",
            "error_message": str(exc),
        }

    score = safe_float(final_result.get("final_score", final_result.get("raw_score")))
    result_threshold = safe_float(final_result.get("threshold"), threshold) or threshold
    predicted = (
        str(final_result.get("binary_label_at_threshold") or "")
        if score is not None
        else ""
    )
    if score is not None and not predicted:
        predicted = binary_label_at_threshold(score, result_threshold)
    final_label = str(final_result.get("final_label") or "")
    is_uncertain = final_label == "uncertain"

    return {
        "score": "" if score is None else round(score, 6),
        "predicted_label": predicted,
        "final_label": final_label,
        "is_uncertain": bool_text(is_uncertain),
        "threshold_used": fmt_float(result_threshold),
        "detector_config_name": detector_config_name,
        "status": "success" if score is not None and final_label else "error",
        "error_message": "" if score is not None and final_label else "No score or final_label returned.",
    }


def evaluate_originals(
    images: list[dict[str, Any]],
    threshold: float,
    detector_config_name: str,
    difficulty_by_path: dict[str, str],
    difficulty_by_filename: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started = time.time()
    for index, item in enumerate(images, 1):
        path = item["path"]
        info = image_basic_info(path)
        detection = run_detector(path, threshold, detector_config_name)
        true_label = item["true_label"]
        predicted = detection["predicted_label"]
        final_label = detection["final_label"]
        raw_fp = true_label == "real" and predicted == "ai"
        final_fp = true_label == "real" and final_label == "ai"
        row = {
            "image_path": display_path(path),
            "true_label": true_label,
            "category": item["category"],
            "dataset_role": item["dataset_role"],
            "semantic_category": item["semantic_category"],
            "transform_group": item["transform_group"],
            "is_main_dataset": bool_text(bool(item["is_main_dataset"])),
            "base_id": item["base_id"],
            "filename": path.name,
            "extension": normalized_extension(path),
            "difficulty": difficulty_for(
                path,
                item["category"],
                difficulty_by_path,
                difficulty_by_filename,
            ),
            **info,
            **detection,
            "raw_false_positive": bool_text(raw_fp),
            "final_false_positive": bool_text(final_fp),
            "false_positive": bool_text(raw_fp or final_fp),
        }
        rows.append(row)
        if index % 50 == 0 or index == len(images):
            elapsed = time.time() - started
            print(f"Original evaluation: {index}/{len(images)} images in {elapsed:.1f}s", flush=True)
    return rows


def numeric_scores(rows: Iterable[dict[str, Any]]) -> list[float]:
    values = [safe_float(row.get("score")) for row in rows]
    return [float(value) for value in values if value is not None]


def cluster_summary(rows: list[dict[str, Any]], analysis_type: str, key_fn: Any) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("true_label") != "real":
            continue
        grouped[str(key_fn(row) or "unknown")].append(row)

    output: list[dict[str, Any]] = []
    for group, items in sorted(grouped.items()):
        scores = numeric_scores(items)
        fp_count = sum(1 for item in items if item.get("false_positive") == "true")
        raw_fp_count = sum(1 for item in items if item.get("raw_false_positive") == "true")
        final_fp_count = sum(1 for item in items if item.get("final_false_positive") == "true")
        total = len(items)
        output.append(
            {
                "analysis_type": analysis_type,
                "group": group,
                "total_real": total,
                "false_positive_count": fp_count,
                "false_positive_rate": fmt_float(safe_ratio(fp_count, total)),
                "raw_false_positive_count": raw_fp_count,
                "raw_false_positive_rate": fmt_float(safe_ratio(raw_fp_count, total)),
                "final_false_positive_count": final_fp_count,
                "final_false_positive_rate": fmt_float(safe_ratio(final_fp_count, total)),
                "avg_score": fmt_float(mean(scores) if scores else None),
                "median_score": fmt_float(median(scores) if scores else None),
                "max_score": fmt_float(max(scores) if scores else None),
            }
        )
    return output


def false_positive_cluster_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    summaries.extend(cluster_summary(rows, "semantic_category", lambda row: row.get("semantic_category")))
    summaries.extend(cluster_summary(rows, "transform_group", lambda row: row.get("transform_group")))
    summaries.extend(cluster_summary(rows, "dataset_role", lambda row: row.get("dataset_role")))
    summaries.extend(cluster_summary(rows, "category", lambda row: row.get("category")))
    summaries.extend(cluster_summary(rows, "extension", lambda row: row.get("extension")))
    summaries.extend(cluster_summary(rows, "exif", lambda row: exif_group(row.get("has_exif"))))
    summaries.extend(
        cluster_summary(
            rows,
            "resolution_bucket",
            lambda row: resolution_bucket(row.get("width"), row.get("height")),
        )
    )
    summaries.extend(cluster_summary(rows, "score_bucket", lambda row: score_bucket(row.get("score"))))
    summaries.extend(cluster_summary(rows, "difficulty", lambda row: row.get("difficulty")))
    return summaries


def false_positive_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row in rows:
        if row.get("true_label") != "real" or row.get("false_positive") != "true":
            continue
        samples.append(
            {
                "image_path": row.get("image_path", ""),
                "category": row.get("category", ""),
                "semantic_category": row.get("semantic_category", ""),
                "transform_group": row.get("transform_group", ""),
                "dataset_role": row.get("dataset_role", ""),
                "extension": row.get("extension", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "has_exif": row.get("has_exif", "unknown"),
                "score": row.get("score", ""),
                "predicted_label": row.get("predicted_label", ""),
                "final_label": row.get("final_label", ""),
                "raw_false_positive": row.get("raw_false_positive", ""),
                "final_false_positive": row.get("final_false_positive", ""),
                "difficulty": row.get("difficulty", "unknown"),
                "resolution_bucket": resolution_bucket(row.get("width"), row.get("height")),
                "score_bucket": score_bucket(row.get("score")),
            }
        )
    return sorted(samples, key=lambda row: safe_float(row.get("score"), -1.0) or -1.0, reverse=True)


def target_size(width: int, height: int, target_long_edge: int) -> tuple[int, int]:
    long_edge = max(width, height)
    if long_edge <= 0:
        raise ValueError("Invalid image size.")
    scale = target_long_edge / long_edge
    return max(1, round(width * scale)), max(1, round(height * scale))


def variant_path_for(source: Path, true_label: str, category: str, target: int, tmp_root: Path) -> Path:
    digest = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:12]
    suffix = source.suffix.lower()
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source.stem)
    return tmp_root / true_label / category / f"{safe_stem}__{digest}__resized_{target}{suffix}"


def save_resized_variant(source: Path, destination: Path, target: int) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        width, height = image.size
        new_size = target_size(width, height, target)
        resampling_source = getattr(Image, "Resampling", Image)
        resized = image.resize(new_size, getattr(resampling_source, "LANCZOS"))
        suffix = destination.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            resized.convert("RGB").save(destination, format="JPEG", quality=95, optimize=True)
        elif suffix == ".png":
            resized.save(destination, format="PNG", optimize=True)
        elif suffix == ".webp":
            resized.convert("RGB").save(destination, format="WEBP", quality=95, method=6)
        elif suffix == ".bmp":
            resized.convert("RGB").save(destination, format="BMP")
        else:
            raise ValueError(f"Unsupported variant extension: {suffix}")
    return new_size


def variant_detection_row(
    original: dict[str, Any],
    source_path: Path,
    variant_name: str,
    variant_path: Path,
    variant_width: int,
    variant_height: int,
    threshold: float,
    detector_config_name: str,
) -> dict[str, Any]:
    detection = run_detector(variant_path, threshold, detector_config_name)
    return {
        "image_path": display_path(source_path),
        "true_label": original["true_label"],
        "category": original["category"],
        "dataset_role": original.get("dataset_role", ""),
        "semantic_category": original.get("semantic_category", ""),
        "transform_group": original.get("transform_group", ""),
        "extension": normalized_extension(source_path),
        "original_width": original.get("width", ""),
        "original_height": original.get("height", ""),
        "variant_name": variant_name,
        "variant_width": variant_width,
        "variant_height": variant_height,
        "variant_path": display_path(variant_path),
        **detection,
    }


def evaluate_resolution_variants(
    images: list[dict[str, Any]],
    original_rows: list[dict[str, Any]],
    threshold: float,
    detector_config_name: str,
    tmp_root: Path,
) -> list[dict[str, Any]]:
    original_by_path = {row["image_path"]: row for row in original_rows}
    rows: list[dict[str, Any]] = []
    started = time.time()
    for index, item in enumerate(images, 1):
        source = item["path"]
        original = original_by_path.get(display_path(source), {})
        width = safe_float(original.get("width"))
        height = safe_float(original.get("height"))
        if width is None or height is None:
            basic = image_basic_info(source)
            width = safe_float(basic.get("width"))
            height = safe_float(basic.get("height"))

        if width is None or height is None:
            base = {
                "true_label": item["true_label"],
                "category": item["category"],
                "dataset_role": item["dataset_role"],
                "semantic_category": item["semantic_category"],
                "transform_group": item["transform_group"],
                "width": "",
                "height": "",
            }
            rows.append(
                {
                    "image_path": display_path(source),
                    "true_label": item["true_label"],
                    "category": item["category"],
                    "dataset_role": item["dataset_role"],
                    "semantic_category": item["semantic_category"],
                    "transform_group": item["transform_group"],
                    "extension": normalized_extension(source),
                    "original_width": "",
                    "original_height": "",
                    "variant_name": "original",
                    "variant_width": "",
                    "variant_height": "",
                    "score": "",
                    "predicted_label": "",
                    "final_label": "",
                    "is_uncertain": "unknown",
                    "threshold_used": fmt_float(threshold),
                    "status": "error",
                    "error_message": "Could not read original image dimensions.",
                    "variant_path": display_path(source),
                }
            )
            for target in VARIANT_TARGETS:
                rows.append(
                    {
                        "image_path": display_path(source),
                        "true_label": item["true_label"],
                        "category": item["category"],
                        "dataset_role": item["dataset_role"],
                        "semantic_category": item["semantic_category"],
                        "transform_group": item["transform_group"],
                        "extension": normalized_extension(source),
                        "original_width": "",
                        "original_height": "",
                        "variant_name": f"resized_{target}",
                        "variant_width": "",
                        "variant_height": "",
                        "score": "",
                        "predicted_label": "",
                        "final_label": "",
                        "is_uncertain": "unknown",
                        "threshold_used": fmt_float(threshold),
                        "status": "error",
                        "error_message": "Skipped because original image dimensions were unavailable.",
                        "variant_path": "",
                    }
                )
            continue

        original_meta = {
            "true_label": item["true_label"],
            "category": item["category"],
            "dataset_role": item["dataset_role"],
            "semantic_category": item["semantic_category"],
            "transform_group": item["transform_group"],
            "width": int(width),
            "height": int(height),
        }
        rows.append(
            variant_detection_row(
                original_meta,
                source,
                "original",
                source,
                int(width),
                int(height),
                threshold,
                detector_config_name,
            )
        )

        for target in VARIANT_TARGETS:
            destination = variant_path_for(source, item["true_label"], item["category"], target, tmp_root)
            try:
                new_width, new_height = save_resized_variant(source, destination, target)
                rows.append(
                    variant_detection_row(
                        original_meta,
                        source,
                        f"resized_{target}",
                        destination,
                        new_width,
                        new_height,
                        threshold,
                        detector_config_name,
                    )
                )
            except Exception as exc:
                rows.append(
                    {
                        "image_path": display_path(source),
                        "true_label": item["true_label"],
                        "category": item["category"],
                        "dataset_role": item["dataset_role"],
                        "semantic_category": item["semantic_category"],
                        "transform_group": item["transform_group"],
                        "extension": normalized_extension(source),
                        "original_width": int(width),
                        "original_height": int(height),
                        "variant_name": f"resized_{target}",
                        "variant_width": "",
                        "variant_height": "",
                        "score": "",
                        "predicted_label": "",
                        "final_label": "",
                        "is_uncertain": "unknown",
                        "threshold_used": fmt_float(threshold),
                        "status": "error",
                        "error_message": str(exc),
                        "variant_path": display_path(destination),
                    }
                )

        if index % 25 == 0 or index == len(images):
            elapsed = time.time() - started
            print(f"Resolution variants: {index}/{len(images)} images in {elapsed:.1f}s", flush=True)
    return rows


def flip_type_for(original_label: str, resized_labels: list[str]) -> str:
    transitions = [(original_label, label) for label in resized_labels if label and label != original_label]
    priority = [
        ("real", "ai", "real_to_ai_after_resize"),
        ("ai", "real", "ai_to_real_after_resize"),
        ("ai", "uncertain", "ai_to_uncertain_after_resize"),
        ("real", "uncertain", "real_to_uncertain_after_resize"),
        ("uncertain", "ai", "uncertain_to_ai_after_resize"),
        ("uncertain", "real", "uncertain_to_real_after_resize"),
    ]
    for source, target, name in priority:
        if (source, target) in transitions:
            return name
    return "other" if transitions else "none"


def build_flip_samples(variant_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in variant_rows:
        grouped[row.get("image_path", "")].append(row)

    all_image_summaries: list[dict[str, Any]] = []
    flip_samples: list[dict[str, Any]] = []
    for image_path, items in sorted(grouped.items()):
        by_variant = {row.get("variant_name", ""): row for row in items}
        original = by_variant.get("original", {})
        original_label = str(original.get("final_label", ""))
        labels = {
            "resized_512": str(by_variant.get("resized_512", {}).get("final_label", "")),
            "resized_768": str(by_variant.get("resized_768", {}).get("final_label", "")),
            "resized_1024": str(by_variant.get("resized_1024", {}).get("final_label", "")),
        }
        score_map = {
            "original": safe_float(original.get("score")),
            "512": safe_float(by_variant.get("resized_512", {}).get("score")),
            "768": safe_float(by_variant.get("resized_768", {}).get("score")),
            "1024": safe_float(by_variant.get("resized_1024", {}).get("score")),
        }
        scores = [score for score in score_map.values() if score is not None]
        score_min = min(scores) if scores else None
        score_max = max(scores) if scores else None
        score_delta = (score_max - score_min) if score_min is not None and score_max is not None else None
        resized_labels = list(labels.values())
        has_flip = bool(original_label and any(label and label != original_label for label in resized_labels))
        flip_type = flip_type_for(original_label, resized_labels)
        original_width = original.get("original_width", "")
        original_height = original.get("original_height", "")
        summary = {
            "image_path": image_path,
            "true_label": original.get("true_label", ""),
            "category": original.get("category", ""),
            "dataset_role": original.get("dataset_role", ""),
            "semantic_category": original.get("semantic_category", ""),
            "transform_group": original.get("transform_group", ""),
            "extension": original.get("extension", ""),
            "original_size": f"{original_width}x{original_height}" if original_width and original_height else "",
            "original_label": original_label,
            "resized_512_label": labels["resized_512"],
            "resized_768_label": labels["resized_768"],
            "resized_1024_label": labels["resized_1024"],
            "score_original": fmt_float(score_map["original"]),
            "score_512": fmt_float(score_map["512"]),
            "score_768": fmt_float(score_map["768"]),
            "score_1024": fmt_float(score_map["1024"]),
            "score_min": fmt_float(score_min),
            "score_max": fmt_float(score_max),
            "score_delta": fmt_float(score_delta),
            "flip_type": flip_type,
            "has_resolution_flip": bool_text(has_flip),
            "original_resolution_bucket": resolution_bucket(original_width, original_height),
        }
        all_image_summaries.append(summary)
        if has_flip:
            flip_samples.append(summary)

    flip_samples = sorted(
        flip_samples,
        key=lambda row: safe_float(row.get("score_delta"), -1.0) or -1.0,
        reverse=True,
    )
    return all_image_summaries, flip_samples


def flip_summary_rows(image_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def summarize(analysis_type: str, key_fn: Any) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in image_summaries:
            grouped[str(key_fn(row) or "unknown")].append(row)
        output: list[dict[str, Any]] = []
        for group, items in sorted(grouped.items()):
            deltas = [
                safe_float(item.get("score_delta"))
                for item in items
                if safe_float(item.get("score_delta")) is not None
            ]
            numeric = [float(delta) for delta in deltas if delta is not None]
            flip_count = sum(1 for item in items if item.get("has_resolution_flip") == "true")
            total = len(items)
            output.append(
                {
                    "analysis_type": analysis_type,
                    "group": group,
                    "total_count": total,
                    "flip_count": flip_count,
                    "flip_rate": fmt_float(safe_ratio(flip_count, total)),
                    "avg_score_delta": fmt_float(mean(numeric) if numeric else None),
                    "median_score_delta": fmt_float(median(numeric) if numeric else None),
                    "max_score_delta": fmt_float(max(numeric) if numeric else None),
                }
            )
        return output

    rows: list[dict[str, Any]] = []
    rows.extend(summarize("true_label", lambda row: row.get("true_label")))
    rows.extend(summarize("semantic_category", lambda row: row.get("semantic_category")))
    rows.extend(summarize("transform_group", lambda row: row.get("transform_group")))
    rows.extend(summarize("dataset_role", lambda row: row.get("dataset_role")))
    rows.extend(summarize("category", lambda row: row.get("category")))
    rows.extend(summarize("extension", lambda row: row.get("extension")))
    rows.extend(summarize("original_resolution_bucket", lambda row: row.get("original_resolution_bucket")))
    rows.extend(summarize("flip_type", lambda row: row.get("flip_type")))
    return rows


def intersection_rows(
    original_rows: list[dict[str, Any]],
    image_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    flip_by_path = {row["image_path"]: row for row in image_summaries}
    real_rows = [row for row in original_rows if row.get("true_label") == "real"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped["__overall__"] = []
    for row in real_rows:
        grouped[row.get("semantic_category", "unknown")].append(row)
        grouped["__overall__"].append(row)

    output: list[dict[str, Any]] = []
    for category, items in sorted(grouped.items()):
        real_total = len(items)
        fp_items = [row for row in items if row.get("false_positive") == "true"]
        flip_items = [
            row for row in items
            if flip_by_path.get(row.get("image_path", ""), {}).get("has_resolution_flip") == "true"
        ]
        fp_and_flip = [
            row for row in fp_items
            if flip_by_path.get(row.get("image_path", ""), {}).get("has_resolution_flip") == "true"
        ]
        all_deltas = [
            safe_float(flip_by_path.get(row.get("image_path", ""), {}).get("score_delta"))
            for row in items
        ]
        fp_deltas = [
            safe_float(flip_by_path.get(row.get("image_path", ""), {}).get("score_delta"))
            for row in fp_items
        ]
        non_fp_deltas = [
            safe_float(flip_by_path.get(row.get("image_path", ""), {}).get("score_delta"))
            for row in items
            if row.get("false_positive") != "true"
        ]
        all_deltas = [float(value) for value in all_deltas if value is not None]
        fp_deltas = [float(value) for value in fp_deltas if value is not None]
        non_fp_deltas = [float(value) for value in non_fp_deltas if value is not None]
        output.append(
            {
                "category": category,
                "real_total": real_total,
                "real_fp_count": len(fp_items),
                "real_fp_rate": fmt_float(safe_ratio(len(fp_items), real_total)),
                "real_flip_count": len(flip_items),
                "real_flip_rate": fmt_float(safe_ratio(len(flip_items), real_total)),
                "fp_and_flip_count": len(fp_and_flip),
                "fp_and_flip_rate": fmt_float(safe_ratio(len(fp_and_flip), len(fp_items))),
                "avg_score_delta_all_real": fmt_float(mean(all_deltas) if all_deltas else None),
                "avg_score_delta_fp_real": fmt_float(mean(fp_deltas) if fp_deltas else None),
                "avg_score_delta_non_fp_real": fmt_float(mean(non_fp_deltas) if non_fp_deltas else None),
            }
        )
    return output


def counts_by(rows: Iterable[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(str(row.get(key, "unknown") or "unknown") for row in rows)


def markdown_table(rows: list[dict[str, Any]], fields: list[str], limit: int | None = None) -> list[str]:
    selected = rows[:limit] if limit is not None else rows
    if not selected:
        return ["No rows."]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in selected:
        values = [str(row.get(field, "")).replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def top_groups(rows: list[dict[str, Any]], analysis_type: str, limit: int = 5) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("analysis_type") == analysis_type]
    return sorted(
        selected,
        key=lambda row: (
            safe_float(row.get("false_positive_rate"), 0.0) or 0.0,
            int(row.get("false_positive_count") or 0),
        ),
        reverse=True,
    )[:limit]


def flip_top_groups(rows: list[dict[str, Any]], analysis_type: str, limit: int = 5) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("analysis_type") == analysis_type]
    return sorted(
        selected,
        key=lambda row: (
            safe_float(row.get("flip_rate"), 0.0) or 0.0,
            int(row.get("flip_count") or 0),
        ),
        reverse=True,
    )[:limit]


def root_cause_hypotheses(
    original_rows: list[dict[str, Any]],
    fp_cluster_rows_: list[dict[str, Any]],
    image_summaries: list[dict[str, Any]],
    intersection: list[dict[str, Any]],
) -> dict[str, list[str]]:
    real_rows = [row for row in original_rows if row.get("true_label") == "real"]
    fp_rows = [row for row in real_rows if row.get("false_positive") == "true"]
    total_real = len(real_rows)
    fp_rate = safe_ratio(len(fp_rows), total_real)
    flip_count = sum(1 for row in image_summaries if row.get("has_resolution_flip") == "true")
    flip_rate = safe_ratio(flip_count, len(image_summaries))

    hypotheses = {"Strong evidence": [], "Medium evidence": [], "Weak evidence": []}

    ext_rows = [row for row in fp_cluster_rows_ if row.get("analysis_type") == "extension"]
    ext_rates = [safe_float(row.get("false_positive_rate"), 0.0) or 0.0 for row in ext_rows]
    if ext_rates and max(ext_rates) - min(ext_rates) >= 0.15:
        top = max(ext_rows, key=lambda row: safe_float(row.get("false_positive_rate"), 0.0) or 0.0)
        hypotheses["Strong evidence"].append(
            f"Format bias is visible: extension '{top['group']}' has the highest real FP rate at {top['false_positive_rate']}."
        )
    elif ext_rates and max(ext_rates) - min(ext_rates) >= 0.08:
        top = max(ext_rows, key=lambda row: safe_float(row.get("false_positive_rate"), 0.0) or 0.0)
        hypotheses["Medium evidence"].append(
            f"Format bias may be present: extension '{top['group']}' leads the FP rate table."
        )
    else:
        hypotheses["Weak evidence"].append("Format bias is not clearly separable from the current sample counts.")

    jpeg_no_exif = [
        row for row in real_rows
        if row.get("extension") in {"jpg", "jpeg"} and exif_group(row.get("has_exif")) == "no_exif"
    ]
    jpeg_no_exif_fp = [row for row in jpeg_no_exif if row.get("false_positive") == "true"]
    jpeg_no_exif_rate = safe_ratio(len(jpeg_no_exif_fp), len(jpeg_no_exif))
    if jpeg_no_exif and jpeg_no_exif_rate >= fp_rate + 0.10:
        hypotheses["Strong evidence"].append(
            f"No-EXIF JPEG is a concentrated FP cluster: {len(jpeg_no_exif_fp)}/{len(jpeg_no_exif)} real no-EXIF JPEGs are FP."
        )
    elif jpeg_no_exif and jpeg_no_exif_rate >= fp_rate + 0.05:
        hypotheses["Medium evidence"].append(
            f"No-EXIF JPEG remains elevated versus overall real FP rate ({jpeg_no_exif_rate:.6f} vs {fp_rate:.6f})."
        )
    else:
        hypotheses["Weak evidence"].append("No-EXIF JPEG concentration is not strong in this run, or the subset is too small.")

    if flip_rate >= 0.30:
        hypotheses["Strong evidence"].append(
            f"Resolution resizing materially affects decisions: overall flip rate is {flip_rate:.6f}."
        )
    elif flip_rate >= 0.15:
        hypotheses["Medium evidence"].append(
            f"Resolution resizing has a measurable effect: overall flip rate is {flip_rate:.6f}."
        )
    else:
        hypotheses["Weak evidence"].append(
            f"Resolution flip rate is limited in this run ({flip_rate:.6f}), though score deltas may still matter."
        )

    category_rows = [row for row in fp_cluster_rows_ if row.get("analysis_type") == "semantic_category"]
    category_rows = [row for row in category_rows if int(row.get("total_real") or 0) > 0]
    if category_rows:
        top_category = max(
            category_rows,
            key=lambda row: (
                safe_float(row.get("false_positive_rate"), 0.0) or 0.0,
                int(row.get("false_positive_count") or 0),
            ),
        )
        top_rate = safe_float(top_category.get("false_positive_rate"), 0.0) or 0.0
        if top_rate >= fp_rate + 0.10 and int(top_category.get("false_positive_count") or 0) >= 3:
            hypotheses["Strong evidence"].append(
                f"Category-specific FP risk is visible in '{top_category['group']}' at rate {top_category['false_positive_rate']}."
            )
        elif top_rate >= fp_rate + 0.05:
            hypotheses["Medium evidence"].append(
                f"Some category skew exists, led by '{top_category['group']}' at FP rate {top_category['false_positive_rate']}."
            )
        else:
            hypotheses["Weak evidence"].append("No category is clearly dominant after normalizing by category size.")
    else:
        hypotheses["Weak evidence"].append("Category-level FP evidence is unavailable because no real images were evaluated.")

    near_boundary = [
        row for row in original_rows
        if (safe_float(row.get("score")) is not None and 0.10 <= float(safe_float(row.get("score"))) < 0.18)
    ]
    if original_rows and len(near_boundary) / len(original_rows) >= 0.25:
        hypotheses["Strong evidence"].append(
            f"Many samples sit near the 0.15 baseline boundary: {len(near_boundary)}/{len(original_rows)} in [0.10, 0.18)."
        )
    elif original_rows and len(near_boundary) / len(original_rows) >= 0.12:
        hypotheses["Medium evidence"].append(
            f"Boundary crowding exists around threshold 0.15: {len(near_boundary)} samples in [0.10, 0.18)."
        )
    else:
        hypotheses["Weak evidence"].append("The current run does not show heavy score crowding around threshold 0.15.")

    raw_fp = sum(1 for row in real_rows if row.get("raw_false_positive") == "true")
    final_fp = sum(1 for row in real_rows if row.get("final_false_positive") == "true")
    uncertain_real = sum(1 for row in real_rows if row.get("final_label") == "uncertain")
    if raw_fp > final_fp and uncertain_real > 0:
        hypotheses["Medium evidence"].append(
            f"The uncertain layer already catches some raw FP pressure ({raw_fp} raw FP vs {final_fp} final FP), but may need stronger handling."
        )
    elif raw_fp == final_fp and raw_fp > 0:
        hypotheses["Medium evidence"].append(
            "The uncertain layer does not reduce current raw real->AI FP cases, so Day16 should inspect soft-decision rules."
        )
    else:
        hypotheses["Weak evidence"].append("Uncertain-layer evidence is limited by the current FP count.")

    overall = next((row for row in intersection if row.get("category") == "__overall__"), None)
    if overall:
        real_fp_rate = safe_float(overall.get("real_fp_rate"), 0.0) or 0.0
        real_flip_rate = safe_float(overall.get("real_flip_rate"), 0.0) or 0.0
        fp_flip_rate = safe_float(overall.get("fp_and_flip_rate"), 0.0) or 0.0
        if fp_flip_rate >= real_flip_rate + 0.10 and real_fp_rate > 0:
            hypotheses["Medium evidence"].append(
                f"Real FP samples flip more often than real samples overall ({fp_flip_rate:.6f} vs {real_flip_rate:.6f})."
            )

    return hypotheses


def render_report(
    path: Path,
    all_original_rows: list[dict[str, Any]],
    original_rows: list[dict[str, Any]],
    resolution_control_rows: list[dict[str, Any]],
    fp_samples_: list[dict[str, Any]],
    fp_summary: list[dict[str, Any]],
    image_summaries: list[dict[str, Any]],
    flip_samples_: list[dict[str, Any]],
    flip_summary: list[dict[str, Any]],
    intersection: list[dict[str, Any]],
    generated_files: list[Path],
    threshold: float,
) -> None:
    ai_count = sum(1 for row in original_rows if row.get("true_label") == "ai")
    real_count = sum(1 for row in original_rows if row.get("true_label") == "real")
    unknown_label_count = sum(1 for row in original_rows if row.get("true_label") == "unknown")
    total = len(original_rows)
    excluded_resolution_control_count = len(resolution_control_rows)
    fp_count = len(fp_samples_)
    fp_rate = safe_ratio(fp_count, real_count)
    raw_fp_count = sum(1 for row in original_rows if row.get("true_label") == "real" and row.get("raw_false_positive") == "true")
    final_fp_count = sum(1 for row in original_rows if row.get("true_label") == "real" and row.get("final_false_positive") == "true")
    flip_count = len(flip_samples_)
    flip_rate = safe_ratio(flip_count, len(image_summaries))
    final_uncertain = sum(1 for row in original_rows if row.get("final_label") == "uncertain")
    final_uncertain_rate = safe_ratio(final_uncertain, total)

    extensions = counts_by(original_rows, "extension")
    categories_ai = {row.get("semantic_category", "") for row in original_rows if row.get("true_label") == "ai"}
    categories_real = {row.get("semantic_category", "") for row in original_rows if row.get("true_label") == "real"}
    resolution_counts = Counter(
        resolution_bucket(row.get("width"), row.get("height"))
        for row in original_rows
    )
    hypotheses = root_cause_hypotheses(original_rows, fp_summary, image_summaries, intersection)
    all_unknown_rows = [row for row in all_original_rows if row.get("true_label") == "unknown"]
    base_id_counts = Counter(
        (row.get("true_label", ""), row.get("semantic_category", ""), row.get("base_id", ""))
        for row in original_rows
        if row.get("dataset_role") in {"raw_source", "paired_format"} and row.get("base_id")
    )
    duplicate_base_count = sum(1 for count in base_id_counts.values() if count > 1)
    appendix_counts = Counter(row.get("transform_group", "unknown") for row in resolution_control_rows)
    appendix_labels = Counter(row.get("true_label", "unknown") for row in resolution_control_rows)
    appendix_final_labels = Counter(row.get("final_label", "unknown") for row in resolution_control_rows)
    appendix_uncertain_count = sum(1 for row in resolution_control_rows if row.get("final_label") == "uncertain")

    lines: list[str] = [
        "# Day15 False Positive Cluster + Resolution Flip Root Cause Analysis",
        "",
        "## 1. Executive Summary",
        "",
        f"- main_total_images: {total}",
        f"- main_ai_count: {ai_count}",
        f"- main_real_count: {real_count}",
        f"- main_unknown_count: {unknown_label_count}",
        f"- excluded_resolution_control_count: {excluded_resolution_control_count}",
        f"- raw_false_positive_count: {raw_fp_count}",
        f"- raw_false_positive_rate: {safe_ratio(raw_fp_count, real_count):.6f}",
        f"- final_false_positive_count: {final_fp_count}",
        f"- final_false_positive_rate: {safe_ratio(final_fp_count, real_count):.6f}",
        f"- main_resolution_flip_count: {flip_count}",
        f"- main_resolution_flip_rate: {flip_rate:.6f}",
        f"- main_uncertain_count: {final_uncertain}",
        f"- main_uncertain_rate: {final_uncertain_rate:.6f}",
        f"- Baseline threshold remains {threshold:.6f}; no detector weights, threshold, or default model strategy were changed.",
        "- Main metrics include raw_source, paired_format, and legacy only; Day14 resolution_control derivatives are excluded from main conclusions.",
        "",
        "## 2. Dataset Overview",
        "",
        f"- AI categories: {len(categories_ai)}.",
        f"- Real categories: {len(categories_real)}.",
        f"- Unknown label count: {unknown_label_count}.",
        f"- Format distribution: {dict(sorted(extensions.items()))}.",
        f"- Transform group distribution: {dict(sorted(counts_by(original_rows, 'transform_group').items()))}.",
        f"- Original resolution buckets: {dict(sorted(resolution_counts.items()))}.",
        "",
        "Top semantic category counts:",
        "",
        *markdown_table(
            [
                {"semantic_category": category, "count": count}
                for category, count in counts_by(original_rows, "semantic_category").most_common(10)
            ],
            ["semantic_category", "count"],
        ),
        "",
        "## 2.1 Data Quality Notes",
        "",
        f"- Unknown label paths in the full scanned set: {len(all_unknown_rows)}.",
        *(
            ["- First 20 unknown label paths:"]
            + [f"  - `{row.get('image_path', '')}`" for row in all_unknown_rows[:20]]
            if all_unknown_rows
            else ["- No unknown-label images were found after filename fallback inference."]
        ),
        f"- Excluded resolution_control images: {excluded_resolution_control_count}. These Day14-derived resize-control images are excluded from main metrics.",
        f"- Duplicate base_id groups in raw/paired main rows: {duplicate_base_count}. Paired JPG/PNG/raw variants increase sample weight; Day16 can add source-level aggregation.",
        "",
        "## 3. False Positive Cluster Analysis",
        "",
        "Highest FP-rate groups by semantic category:",
        "",
        *markdown_table(
            top_groups(fp_summary, "semantic_category"),
            ["group", "total_real", "false_positive_count", "false_positive_rate", "avg_score", "median_score"],
        ),
        "",
        "Highest FP-rate groups by transform group:",
        "",
        *markdown_table(
            top_groups(fp_summary, "transform_group"),
            ["group", "total_real", "false_positive_count", "false_positive_rate", "avg_score", "median_score"],
        ),
        "",
        "Highest FP-rate groups by extension:",
        "",
        *markdown_table(
            top_groups(fp_summary, "extension"),
            ["group", "total_real", "false_positive_count", "false_positive_rate", "avg_score", "median_score"],
        ),
        "",
        "Highest FP-rate groups by EXIF:",
        "",
        *markdown_table(
            top_groups(fp_summary, "exif"),
            ["group", "total_real", "false_positive_count", "false_positive_rate", "avg_score", "median_score"],
        ),
        "",
        "False Positive top samples:",
        "",
        *markdown_table(
            fp_samples_[:30],
            ["image_path", "semantic_category", "transform_group", "extension", "width", "height", "has_exif", "score", "final_label", "difficulty"],
        ),
        "",
        "## 4. Resolution Flip Analysis",
        "",
        "Flip-rate groups by true label:",
        "",
        *markdown_table(
            flip_top_groups(flip_summary, "true_label"),
            ["group", "total_count", "flip_count", "flip_rate", "avg_score_delta", "max_score_delta"],
        ),
        "",
        "Flip-rate groups by semantic category:",
        "",
        *markdown_table(
            flip_top_groups(flip_summary, "semantic_category"),
            ["group", "total_count", "flip_count", "flip_rate", "avg_score_delta", "max_score_delta"],
        ),
        "",
        "Flip-rate groups by transform group:",
        "",
        *markdown_table(
            flip_top_groups(flip_summary, "transform_group"),
            ["group", "total_count", "flip_count", "flip_rate", "avg_score_delta", "max_score_delta"],
        ),
        "",
        "Resolution Flip top samples:",
        "",
        *markdown_table(
            flip_samples_[:30],
            [
                "image_path",
                "true_label",
                "semantic_category",
                "transform_group",
                "extension",
                "original_size",
                "original_label",
                "resized_512_label",
                "resized_768_label",
                "resized_1024_label",
                "score_delta",
            ],
        ),
        "",
        "## 5. FP x Resolution Flip Intersection",
        "",
        *markdown_table(
            intersection,
            [
                "category",
                "real_total",
                "real_fp_count",
                "real_fp_rate",
                "real_flip_count",
                "real_flip_rate",
                "fp_and_flip_count",
                "fp_and_flip_rate",
            ],
        ),
        "",
        "## Appendix: Derived Resolution Control Set",
        "",
        "This section describes the Day14-derived resolution control set. It is not included in main FP or main flip conclusions, and is only used to observe whether existing long_512 / long_768 / long_1024 variants are stable.",
        "",
        f"- resolution_control_total: {excluded_resolution_control_count}",
        f"- label distribution: {dict(sorted(appendix_labels.items()))}",
        f"- transform distribution: {dict(sorted(appendix_counts.items()))}",
        f"- final_label distribution: {dict(sorted(appendix_final_labels.items()))}",
        f"- uncertain count: {appendix_uncertain_count}",
        "",
        "## 6. Root Cause Hypotheses",
        "",
    ]

    for strength in ("Strong evidence", "Medium evidence", "Weak evidence"):
        lines.append(f"### {strength}")
        lines.append("")
        items = hypotheses[strength] or ["No hypothesis reached this evidence level in the current run."]
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(
        [
            "## 7. Engineering Recommendations for Day16",
            "",
            "- Consider enhancing the uncertain layer for score-near-threshold samples instead of moving the default threshold.",
            "- Add image_quality and metadata_quality features so no-EXIF and JPEG compression are contextual signals rather than direct authenticity signals.",
            "- Add soft-decision handling for samples near threshold 0.15 and inside the current 0.12-0.18 final-label band.",
            "- Explore resolution-stability constraints so a single resize cannot silently flip the product-facing label.",
            "- Add more controlled Real JPEG no-EXIF counterexamples, especially in the categories with elevated FP rates.",
            "- Add explainable evidence to reports so FP clusters can be traced to metadata, forensic, or frequency components.",
            "",
            "## 8. Files Generated",
            "",
        ]
    )
    for generated in generated_files:
        lines.append(f"- `{display_path(generated)}`")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    test_root = resolve_path(args.test_root)
    reports_dir = resolve_path(args.reports_dir)
    tmp_root = resolve_path(args.tmp_root)

    config = load_detector_weight_config()
    policy = load_decision_policy(config)
    threshold = float(policy["threshold"])
    detector_config_name = str(config.get("default_profile") or "baseline")

    images = collect_images(test_root)
    print_scan_debug(PROJECT_ROOT, test_root, images)
    if not images:
        print("ERROR: No images found under data/test_images.")
        print("Please check whether the dataset is inside the current project root.")
        print_directory_tree(test_root, max_depth=3)
        return 1

    difficulty_by_path, difficulty_by_filename = load_difficulty_lookup(test_root)

    print(f"Day15 scanning root: {display_path(test_root)}", flush=True)
    print(f"Found {len(images)} images under data/test_images recursively.", flush=True)

    original_rows = evaluate_originals(
        images,
        threshold,
        detector_config_name,
        difficulty_by_path,
        difficulty_by_filename,
    )
    main_images = [item for item in images if item.get("is_main_dataset")]
    main_original_rows = [row for row in original_rows if row.get("is_main_dataset") == "true"]
    resolution_control_rows = [
        row for row in original_rows
        if row.get("dataset_role") == "resolution_control"
    ]
    fp_samples_ = false_positive_samples(main_original_rows)
    fp_summary = false_positive_cluster_rows(main_original_rows)
    variant_rows = evaluate_resolution_variants(
        main_images,
        main_original_rows,
        threshold,
        detector_config_name,
        tmp_root,
    )
    image_summaries, flip_samples_ = build_flip_samples(variant_rows)
    flip_summary = flip_summary_rows(image_summaries)
    intersection = intersection_rows(main_original_rows, image_summaries)

    output_paths = {
        ALL_PREDICTIONS_CSV: reports_dir / ALL_PREDICTIONS_CSV,
        FALSE_POSITIVE_SAMPLES_CSV: reports_dir / FALSE_POSITIVE_SAMPLES_CSV,
        FALSE_POSITIVE_CLUSTER_SUMMARY_CSV: reports_dir / FALSE_POSITIVE_CLUSTER_SUMMARY_CSV,
        RESOLUTION_VARIANT_PREDICTIONS_CSV: reports_dir / RESOLUTION_VARIANT_PREDICTIONS_CSV,
        RESOLUTION_FLIP_SAMPLES_CSV: reports_dir / RESOLUTION_FLIP_SAMPLES_CSV,
        RESOLUTION_FLIP_SUMMARY_CSV: reports_dir / RESOLUTION_FLIP_SUMMARY_CSV,
        FP_RESOLUTION_INTERSECTION_CSV: reports_dir / FP_RESOLUTION_INTERSECTION_CSV,
        REPORT_MD: reports_dir / REPORT_MD,
        RESOLUTION_CONTROL_APPENDIX_CSV: reports_dir / RESOLUTION_CONTROL_APPENDIX_CSV,
    }

    write_csv(output_paths[ALL_PREDICTIONS_CSV], ALL_PREDICTION_FIELDS, original_rows)
    write_csv(output_paths[FALSE_POSITIVE_SAMPLES_CSV], FP_SAMPLE_FIELDS, fp_samples_)
    write_csv(output_paths[FALSE_POSITIVE_CLUSTER_SUMMARY_CSV], FP_CLUSTER_FIELDS, fp_summary)
    write_csv(output_paths[RESOLUTION_VARIANT_PREDICTIONS_CSV], VARIANT_FIELDS, variant_rows)
    write_csv(output_paths[RESOLUTION_FLIP_SAMPLES_CSV], FLIP_SAMPLE_FIELDS, flip_samples_)
    write_csv(output_paths[RESOLUTION_FLIP_SUMMARY_CSV], FLIP_SUMMARY_FIELDS, flip_summary)
    write_csv(output_paths[FP_RESOLUTION_INTERSECTION_CSV], INTERSECTION_FIELDS, intersection)
    write_csv(output_paths[RESOLUTION_CONTROL_APPENDIX_CSV], ALL_PREDICTION_FIELDS, resolution_control_rows)
    render_report(
        output_paths[REPORT_MD],
        original_rows,
        main_original_rows,
        resolution_control_rows,
        fp_samples_,
        fp_summary,
        image_summaries,
        flip_samples_,
        flip_summary,
        intersection,
        list(output_paths.values()),
        threshold,
    )

    ai_count = sum(1 for row in main_original_rows if row.get("true_label") == "ai")
    real_count = sum(1 for row in main_original_rows if row.get("true_label") == "real")
    unknown_label_count = sum(1 for row in main_original_rows if row.get("true_label") == "unknown")
    excluded_resolution_control_count = len(resolution_control_rows)
    raw_fp_count = sum(1 for row in main_original_rows if row.get("true_label") == "real" and row.get("raw_false_positive") == "true")
    final_fp_count = sum(1 for row in main_original_rows if row.get("true_label") == "real" and row.get("final_false_positive") == "true")
    flip_count = len(flip_samples_)
    uncertain_count = sum(1 for row in main_original_rows if row.get("final_label") == "uncertain")

    print(f"main_total_images: {len(main_original_rows)}")
    print(f"main_ai_count: {ai_count}")
    print(f"main_real_count: {real_count}")
    print(f"main_unknown_count: {unknown_label_count}")
    print(f"excluded_resolution_control_count: {excluded_resolution_control_count}")
    print(f"raw_false_positive_count: {raw_fp_count}")
    print(f"raw_false_positive_rate: {safe_ratio(raw_fp_count, real_count):.6f}")
    print(f"final_false_positive_count: {final_fp_count}")
    print(f"final_false_positive_rate: {safe_ratio(final_fp_count, real_count):.6f}")
    print(f"main_resolution_flip_count: {flip_count}")
    print(f"main_resolution_flip_rate: {safe_ratio(flip_count, len(image_summaries)):.6f}")
    print(f"main_uncertain_count: {uncertain_count}")
    print(f"main_uncertain_rate: {safe_ratio(uncertain_count, len(main_original_rows)):.6f}")
    print(f"Report path: {display_path(output_paths[REPORT_MD])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
