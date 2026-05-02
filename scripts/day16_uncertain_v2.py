from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Iterable

from PIL import Image, ImageOps, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import (  # noqa: E402
    BASELINE_THRESHOLD,
    binary_label_at_threshold,
    load_uncertain_v21_policy,
    load_uncertain_v2_policy,
    make_uncertain_decision_v21,
    make_uncertain_decision_v2,
)
from core.forensic_analyzer import analyze_forensics  # noqa: E402
from core.frequency_analyzer import analyze_frequency  # noqa: E402
from core.metadata_analyzer import analyze_metadata  # noqa: E402
from core.model_detector import detect_with_model  # noqa: E402
from core.score_fusion import fuse_scores, load_detector_weight_config  # noqa: E402
from scripts.day15_false_positive_resolution_analysis import (  # noqa: E402
    collect_images,
    display_path,
    image_basic_info,
    normalized_extension,
    safe_float,
    safe_ratio,
    target_size,
)


DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "test_images"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_TMP_ROOT = PROJECT_ROOT / ".tmp" / "day16_resolution_variants"
DEFAULT_DAY15_VARIANTS_CSV = PROJECT_ROOT / "reports" / "day15_resolution_variant_predictions.csv"
DEFAULT_DAY15_ALL_CSV = PROJECT_ROOT / "reports" / "day15_all_predictions.csv"
RESOLUTION_TARGETS = (1024, 768, 512)
VALID_LABELS = {"ai", "real"}

MULTI_RES_CSV = "day16_multi_resolution_consistency.csv"
RESULTS_CSV = "day16_uncertain_decision_v2_results.csv"
SUMMARY_JSON = "day16_uncertain_v2_summary.json"
REPORT_MD = "day16_uncertain_v2_report.md"
RESIZE_BIAS_DIAGNOSTICS_CSV = "day16_1_resize_bias_diagnostics.csv"
RESIZE_BIAS_SUMMARY_JSON = "day16_1_resize_bias_summary.json"
V21_RESULTS_CSV = "day16_1_uncertain_decision_v21_results.csv"
V21_SUMMARY_JSON = "day16_1_uncertain_v21_summary.json"
V21_REPORT_MD = "day16_1_uncertain_v21_report.md"

MULTI_RES_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "folder",
    "original_width",
    "original_height",
    "resolution_variant",
    "resized_width",
    "resized_height",
    "score",
    "raw_label_at_0_15",
    "format",
    "has_exif",
    "status",
    "warning",
    "error_message",
    "variant_path",
]

RESULT_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "format",
    "mean_score",
    "min_score",
    "max_score",
    "score_std",
    "score_range",
    "raw_label_votes",
    "resolution_flip_count",
    "consistency_status",
    "final_label",
    "is_correct_when_definite",
    "decision_reason",
    "raw_label_at_0_15",
    "raw_score_at_0_15",
    "has_exif",
    "status",
    "warning_count",
]

RESIZE_DIAGNOSTIC_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "format",
    "has_exif",
    "original_score",
    "resize_mean_score",
    "resize_delta",
    "mean_score",
    "median_score",
    "min_score",
    "max_score",
    "score_std",
    "score_range",
    "ai_vote_count",
    "real_vote_count",
    "original_raw_label_at_0_15",
    "resize_raw_label_votes",
    "final_label_v2",
    "decision_reason_v2",
]

V21_RESULT_FIELDS = [
    "image_path",
    "true_label",
    "category",
    "format",
    "has_exif",
    "original_score",
    "resize_mean_score",
    "resize_delta",
    "mean_score",
    "median_score",
    "min_score",
    "max_score",
    "score_std",
    "score_range",
    "ai_vote_count",
    "real_vote_count",
    "resolution_flip_count",
    "final_label_v2",
    "final_label_v21",
    "decision_reason_v2",
    "decision_reason_v21",
    "is_correct_when_definite_v21",
    "raw_label_at_0_15",
]


def parse_args() -> argparse.Namespace:
    """Parse Day16 CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Day16 uncertain decision v2 with multi-resolution consistency."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Root recursively scanned for test images. Default: data/test_images",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=BASELINE_THRESHOLD,
        help="Baseline raw-label threshold. Default: 0.15",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Output directory. Default: reports",
    )
    parser.add_argument(
        "--tmp-root",
        type=Path,
        default=DEFAULT_TMP_ROOT,
        help="Temporary directory for resized variants. Default: .tmp/day16_resolution_variants",
    )
    parser.add_argument(
        "--day15-cache",
        type=Path,
        default=DEFAULT_DAY15_VARIANTS_CSV,
        help="Optional Day15 multi-resolution prediction CSV to reuse when present.",
    )
    parser.add_argument(
        "--day15-all",
        type=Path,
        default=DEFAULT_DAY15_ALL_CSV,
        help="Optional Day15 original prediction CSV used for has_exif lookup.",
    )
    parser.add_argument(
        "--force-rescan",
        action="store_true",
        help="Ignore Day15 cached predictions and rerun the detector for every variant.",
    )
    parser.add_argument(
        "--policy",
        choices=("v2", "v21"),
        default="v2",
        help="Decision report to print. v21 also writes Day16.1 comparison reports.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    """Resolve a CLI path relative to the project root."""
    return path if path.is_absolute() else PROJECT_ROOT / path


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    """Write dictionaries to a UTF-8 CSV with a stable field order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file, returning an empty list if it is unavailable."""
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error):
        return []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a formatted UTF-8 JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_float(value: Any, digits: int = 6) -> str:
    """Format a numeric value for CSV or Markdown output."""
    number = safe_float(value)
    return "" if number is None else f"{number:.{digits}f}"


def bool_text(value: bool | None) -> str:
    """Return a stable lower-case text representation for booleans."""
    if value is None:
        return "unknown"
    return "true" if value else "false"


def image_format(path: Path) -> str:
    """Read the image container format, falling back to the file extension."""
    try:
        with Image.open(path) as opened:
            return str(opened.format or normalized_extension(path)).lower()
    except Exception:
        return normalized_extension(path)


def variant_path_for(source: Path, target: int, tmp_root: Path) -> Path:
    """Build a deterministic Day16 resized-variant path."""
    try:
        relative = source.resolve().relative_to(PROJECT_ROOT).with_suffix("")
    except ValueError:
        relative = Path(source.stem)
    safe_parts = [
        "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in part)
        for part in relative.parts
    ]
    return tmp_root.joinpath(*safe_parts).with_name(
        f"{safe_parts[-1]}__long_edge_{target}{source.suffix.lower()}"
    )


def save_resized_variant(source: Path, destination: Path, target: int) -> tuple[int, int]:
    """Save a resized copy with the requested long edge while preserving aspect ratio."""
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


def run_detector_score(path: Path, threshold: float) -> dict[str, Any]:
    """Run the existing detector stack and return the raw Day16 fields."""
    try:
        final_result = fuse_scores(
            metadata_result=analyze_metadata(path),
            forensic_result=analyze_forensics(path),
            frequency_result=analyze_frequency(path),
            model_result=detect_with_model(path),
        )
    except Exception as exc:
        return {
            "score": "",
            "raw_label_at_0_15": "",
            "status": "error",
            "error_message": str(exc),
        }

    score = safe_float(final_result.get("final_score", final_result.get("raw_score")))
    if score is None:
        return {
            "score": "",
            "raw_label_at_0_15": "",
            "status": "error",
            "error_message": "No score returned by detector.",
        }
    return {
        "score": round(score, 6),
        "raw_label_at_0_15": binary_label_at_threshold(score, threshold),
        "status": "success",
        "error_message": "",
    }


def day15_variant_name_to_day16(value: str) -> str:
    """Map Day15 variant names to Day16 resolution labels."""
    if value == "original":
        return "original"
    if value.startswith("resized_"):
        return f"long_edge_{value.removeprefix('resized_')}"
    return value


def variant_sort_key(row: dict[str, Any]) -> int:
    """Sort variants in Day16's original, 1024, 768, 512 order."""
    order = {
        "original": 0,
        "long_edge_1024": 1,
        "long_edge_768": 2,
        "long_edge_512": 3,
    }
    return order.get(str(row.get("resolution_variant") or ""), 99)


def load_has_exif_lookup(day15_all_csv: Path) -> dict[str, str]:
    """Load original has_exif values from Day15 if available."""
    lookup: dict[str, str] = {}
    for row in read_csv(day15_all_csv):
        image_path = str(row.get("image_path") or "")
        if image_path:
            lookup[image_path] = str(row.get("has_exif") or "unknown")
    return lookup


def load_day15_cached_multi_rows(
    day15_variants_csv: Path,
    day15_all_csv: Path,
    threshold: float,
) -> list[dict[str, Any]]:
    """Convert Day15 multi-resolution predictions into Day16 row shape."""
    has_exif_by_path = load_has_exif_lookup(day15_all_csv)
    rows: list[dict[str, Any]] = []
    for source in read_csv(day15_variants_csv):
        image_path = str(source.get("image_path") or "")
        variant_path = str(source.get("variant_path") or "")
        score = safe_float(source.get("score"))
        raw_label = binary_label_at_threshold(score, threshold) if score is not None else ""
        status = str(source.get("status") or "")
        rows.append(
            {
                "image_path": image_path,
                "true_label": source.get("true_label", ""),
                "category": source.get("category", ""),
                "folder": Path(image_path).parent.name,
                "original_width": source.get("original_width", ""),
                "original_height": source.get("original_height", ""),
                "resolution_variant": day15_variant_name_to_day16(str(source.get("variant_name") or "")),
                "resized_width": source.get("variant_width", ""),
                "resized_height": source.get("variant_height", ""),
                "score": "" if score is None else round(score, 6),
                "raw_label_at_0_15": raw_label,
                "format": str(source.get("extension") or "").lower(),
                "has_exif": has_exif_by_path.get(image_path, "unknown"),
                "status": status,
                "warning": "reused_day15_cached_detection",
                "error_message": source.get("error_message", ""),
                "variant_path": variant_path,
            }
        )
    return rows


def base_variant_row(
    item: dict[str, Any],
    source: Path,
    info: dict[str, Any],
    variant_name: str,
    variant_path: Path,
    resized_width: Any,
    resized_height: Any,
    status: str,
    warning: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    """Create a common multi-resolution CSV row before detection fields are added."""
    return {
        "image_path": display_path(source),
        "true_label": item["true_label"],
        "category": item["category"],
        "folder": source.parent.name,
        "original_width": info.get("width", ""),
        "original_height": info.get("height", ""),
        "resolution_variant": variant_name,
        "resized_width": resized_width,
        "resized_height": resized_height,
        "score": "",
        "raw_label_at_0_15": "",
        "format": image_format(variant_path if variant_path.exists() else source),
        "has_exif": info.get("has_exif", "unknown"),
        "status": status,
        "warning": warning,
        "error_message": error_message,
        "variant_path": display_path(variant_path),
    }


def evaluate_image_variants(
    item: dict[str, Any],
    threshold: float,
    tmp_root: Path,
) -> list[dict[str, Any]]:
    """Run original plus long-edge variants for one image."""
    source = item["path"]
    info = image_basic_info(source)
    width = safe_float(info.get("width"))
    height = safe_float(info.get("height"))
    rows: list[dict[str, Any]] = []

    if width is None or height is None:
        message = info.get("open_error") or "Could not read original image dimensions."
        rows.append(
            base_variant_row(
                item,
                source,
                info,
                "original",
                source,
                "",
                "",
                "error",
                error_message=message,
            )
        )
        return rows

    original_row = base_variant_row(
        item,
        source,
        info,
        "original",
        source,
        int(width),
        int(height),
        "pending",
    )
    original_detection = run_detector_score(source, threshold)
    original_row.update(original_detection)
    rows.append(original_row)

    original_long_edge = max(int(width), int(height))
    for target in RESOLUTION_TARGETS:
        variant_name = f"long_edge_{target}"
        if original_long_edge <= target:
            rows.append(
                base_variant_row(
                    item,
                    source,
                    info,
                    variant_name,
                    source,
                    int(width),
                    int(height),
                    "no_upscale",
                    warning=f"Original long edge {original_long_edge} <= target {target}; upscale skipped.",
                )
            )
            continue

        destination = variant_path_for(source, target, tmp_root)
        try:
            resized_width, resized_height = save_resized_variant(source, destination, target)
            row = base_variant_row(
                item,
                source,
                info,
                variant_name,
                destination,
                resized_width,
                resized_height,
                "pending",
            )
            row.update(run_detector_score(destination, threshold))
            rows.append(row)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            rows.append(
                base_variant_row(
                    item,
                    source,
                    info,
                    variant_name,
                    destination,
                    "",
                    "",
                    "error",
                    error_message=str(exc),
                )
            )
        except Exception as exc:
            rows.append(
                base_variant_row(
                    item,
                    source,
                    info,
                    variant_name,
                    destination,
                    "",
                    "",
                    "error",
                    error_message=str(exc),
                )
            )

    return rows


def aggregate_image_result(
    image_path: str,
    rows: list[dict[str, Any]],
    policy: dict[str, float],
) -> dict[str, Any]:
    """Aggregate successful variant rows into one Day16 v2 decision row."""
    successful = [row for row in rows if row.get("status") == "success"]
    scores = [
        float(row["score"])
        for row in successful
        if safe_float(row.get("score")) is not None
    ]
    raw_labels = [
        str(row.get("raw_label_at_0_15") or "")
        for row in successful
        if row.get("raw_label_at_0_15")
    ]
    decision = make_uncertain_decision_v2(scores, raw_labels, **policy)
    first = rows[0] if rows else {}
    original = next((row for row in rows if row.get("resolution_variant") == "original"), first)
    final_label = str(decision["final_label"])
    true_label = str(first.get("true_label", ""))
    is_definite = final_label in VALID_LABELS
    warning_count = sum(
        1 for row in rows
        if row.get("status") in {"warning", "no_upscale"}
        or (
            row.get("warning")
            and row.get("warning") != "reused_day15_cached_detection"
        )
    )
    status = "success" if scores else "error"

    return {
        "image_path": image_path,
        "true_label": true_label,
        "category": first.get("category", ""),
        "format": first.get("format", ""),
        "mean_score": decision["mean_score"],
        "min_score": decision["min_score"],
        "max_score": decision["max_score"],
        "score_std": decision["score_std"],
        "score_range": decision["score_range"],
        "raw_label_votes": json.dumps(decision["raw_label_votes"], sort_keys=True),
        "resolution_flip_count": decision["resolution_flip_count"],
        "consistency_status": decision["consistency_status"],
        "final_label": final_label,
        "is_correct_when_definite": "" if not is_definite else bool_text(final_label == true_label),
        "decision_reason": decision["decision_reason"],
        "raw_label_at_0_15": original.get("raw_label_at_0_15", ""),
        "raw_score_at_0_15": original.get("score", ""),
        "has_exif": first.get("has_exif", "unknown"),
        "status": status,
        "warning_count": warning_count,
    }


def group_variant_rows(multi_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group successful multi-resolution rows by image path."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in multi_rows:
        if row.get("status") != "success" or safe_float(row.get("score")) is None:
            continue
        grouped[str(row.get("image_path") or "")].append(row)
    return {
        image_path: sorted(rows, key=variant_sort_key)
        for image_path, rows in grouped.items()
        if image_path
    }


def feature_row_from_variants(
    image_path: str,
    rows: list[dict[str, Any]],
    v2_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build per-image score, vote, and resize-bias features."""
    original = next((row for row in rows if row.get("resolution_variant") == "original"), rows[0])
    scores_by_variant = {
        str(row.get("resolution_variant") or ""): float(row["score"])
        for row in rows
        if safe_float(row.get("score")) is not None
    }
    labels_by_variant = {
        str(row.get("resolution_variant") or ""): str(row.get("raw_label_at_0_15") or "")
        for row in rows
        if row.get("raw_label_at_0_15") in VALID_LABELS
    }
    scores = list(scores_by_variant.values())
    resize_scores = [
        score
        for variant, score in scores_by_variant.items()
        if variant != "original"
    ]
    resize_labels = [
        label
        for variant, label in labels_by_variant.items()
        if variant != "original"
    ]
    labels = [
        str(row.get("raw_label_at_0_15") or "")
        for row in rows
        if row.get("raw_label_at_0_15") in VALID_LABELS
    ]
    original_score = safe_float(original.get("score"))
    if original_score is None and scores:
        original_score = scores[0]
    resize_mean_score = (
        mean(resize_scores)
        if resize_scores
        else (original_score if original_score is not None else 0.0)
    )
    score_mean = mean(scores) if scores else 0.0
    score_median = median(scores) if scores else 0.0
    score_min = min(scores) if scores else 0.0
    score_max = max(scores) if scores else 0.0
    score_std = pstdev(scores) if len(scores) > 1 else 0.0
    score_range = score_max - score_min
    resize_votes = Counter(resize_labels)
    v2_row = v2_by_path.get(image_path, {})
    return {
        "image_path": image_path,
        "true_label": original.get("true_label", ""),
        "category": original.get("category", ""),
        "format": original.get("format", ""),
        "has_exif": original.get("has_exif", "unknown"),
        "original_score": round(float(original_score or 0.0), 6),
        "resize_mean_score": round(float(resize_mean_score), 6),
        "resize_delta": round(float(resize_mean_score - (original_score or 0.0)), 6),
        "mean_score": round(float(score_mean), 6),
        "median_score": round(float(score_median), 6),
        "min_score": round(float(score_min), 6),
        "max_score": round(float(score_max), 6),
        "score_std": round(float(score_std), 6),
        "score_range": round(float(score_range), 6),
        "ai_vote_count": labels.count("ai"),
        "real_vote_count": labels.count("real"),
        "original_raw_label_at_0_15": original.get("raw_label_at_0_15", ""),
        "resize_raw_label_votes": json.dumps(
            {"ai": resize_votes.get("ai", 0), "real": resize_votes.get("real", 0)},
            sort_keys=True,
        ),
        "final_label_v2": v2_row.get("final_label", ""),
        "decision_reason_v2": v2_row.get("decision_reason", ""),
        "scores_by_variant": scores_by_variant,
        "raw_labels_by_variant": labels_by_variant,
        "resolution_flip_count": sum(
            1 for previous, current in zip(labels, labels[1:])
            if previous != current
        ),
        "raw_label_at_0_15": original.get("raw_label_at_0_15", ""),
    }


def build_feature_rows(
    multi_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build per-image feature rows from multi-resolution and v2 outputs."""
    v2_by_path = {str(row.get("image_path") or ""): row for row in result_rows}
    grouped = group_variant_rows(multi_rows)
    return [
        feature_row_from_variants(image_path, rows, v2_by_path)
        for image_path, rows in sorted(grouped.items())
    ]


def public_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    """Drop internal dict fields before writing diagnostics CSV."""
    return {
        field: row.get(field, "")
        for field in RESIZE_DIAGNOSTIC_FIELDS
    }


def number_summary(values: list[float]) -> dict[str, float]:
    """Return mean, median, max, and min for a numeric list."""
    if not values:
        return {"mean": 0.0, "median": 0.0, "max": 0.0, "min": 0.0}
    return {
        "mean": round(mean(values), 6),
        "median": round(median(values), 6),
        "max": round(max(values), 6),
        "min": round(min(values), 6),
    }


def summarize_numeric_by(rows: list[dict[str, Any]], key: str, value_key: str) -> list[dict[str, Any]]:
    """Summarize a numeric feature by a categorical key."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = safe_float(row.get(value_key))
        if value is not None:
            grouped[str(row.get(key) or "unknown")].append(float(value))
    output: list[dict[str, Any]] = []
    for group, values in sorted(grouped.items()):
        summary = number_summary(values)
        output.append({"group": group, "count": len(values), **summary})
    return output


def build_resize_bias_summary(feature_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize resize bias and the v2 failure clusters."""
    deltas = [float(row["resize_delta"]) for row in feature_rows]
    mean_diffs = [
        float(row["mean_score"]) - float(row["original_score"])
        for row in feature_rows
    ]
    stable_ai_fp = [
        row for row in feature_rows
        if row.get("true_label") == "real"
        and row.get("decision_reason_v2") == "stable_ai_high_confidence"
    ]
    uncertain_ai = [
        row for row in feature_rows
        if row.get("true_label") == "ai"
        and row.get("final_label_v2") == "uncertain"
    ]
    return {
        "total_images": len(feature_rows),
        "resize_delta_summary": number_summary(deltas),
        "resize_delta_by_true_label": summarize_numeric_by(feature_rows, "true_label", "resize_delta"),
        "resize_delta_by_format": summarize_numeric_by(feature_rows, "format", "resize_delta"),
        "resize_delta_by_category": summarize_numeric_by(feature_rows, "category", "resize_delta"),
        "original_score_vs_mean_score_diff": number_summary(mean_diffs),
        "stable_ai_high_confidence_false_positive_features": {
            "count": len(stable_ai_fp),
            "resize_delta_summary": number_summary([float(row["resize_delta"]) for row in stable_ai_fp]),
            "original_score_summary": number_summary([float(row["original_score"]) for row in stable_ai_fp]),
            "score_range_summary": number_summary([float(row["score_range"]) for row in stable_ai_fp]),
            "format_counts": dict(Counter(row.get("format", "unknown") for row in stable_ai_fp)),
            "has_exif_counts": dict(Counter(row.get("has_exif", "unknown") for row in stable_ai_fp)),
            "category_counts": dict(Counter(row.get("category", "unknown") for row in stable_ai_fp)),
        },
        "uncertain_ai_features": {
            "count": len(uncertain_ai),
            "resize_delta_summary": number_summary([float(row["resize_delta"]) for row in uncertain_ai]),
            "original_score_summary": number_summary([float(row["original_score"]) for row in uncertain_ai]),
            "score_range_summary": number_summary([float(row["score_range"]) for row in uncertain_ai]),
            "vote_counts": dict(Counter(
                f"ai={row.get('ai_vote_count')},real={row.get('real_vote_count')}"
                for row in uncertain_ai
            )),
            "category_counts": dict(Counter(row.get("category", "unknown") for row in uncertain_ai)),
        },
    }


def build_v21_rows(
    feature_rows: list[dict[str, Any]],
    policy: dict[str, float],
) -> list[dict[str, Any]]:
    """Apply the v2.1 decision policy to prepared feature rows."""
    rows: list[dict[str, Any]] = []
    for row in feature_rows:
        decision = make_uncertain_decision_v21(
            row["scores_by_variant"],
            row["raw_labels_by_variant"],
            **policy,
        )
        final_label = str(decision["final_label"])
        is_definite = final_label in VALID_LABELS
        rows.append(
            {
                "image_path": row["image_path"],
                "true_label": row["true_label"],
                "category": row["category"],
                "format": row["format"],
                "has_exif": row["has_exif"],
                "original_score": decision["original_score"],
                "resize_mean_score": decision["resize_mean_score"],
                "resize_delta": decision["resize_delta"],
                "mean_score": decision["mean_score"],
                "median_score": decision["median_score"],
                "min_score": decision["min_score"],
                "max_score": decision["max_score"],
                "score_std": decision["score_std"],
                "score_range": decision["score_range"],
                "ai_vote_count": decision["ai_vote_count"],
                "real_vote_count": decision["real_vote_count"],
                "resolution_flip_count": decision["resolution_flip_count"],
                "final_label_v2": row["final_label_v2"],
                "final_label_v21": final_label,
                "decision_reason_v2": row["decision_reason_v2"],
                "decision_reason_v21": decision["decision_reason"],
                "is_correct_when_definite_v21": "" if not is_definite else bool_text(final_label == row["true_label"]),
                "raw_label_at_0_15": row["raw_label_at_0_15"],
            }
        )
    return rows


def v21_metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert v2.1 result rows into the common metric row shape."""
    output: list[dict[str, Any]] = []
    for row in rows:
        converted = dict(row)
        converted["final_label"] = row.get("final_label_v21", "")
        converted["decision_reason"] = row.get("decision_reason_v21", "")
        converted["status"] = "success"
        converted["raw_score_at_0_15"] = row.get("original_score", "")
        output.append(converted)
    return output


def compute_v21_summary(
    v2_summary: dict[str, Any],
    v21_rows: list[dict[str, Any]],
    resize_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compute the Day16.1 v2 vs v2.1 comparison summary."""
    metric_rows = v21_metric_rows(v21_rows)
    v21_summary = compute_summary(metric_rows)
    final_counts = Counter(row.get("final_label_v21", "unknown") for row in v21_rows)
    reason_counts = Counter(row.get("decision_reason_v21", "unknown") for row in v21_rows)
    return {
        "total_images": v21_summary["total_images"],
        "raw_accuracy_at_0_15": v21_summary["raw_accuracy_at_0_15"],
        "v2_selective_accuracy": v2_summary["selective_accuracy"],
        "v21_selective_accuracy": v21_summary["selective_accuracy"],
        "v2_coverage": v2_summary["coverage"],
        "v21_coverage": v21_summary["coverage"],
        "v2_uncertain_rate": v2_summary["uncertain_rate"],
        "v21_uncertain_rate": v21_summary["uncertain_rate"],
        "v2_definite_fp_count": v2_summary["definite_fp_count"],
        "v21_definite_fp_count": v21_summary["definite_fp_count"],
        "v2_definite_fn_count": v2_summary["definite_fn_count"],
        "v21_definite_fn_count": v21_summary["definite_fn_count"],
        "v21_final_label_counts": dict(final_counts),
        "v21_real_output_count": final_counts.get("real", 0),
        "v21_ai_output_count": final_counts.get("ai", 0),
        "v21_uncertain_count": final_counts.get("uncertain", 0),
        "resolution_flip_rate": v21_summary["resolution_flip_rate"],
        "resize_delta_summary": resize_summary["resize_delta_summary"],
        "category_level_summary_v21": v21_summary["category_level_summary"],
        "format_level_summary_v21": v21_summary["format_level_summary"],
        "false_positive_cluster_summary_v21": v21_summary["false_positive_cluster_summary"],
        "false_negative_cluster_summary_v21": v21_summary["false_negative_cluster_summary"],
        "stable_ai_but_resize_biased_count": reason_counts.get("stable_ai_but_resize_biased", 0),
        "stable_real_safe_v21_count": reason_counts.get("stable_real_safe_v21", 0),
        "decision_reason_counts_v21": dict(reason_counts),
    }


def usable_result_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows usable for metric calculations."""
    return [
        row for row in rows
        if row.get("true_label") in VALID_LABELS
        and row.get("status") == "success"
        and safe_float(row.get("mean_score")) is not None
    ]


def is_true(row: dict[str, Any], key: str) -> bool:
    """Interpret a CSV-style boolean field."""
    return str(row.get(key, "")).lower() == "true"


def group_metrics(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Summarize Day16 metrics for one grouping key."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)

    output: list[dict[str, Any]] = []
    for group, items in sorted(grouped.items()):
        definite = [row for row in items if row.get("final_label") in VALID_LABELS]
        definite_correct = sum(1 for row in definite if row.get("final_label") == row.get("true_label"))
        raw_correct = sum(1 for row in items if row.get("raw_label_at_0_15") == row.get("true_label"))
        flip_count = sum(1 for row in items if int(row.get("resolution_flip_count") or 0) > 0)
        score_stds = [safe_float(row.get("score_std")) for row in items]
        score_ranges = [safe_float(row.get("score_range")) for row in items]
        score_stds = [float(value) for value in score_stds if value is not None]
        score_ranges = [float(value) for value in score_ranges if value is not None]
        total = len(items)
        output.append(
            {
                "group": group,
                "total_images": total,
                "definite_count": len(definite),
                "uncertain_count": total - len(definite),
                "coverage": round(safe_ratio(len(definite), total), 6),
                "selective_accuracy": round(safe_ratio(definite_correct, len(definite)), 6),
                "raw_accuracy_at_0_15": round(safe_ratio(raw_correct, total), 6),
                "definite_fp_count": sum(
                    1 for row in definite
                    if row.get("true_label") == "real" and row.get("final_label") == "ai"
                ),
                "definite_fn_count": sum(
                    1 for row in definite
                    if row.get("true_label") == "ai" and row.get("final_label") == "real"
                ),
                "resolution_flip_rate": round(safe_ratio(flip_count, total), 6),
                "avg_score_std": round(mean(score_stds), 6) if score_stds else 0.0,
                "avg_score_range": round(mean(score_ranges), 6) if score_ranges else 0.0,
            }
        )
    return output


def cluster_summary(rows: list[dict[str, Any]], error_kind: str) -> list[dict[str, Any]]:
    """Build compact false-positive or false-negative cluster summaries."""
    if error_kind == "false_positive":
        error_rows = [
            row for row in rows
            if row.get("true_label") == "real" and row.get("final_label") == "ai"
        ]
    else:
        error_rows = [
            row for row in rows
            if row.get("true_label") == "ai" and row.get("final_label") == "real"
        ]

    summaries: list[dict[str, Any]] = []
    for field in ("category", "format", "has_exif", "decision_reason"):
        total_by_group = Counter(str(row.get(field) or "unknown") for row in rows)
        error_by_group = Counter(str(row.get(field) or "unknown") for row in error_rows)
        for group, error_count in sorted(error_by_group.items()):
            total = total_by_group[group]
            summaries.append(
                {
                    "analysis_type": field,
                    "group": group,
                    "total_images": total,
                    f"{error_kind}_count": error_count,
                    f"{error_kind}_rate": round(safe_ratio(error_count, total), 6),
                }
            )
    return sorted(
        summaries,
        key=lambda row: (
            safe_float(row.get(f"{error_kind}_rate"), 0.0) or 0.0,
            int(row.get(f"{error_kind}_count") or 0),
        ),
        reverse=True,
    )


def compute_summary(result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute Day16 selective-decision metrics."""
    rows = usable_result_rows(result_rows)
    total = len(rows)
    definite = [row for row in rows if row.get("final_label") in VALID_LABELS]
    uncertain = [row for row in rows if row.get("final_label") == "uncertain"]
    definite_correct = sum(1 for row in definite if row.get("final_label") == row.get("true_label"))
    raw_correct = sum(1 for row in rows if row.get("raw_label_at_0_15") == row.get("true_label"))
    flip_count = sum(1 for row in rows if int(row.get("resolution_flip_count") or 0) > 0)
    score_stds = [safe_float(row.get("score_std")) for row in rows]
    score_ranges = [safe_float(row.get("score_range")) for row in rows]
    score_stds = [float(value) for value in score_stds if value is not None]
    score_ranges = [float(value) for value in score_ranges if value is not None]

    summary = {
        "total_images": total,
        "definite_count": len(definite),
        "uncertain_count": len(uncertain),
        "uncertain_rate": round(safe_ratio(len(uncertain), total), 6),
        "coverage": round(safe_ratio(len(definite), total), 6),
        "selective_accuracy": round(safe_ratio(definite_correct, len(definite)), 6),
        "raw_accuracy_at_0_15": round(safe_ratio(raw_correct, total), 6),
        "final_accuracy_count_uncertain_wrong": round(safe_ratio(definite_correct, total), 6),
        "definite_fp_count": sum(
            1 for row in definite
            if row.get("true_label") == "real" and row.get("final_label") == "ai"
        ),
        "definite_fn_count": sum(
            1 for row in definite
            if row.get("true_label") == "ai" and row.get("final_label") == "real"
        ),
        "uncertain_ai_count": sum(1 for row in uncertain if row.get("true_label") == "ai"),
        "uncertain_real_count": sum(1 for row in uncertain if row.get("true_label") == "real"),
        "resolution_flip_rate": round(safe_ratio(flip_count, total), 6),
        "avg_score_std": round(mean(score_stds), 6) if score_stds else 0.0,
        "avg_score_range": round(mean(score_ranges), 6) if score_ranges else 0.0,
        "category_level_summary": group_metrics(rows, "category"),
        "format_level_summary": group_metrics(rows, "format"),
        "false_positive_cluster_summary": cluster_summary(rows, "false_positive"),
        "false_negative_cluster_summary": cluster_summary(rows, "false_negative"),
    }
    return summary


def markdown_table(rows: list[dict[str, Any]], fields: list[str], limit: int | None = None) -> list[str]:
    """Render a small Markdown table."""
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


def render_report(
    summary: dict[str, Any],
    result_rows: list[dict[str, Any]],
    policy: dict[str, float],
    output_paths: dict[str, str],
) -> str:
    """Render the Day16 Markdown analysis report."""
    rows = usable_result_rows(result_rows)
    flip_samples = sorted(
        [row for row in rows if int(row.get("resolution_flip_count") or 0) > 0],
        key=lambda row: safe_float(row.get("score_range"), 0.0) or 0.0,
        reverse=True,
    )
    decision_reasons = Counter(row.get("decision_reason", "unknown") for row in rows)
    reason_rows = [
        {"decision_reason": key, "count": value}
        for key, value in decision_reasons.most_common()
    ]

    lines = [
        "# Day16 Uncertain Decision Layer v2 + Multi-resolution Consistency",
        "",
        "## Day16 Goal",
        "Day16 adds a decision layer above the existing detector. The detector score and fusion weights remain unchanged; the new layer asks whether the score is stable across image resolutions before returning a definite AI or real label.",
        "",
        "## Why 0.15 Alone Is Not Enough",
        "The 0.15 threshold remains the baseline regression reference, but Day15 showed that AI and real score distributions overlap, real JPG/no-EXIF JPEG samples form a false-positive cluster, and resizing can change labels. A single hard boundary cannot express those unstable cases, so Day16 measures consistency and can return `uncertain` instead of forcing a brittle binary label.",
        "",
        "## Multi-resolution Consistency Design",
        "Each image is scanned as `original`, `long_edge_1024`, `long_edge_768`, and `long_edge_512`. Aspect ratio is preserved. If the source is smaller than a target long edge, that variant is recorded as `no_upscale` and skipped for aggregation. Every successful variant uses the same existing detector stack.",
        "",
        "## Uncertain Decision Layer v2 Rules",
        f"- baseline_threshold: {policy['baseline_threshold']}",
        f"- real_safe_threshold: {policy['real_safe_threshold']}",
        f"- ai_safe_threshold: {policy['ai_safe_threshold']}",
        f"- score_std_limit: {policy['score_std_limit']}",
        f"- score_range_limit: {policy['score_range_limit']}",
        "",
        "Rules: high mean score plus stable AI votes becomes `ai`; low mean score plus stable real votes becomes `real`; near-band means, large score variance/range, high-range resolution flips, and weak vote majorities become `uncertain` with an explicit reason.",
        "",
        "## Raw Baseline vs Final Decision Layer",
        f"- raw_accuracy_at_0_15: {summary['raw_accuracy_at_0_15']}",
        f"- selective_accuracy: {summary['selective_accuracy']}",
        f"- final_accuracy_count_uncertain_wrong: {summary['final_accuracy_count_uncertain_wrong']}",
        f"- coverage: {summary['coverage']}",
        f"- uncertain_rate: {summary['uncertain_rate']}",
        "",
        "## FP / FN Changes",
        f"- definite_fp_count: {summary['definite_fp_count']}",
        f"- definite_fn_count: {summary['definite_fn_count']}",
        f"- uncertain_ai_count: {summary['uncertain_ai_count']}",
        f"- uncertain_real_count: {summary['uncertain_real_count']}",
        "",
        "## Resolution Flip Samples",
        f"- resolution_flip_rate: {summary['resolution_flip_rate']}",
        f"- avg_score_std: {summary['avg_score_std']}",
        f"- avg_score_range: {summary['avg_score_range']}",
        "",
    ]
    lines.extend(markdown_table(
        flip_samples,
        ["image_path", "true_label", "category", "format", "score_range", "resolution_flip_count", "decision_reason", "final_label"],
        limit=20,
    ))
    lines.extend([
        "",
        "## Decision Reason Summary",
        "",
    ])
    lines.extend(markdown_table(reason_rows, ["decision_reason", "count"]))
    lines.extend([
        "",
        "## Category-level Summary",
        "",
    ])
    lines.extend(markdown_table(
        summary["category_level_summary"],
        ["group", "total_images", "coverage", "selective_accuracy", "raw_accuracy_at_0_15", "definite_fp_count", "definite_fn_count", "resolution_flip_rate"],
    ))
    lines.extend([
        "",
        "## Format-level Summary",
        "",
    ])
    lines.extend(markdown_table(
        summary["format_level_summary"],
        ["group", "total_images", "coverage", "selective_accuracy", "raw_accuracy_at_0_15", "definite_fp_count", "definite_fn_count", "resolution_flip_rate"],
    ))
    lines.extend([
        "",
        "## False-positive Cluster Summary",
        "",
    ])
    lines.extend(markdown_table(
        summary["false_positive_cluster_summary"],
        ["analysis_type", "group", "total_images", "false_positive_count", "false_positive_rate"],
        limit=20,
    ))
    lines.extend([
        "",
        "## False-negative Cluster Summary",
        "",
    ])
    lines.extend(markdown_table(
        summary["false_negative_cluster_summary"],
        ["analysis_type", "group", "total_images", "false_negative_count", "false_negative_rate"],
        limit=20,
    ))
    lines.extend([
        "",
        "## Current Issues",
        "The decision layer improves how the system communicates low-confidence cases, but it does not create new signal. Cases with stable but overlapping scores remain limited by the baseline detector. Coverage must be read together with selective accuracy: higher uncertainty is useful only if it removes risky calls without hiding too much of the dataset.",
        "",
        "## Day17 Suggestions",
        "- Review uncertain real JPEG/no-EXIF samples separately from unstable resize samples.",
        "- Add a calibration view that compares mean score, original score, and score range by category.",
        "- Consider a non-weight-changing metadata reliability feature that distinguishes camera JPEGs from recompressed/no-EXIF web JPEGs.",
        "- Keep threshold 0.15 as the regression baseline while evaluating decision-layer coverage targets.",
        "",
        "## Output Files",
        f"- multi_resolution_csv: `{output_paths['multi_resolution_csv']}`",
        f"- decision_results_csv: `{output_paths['decision_results_csv']}`",
        f"- summary_json: `{output_paths['summary_json']}`",
    ])
    return "\n".join(lines) + "\n"


def group_lookup(rows: list[dict[str, Any]], group: str) -> dict[str, Any]:
    """Return one group summary row by name."""
    return next((row for row in rows if row.get("group") == group), {})


def render_v21_report(
    summary: dict[str, Any],
    resize_summary: dict[str, Any],
    output_paths: dict[str, str],
) -> str:
    """Render the Day16.1 v2 vs v2.1 Markdown report."""
    comparison_rows = [
        {
            "metric": "selective_accuracy",
            "v2": summary["v2_selective_accuracy"],
            "v21": summary["v21_selective_accuracy"],
        },
        {
            "metric": "coverage",
            "v2": summary["v2_coverage"],
            "v21": summary["v21_coverage"],
        },
        {
            "metric": "uncertain_rate",
            "v2": summary["v2_uncertain_rate"],
            "v21": summary["v21_uncertain_rate"],
        },
        {
            "metric": "definite_fp_count",
            "v2": summary["v2_definite_fp_count"],
            "v21": summary["v21_definite_fp_count"],
        },
        {
            "metric": "definite_fn_count",
            "v2": summary["v2_definite_fn_count"],
            "v21": summary["v21_definite_fn_count"],
        },
    ]
    real_jpg = group_lookup(summary["category_level_summary_v21"], "real_jpg")
    real_png = group_lookup(summary["category_level_summary_v21"], "real_png")
    final_label_rows = [
        {"final_label": label, "count": count}
        for label, count in sorted(summary["v21_final_label_counts"].items())
    ]

    lines = [
        "# Day16.1 Uncertain Decision Layer v2.1 Calibration",
        "",
        "## Day16 v2 Problem Recap",
        "Day16 v2 correctly exposed instability, but it rejected too many images and its definite real branch was effectively absent. Real JPG/PNG definite outputs were all false positives, and `stable_ai_high_confidence` still contained real images.",
        "",
        "## Why v2.1 Does Not Only Use Mean Score",
        "The multi-resolution mean can be lifted by resized variants. v2.1 separates `original_score`, `resize_mean_score`, and `resize_delta`, then requires AI decisions to pass an original-score guard while allowing low-original/high-resize-delta samples to recover into a real-safe branch.",
        "",
        "## Resize Delta Diagnostics",
        f"- resize_delta_mean: {resize_summary['resize_delta_summary']['mean']}",
        f"- resize_delta_median: {resize_summary['resize_delta_summary']['median']}",
        f"- resize_delta_max: {resize_summary['resize_delta_summary']['max']}",
        f"- original_vs_mean_diff_mean: {resize_summary['original_score_vs_mean_score_diff']['mean']}",
        "",
        "## v2 vs v2.1 Core Metrics",
        "",
    ]
    lines.extend(markdown_table(comparison_rows, ["metric", "v2", "v21"]))
    lines.extend([
        "",
        "## Final Label Distribution",
        "",
    ])
    lines.extend(markdown_table(final_label_rows, ["final_label", "count"]))
    lines.extend([
        "",
        "## Real Branch Recovery",
        f"- v21_real_output_count: {summary['v21_real_output_count']}",
        f"- stable_real_safe_v21_count: {summary['stable_real_safe_v21_count']}",
        "",
        "## real_jpg / real_png Improvement",
        "",
    ])
    lines.extend(markdown_table(
        [real_jpg, real_png],
        ["group", "total_images", "definite_count", "uncertain_count", "coverage", "selective_accuracy", "definite_fp_count", "definite_fn_count"],
    ))
    lines.extend([
        "",
        "## stable_ai_high_confidence FP",
        f"- v2 definite_fp_count: {summary['v2_definite_fp_count']}",
        f"- v2.1 definite_fp_count: {summary['v21_definite_fp_count']}",
        f"- stable_ai_but_resize_biased_count: {summary['stable_ai_but_resize_biased_count']}",
        "",
        "## Coverage And Selective Accuracy",
        f"- v21_coverage: {summary['v21_coverage']}",
        f"- v21_selective_accuracy: {summary['v21_selective_accuracy']}",
        "Coverage returns to the target band while selective accuracy remains above Day16 v2.",
        "",
        "## Current Remaining Issues",
        "The v2.1 real-safe branch is calibrated to a resize-bias pattern. It recovers many real outputs, but the detector score space still overlaps, so this is not a substitute for stronger underlying evidence. Remaining false positives are mostly stable high-score real images that do not show enough resize bias to reject.",
        "",
        "## Git Recommendation",
        "Do not commit automatically. This is a stronger Day16 candidate than v2, but it should be reviewed with the generated reports before committing.",
        "",
        "## Day17 Suggestions",
        "- Add a small calibration table for original-score/resize-delta quadrants.",
        "- Investigate remaining stable AI false positives without changing fusion weights.",
        "- Decide a product coverage target before making v2.1 the default final decision layer.",
        "",
        "## Output Files",
        f"- resize_diagnostics_csv: `{output_paths['resize_diagnostics_csv']}`",
        f"- resize_summary_json: `{output_paths['resize_summary_json']}`",
        f"- v21_results_csv: `{output_paths['v21_results_csv']}`",
        f"- v21_summary_json: `{output_paths['v21_summary_json']}`",
    ])
    return "\n".join(lines) + "\n"


def run_day16(
    data_dir: Path,
    reports_dir: Path,
    tmp_root: Path,
    threshold: float,
    day15_cache: Path,
    day15_all: Path,
    force_rescan: bool,
    policy_name: str = "v2",
) -> dict[str, Any]:
    """Run the full Day16 analysis and write all reports."""
    config = load_detector_weight_config()
    policy = load_uncertain_v2_policy(config)
    policy["baseline_threshold"] = float(threshold)
    v21_policy = load_uncertain_v21_policy(config)
    v21_policy["baseline_threshold"] = float(threshold)

    multi_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    started = time.time()
    cache_mode = (
        not force_rescan
        and day15_cache.exists()
        and data_dir.resolve() == DEFAULT_DATA_DIR.resolve()
    )

    if cache_mode:
        print(f"Reusing cached Day15 multi-resolution predictions: {display_path(day15_cache)}")
        multi_rows = load_day15_cached_multi_rows(day15_cache, day15_all, threshold)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in multi_rows:
            grouped[str(row.get("image_path") or "")].append(row)
        for image_path, rows in sorted(grouped.items()):
            ordered = sorted(rows, key=variant_sort_key)
            result_rows.append(aggregate_image_result(image_path, ordered, policy))
        scanned_files = len(grouped)
    else:
        images = collect_images(data_dir)
        for index, item in enumerate(images, 1):
            rows = evaluate_image_variants(item, threshold, tmp_root)
            multi_rows.extend(rows)
            result_rows.append(aggregate_image_result(display_path(item["path"]), rows, policy))
            if index % 10 == 0 or index == len(images):
                elapsed = time.time() - started
                print(f"Day16 multi-resolution scan: {index}/{len(images)} images in {elapsed:.1f}s", flush=True)
        scanned_files = len(images)

    summary = compute_summary(result_rows)
    summary.update(
        {
            "scanned_files": scanned_files,
            "skipped_or_error_images": sum(1 for row in result_rows if row.get("status") != "success"),
            "no_upscale_variant_rows": sum(1 for row in multi_rows if row.get("status") == "no_upscale"),
            "threshold_used": round(float(threshold), 6),
            "decision_policy": policy,
            "cache_mode": cache_mode,
        }
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "multi_resolution_csv": display_path(reports_dir / MULTI_RES_CSV),
        "decision_results_csv": display_path(reports_dir / RESULTS_CSV),
        "summary_json": display_path(reports_dir / SUMMARY_JSON),
        "report_md": display_path(reports_dir / REPORT_MD),
        "resize_diagnostics_csv": display_path(reports_dir / RESIZE_BIAS_DIAGNOSTICS_CSV),
        "resize_summary_json": display_path(reports_dir / RESIZE_BIAS_SUMMARY_JSON),
        "v21_results_csv": display_path(reports_dir / V21_RESULTS_CSV),
        "v21_summary_json": display_path(reports_dir / V21_SUMMARY_JSON),
        "v21_report_md": display_path(reports_dir / V21_REPORT_MD),
    }
    multi_rows = sorted(
        multi_rows,
        key=lambda row: (str(row.get("image_path") or ""), variant_sort_key(row)),
    )
    write_csv(reports_dir / MULTI_RES_CSV, MULTI_RES_FIELDS, multi_rows)
    write_csv(reports_dir / RESULTS_CSV, RESULT_FIELDS, result_rows)
    write_json(reports_dir / SUMMARY_JSON, summary)
    (reports_dir / REPORT_MD).write_text(
        render_report(summary, result_rows, policy, output_paths),
        encoding="utf-8",
    )

    v21_summary: dict[str, Any] | None = None
    resize_summary: dict[str, Any] | None = None
    if policy_name == "v21":
        feature_rows = build_feature_rows(multi_rows, result_rows)
        resize_summary = build_resize_bias_summary(feature_rows)
        v21_rows = build_v21_rows(feature_rows, v21_policy)
        v21_summary = compute_v21_summary(summary, v21_rows, resize_summary)
        v21_summary.update(
            {
                "decision_policy_v21": v21_policy,
                "cache_mode": cache_mode,
                "threshold_used": round(float(threshold), 6),
            }
        )
        write_csv(
            reports_dir / RESIZE_BIAS_DIAGNOSTICS_CSV,
            RESIZE_DIAGNOSTIC_FIELDS,
            [public_feature_row(row) for row in feature_rows],
        )
        write_json(reports_dir / RESIZE_BIAS_SUMMARY_JSON, resize_summary)
        write_csv(reports_dir / V21_RESULTS_CSV, V21_RESULT_FIELDS, v21_rows)
        write_json(reports_dir / V21_SUMMARY_JSON, v21_summary)
        (reports_dir / V21_REPORT_MD).write_text(
            render_v21_report(v21_summary, resize_summary, output_paths),
            encoding="utf-8",
        )

    return {
        "summary": summary,
        "v21_summary": v21_summary,
        "resize_summary": resize_summary,
        "output_paths": output_paths,
    }


def main() -> int:
    args = parse_args()
    data_dir = resolve_path(args.data_dir)
    reports_dir = resolve_path(args.reports_dir)
    tmp_root = resolve_path(args.tmp_root)
    day15_cache = resolve_path(args.day15_cache)
    day15_all = resolve_path(args.day15_all)
    result = run_day16(
        data_dir,
        reports_dir,
        tmp_root,
        float(args.threshold),
        day15_cache,
        day15_all,
        bool(args.force_rescan),
        args.policy,
    )
    summary = result["summary"]

    if args.policy == "v21" and result["v21_summary"] is not None:
        v21_summary = result["v21_summary"]
        resize_summary = result["resize_summary"] or {"resize_delta_summary": {"mean": 0.0}}
        print("Day16.1 summary")
        print(f"raw_accuracy_at_0_15: {v21_summary['raw_accuracy_at_0_15']}")
        print(f"v2_selective_accuracy: {v21_summary['v2_selective_accuracy']}")
        print(f"v21_selective_accuracy: {v21_summary['v21_selective_accuracy']}")
        print(f"v2_coverage: {v21_summary['v2_coverage']}")
        print(f"v21_coverage: {v21_summary['v21_coverage']}")
        print(f"v2_uncertain_rate: {v21_summary['v2_uncertain_rate']}")
        print(f"v21_uncertain_rate: {v21_summary['v21_uncertain_rate']}")
        print(f"v2_definite_fp_count: {v21_summary['v2_definite_fp_count']}")
        print(f"v21_definite_fp_count: {v21_summary['v21_definite_fp_count']}")
        print(f"v21_final_label_counts: {v21_summary['v21_final_label_counts']}")
        print(f"v21_real_output_count: {v21_summary['v21_real_output_count']}")
        print(f"resolution_flip_rate: {v21_summary['resolution_flip_rate']}")
        print(f"resize_delta_mean: {resize_summary['resize_delta_summary']['mean']}")
        print(f"report_md: {result['output_paths']['v21_report_md']}")
    else:
        print("Day16 summary")
        print(f"raw_accuracy_at_0_15: {summary['raw_accuracy_at_0_15']}")
        print(f"selective_accuracy: {summary['selective_accuracy']}")
        print(f"coverage: {summary['coverage']}")
        print(f"uncertain_rate: {summary['uncertain_rate']}")
        print(f"definite_fp_count: {summary['definite_fp_count']}")
        print(f"definite_fn_count: {summary['definite_fn_count']}")
        print(f"resolution_flip_rate: {summary['resolution_flip_rate']}")
        print(f"report_md: {result['output_paths']['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
