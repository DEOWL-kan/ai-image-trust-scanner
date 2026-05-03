from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.detection_service import detect_image_for_api  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
AI_LABELS = {"ai", "ai_generated", "generated", "likely_ai", "synthetic"}
REAL_LABELS = {"real", "real_photo", "authentic", "likely_real", "human", "camera"}
UNCERTAIN_LABELS = {
    "uncertain",
    "unsure",
    "needs_review",
    "review",
    "unknown",
    "none",
    "",
}

RESULTS_JSON = "day23_benchmark_results.json"
SUMMARY_JSON = "day23_benchmark_summary.json"
RESULTS_CSV = "day23_benchmark_results.csv"
REPORT_MD = "day23_benchmark_protocol_v2_report.md"
SKIPPED_CSV = "day23_skipped_samples.csv"
DISCOVERY_JSON = "day23_dataset_discovery_report.json"

AI_DIR_ALLOWLIST = {
    "ai",
    "ai_jpg",
    "ai_png",
    "ai_webp",
    "samples_ai",
    "generated_ai",
    "synthetic_ai",
    "ai_resized",
    "ai_resolution",
    "ai_format",
    "format_ai",
    "resolution_ai",
}
REAL_DIR_ALLOWLIST = {
    "real",
    "real_jpg",
    "real_png",
    "real_webp",
    "samples_real",
    "camera_real",
    "authentic_real",
    "real_resized",
    "real_resolution",
    "real_format",
    "format_real",
    "resolution_real",
}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "frontend",
    "reports",
    "benchmark_outputs",
    "static",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Benchmark Protocol v2 for AI Image Trust Scanner."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("data/test_images"),
        help="Dataset root containing ai/ and real/ folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/benchmark_outputs/day23"),
        help="Directory for benchmark JSON and CSV outputs.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/day23"),
        help="Directory for the Markdown benchmark report.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_label(label: Any) -> str:
    """Normalize detector labels into ai, real, or uncertain."""
    if label is None:
        return "uncertain"
    value = str(label).strip().lower()
    if value in AI_LABELS:
        return "ai"
    if value in REAL_LABELS:
        return "real"
    if value in UNCERTAIN_LABELS:
        return "uncertain"
    return "uncertain"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 4)


def safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def flatten_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)


def file_ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "unknown"


def format_group(ext: str) -> str:
    value = ext.lower().lstrip(".")
    if value in {"jpg", "jpeg"}:
        return "jpg"
    if value == "png":
        return "png"
    if value == "webp":
        return "webp"
    return "others"


def split_label_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[_\-\s]+", value.strip().lower()) if token]


def is_excluded_path(path: Path, dataset_root: Path) -> bool:
    try:
        relative_parts = path.relative_to(dataset_root).parts
    except ValueError:
        relative_parts = path.parts
    return any(part.lower() in EXCLUDED_DIR_NAMES for part in relative_parts[:-1])


def benchmark_group_for(path: Path) -> str:
    text_parts = [part.lower() for part in path.parts]
    joined = " ".join(text_parts)
    if "benchmark_outputs" in text_parts:
        return "benchmark_output"
    if any(token in joined for token in ("resolution", "resized", "resize", "scale")):
        return "resolution_variant"
    if any(token in joined for token in ("format", "jpg", "jpeg", "png", "webp")):
        return "format_variant"
    if any(token in text_parts for token in ("test_images", "samples", "samples_ai", "samples_real")):
        return "original_test_images"
    return "unknown_group"


def scenario_for(image_path: Path, label_dir: Path) -> str:
    rel = image_path.relative_to(label_dir)
    if len(rel.parts) >= 2:
        return rel.parts[0]
    return "unknown"


def infer_label_from_dir_name(name: str) -> str | None:
    value = name.strip().lower()
    tokens = split_label_tokens(value)
    if value in AI_DIR_ALLOWLIST or "ai" in tokens:
        return "ai"
    if value in REAL_DIR_ALLOWLIST or "real" in tokens:
        return "real"
    return None


def infer_label_from_filename(filename: str) -> str | None:
    tokens = split_label_tokens(Path(filename).stem)
    if not tokens:
        return None
    first = tokens[0]
    if first == "ai":
        return "ai"
    if first == "real":
        return "real"
    return None


def infer_label_anchor(image_path: Path, dataset_root: Path) -> tuple[str | None, Path | None, str]:
    try:
        relative = image_path.relative_to(dataset_root)
    except ValueError:
        relative = image_path
    directory_parts = relative.parts[:-1]

    exact_matches: list[tuple[str, int]] = []
    loose_matches: list[tuple[str, int]] = []
    for index, part in enumerate(directory_parts):
        lowered = part.lower()
        if lowered in {"ai", "real"}:
            exact_matches.append((lowered, index))
            continue
        inferred = infer_label_from_dir_name(part)
        if inferred:
            loose_matches.append((inferred, index))

    matches = exact_matches or loose_matches
    if matches:
        ground_truth, index = matches[-1]
        return ground_truth, dataset_root.joinpath(*directory_parts[: index + 1]), "path_segment"

    filename_label = infer_label_from_filename(image_path.name)
    if filename_label:
        fallback_anchor = image_path.parent.parent if image_path.parent != dataset_root else image_path.parent
        return filename_label, fallback_anchor, "filename_prefix"

    return None, None, "unknown_label"


def scenario_from_anchor(image_path: Path, label_anchor: Path, label_source: str) -> str:
    if label_source == "filename_prefix":
        parent = image_path.parent
        return parent.name if parent.name else "unknown"
    try:
        rel = image_path.relative_to(label_anchor)
    except ValueError:
        return "unknown"
    if len(rel.parts) >= 2:
        return rel.parts[0]
    return "unknown"


def describe_dataset_tree(dataset_root: Path) -> dict[str, Any]:
    directories: list[Path] = []
    if dataset_root.exists():
        directories = sorted(
            path
            for path in dataset_root.rglob("*")
            if path.is_dir() and not is_excluded_path(path / "placeholder.txt", dataset_root)
        )

    def depth(path: Path) -> int:
        try:
            return len(path.relative_to(dataset_root).parts)
        except ValueError:
            return 999

    image_dirs = sorted(
        {
            path.parent
            for path in dataset_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not is_excluded_path(path, dataset_root)
        }
    ) if dataset_root.exists() else []

    return {
        "dataset_root": display_path(dataset_root),
        "root_exists": dataset_root.exists(),
        "first_level_directories": [
            display_path(path) for path in directories if depth(path) == 1
        ],
        "second_level_directories": [
            display_path(path) for path in directories if depth(path) == 2
        ],
        "image_directories": [
            {
                "path": display_path(path),
                "image_count": sum(
                    1
                    for item in path.iterdir()
                    if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
                ),
            }
            for path in image_dirs
        ],
    }


def discover_dataset_images(dataset_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    skipped_unknown_label_count = 0
    skipped_samples: list[dict[str, Any]] = []
    ai_label_dirs: set[str] = set()
    real_label_dirs: set[str] = set()
    recognized_label_anchors: dict[str, Counter[str]] = {
        "ai": Counter(),
        "real": Counter(),
    }
    all_parent_dirs: Counter[str] = Counter()
    skipped_parent_dirs: Counter[str] = Counter()

    image_paths = (
        sorted(
            path
            for path in dataset_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not is_excluded_path(path, dataset_root)
        )
        if dataset_root.exists()
        else []
    )

    for image_path in image_paths:
        parent_dir = display_path(image_path.parent)
        all_parent_dirs[parent_dir] += 1
        ground_truth, label_anchor, label_source = infer_label_anchor(image_path, dataset_root)
        if ground_truth is None or label_anchor is None:
            skipped_unknown_label_count += 1
            skipped_parent_dirs[parent_dir] += 1
            try:
                relative_path = str(image_path.relative_to(dataset_root))
            except ValueError:
                relative_path = display_path(image_path)
            skipped_samples.append(
                {
                    "image_path": display_path(image_path),
                    "filename": image_path.name,
                    "parent_dir": parent_dir,
                    "relative_path": relative_path,
                    "reason": (
                        "unknown_ground_truth_label; label lost during preprocessing; "
                        "need preserve ai/real in output path or metadata"
                    ),
                }
            )
            continue

        if ground_truth == "ai":
            ai_label_dirs.add(display_path(label_anchor))
        else:
            real_label_dirs.add(display_path(label_anchor))
        anchor_key = f"{display_path(label_anchor)} [{label_source}]"
        recognized_label_anchors[ground_truth][anchor_key] += 1

        ext = file_ext(image_path)
        samples.append(
            {
                "image_path": image_path,
                "filename": image_path.name,
                "ground_truth": ground_truth,
                "scenario": scenario_from_anchor(image_path, label_anchor, label_source),
                "file_ext": ext,
                "format_group": format_group(ext),
                "benchmark_group": benchmark_group_for(image_path),
                "label_source": label_source,
                "label_anchor": display_path(label_anchor),
            }
        )

    tree = describe_dataset_tree(dataset_root)
    discovery = {
        **tree,
        "total_image_files_seen": len(image_paths),
        "total_image_files_found_before_label_filter": len(image_paths),
        "labeled_image_count": len(samples),
        "ai_count": sum(1 for sample in samples if sample["ground_truth"] == "ai"),
        "real_count": sum(1 for sample in samples if sample["ground_truth"] == "real"),
        "skipped_unknown_label_count": skipped_unknown_label_count,
        "skipped_examples": skipped_samples[:50],
        "skipped_samples": skipped_samples,
        "top_skipped_parent_dirs": [
            {"parent_dir": parent, "count": count}
            for parent, count in skipped_parent_dirs.most_common(30)
        ],
        "top_all_parent_dirs": [
            {"parent_dir": parent, "count": count}
            for parent, count in all_parent_dirs.most_common(50)
        ],
        "recognized_label_anchors": {
            label: [
                {"anchor": anchor, "count": count}
                for anchor, count in counter.most_common()
            ]
            for label, counter in recognized_label_anchors.items()
        },
        "found_ai_label_dirs": sorted(ai_label_dirs),
        "found_real_label_dirs": sorted(real_label_dirs),
        "found_ai_or_real_dirs": bool(ai_label_dirs or real_label_dirs),
    }
    return samples, discovery


def extract_raw_score(result: dict[str, Any]) -> float | None:
    debug = result.get("debug_evidence") if isinstance(result.get("debug_evidence"), dict) else {}
    technical = (
        result.get("technical_explanation")
        if isinstance(result.get("technical_explanation"), dict)
        else {}
    )
    for value in (
        debug.get("raw_score"),
        technical.get("score"),
        debug.get("feature_summary", {}).get("raw_score")
        if isinstance(debug.get("feature_summary"), dict)
        else None,
    ):
        number = safe_float(value)
        if number is not None:
            return number
    return None


def detect_one(sample: dict[str, Any]) -> dict[str, Any]:
    image_path = sample["image_path"]
    started = time.perf_counter()
    base = {
        "image_path": display_path(image_path),
        "filename": sample["filename"],
        "ground_truth": sample["ground_truth"],
        "scenario": sample["scenario"],
        "file_ext": sample["file_ext"],
        "format_group": sample["format_group"],
        "benchmark_group": sample.get("benchmark_group") or "unknown_group",
        "label_source": sample.get("label_source") or "",
        "label_anchor": sample.get("label_anchor") or "",
    }

    try:
        result = detect_image_for_api(str(image_path), filename=image_path.name)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        final_label = result.get("final_label")
        predicted_label = normalize_label(final_label)
        confidence = safe_float(result.get("confidence"))
        raw_score = extract_raw_score(result)
        return {
            **base,
            "status": "success",
            "predicted_label": predicted_label,
            "final_label": final_label,
            "risk_level": result.get("risk_level"),
            "confidence": confidence,
            "decision_reason": result.get("decision_reason") or [],
            "recommendation": result.get("recommendation") or {},
            "is_uncertain": predicted_label == "uncertain",
            "raw_score": raw_score,
            "debug_evidence": result.get("debug_evidence") or {},
            "technical_explanation": result.get("technical_explanation") or {},
            "user_facing_summary": result.get("user_facing_summary") or "",
            "error": None,
            "inference_time_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            **base,
            "status": "error",
            "predicted_label": "uncertain",
            "final_label": None,
            "risk_level": None,
            "confidence": None,
            "decision_reason": [],
            "recommendation": {},
            "is_uncertain": True,
            "raw_score": None,
            "debug_evidence": {},
            "technical_explanation": {},
            "user_facing_summary": "",
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "inference_time_ms": elapsed_ms,
        }


def empty_confusion() -> dict[str, int]:
    return {
        "TP": 0,
        "TN": 0,
        "FP": 0,
        "FN": 0,
        "uncertain_ai_count": 0,
        "uncertain_real_count": 0,
    }


def confusion_matrix(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = empty_confusion()
    for row in rows:
        if row.get("status") != "success":
            continue
        truth = row.get("ground_truth")
        pred = normalize_label(row.get("predicted_label"))
        if truth == "ai" and pred == "ai":
            counts["TP"] += 1
        elif truth == "real" and pred == "real":
            counts["TN"] += 1
        elif truth == "real" and pred == "ai":
            counts["FP"] += 1
        elif truth == "ai" and pred == "real":
            counts["FN"] += 1
        elif truth == "ai" and pred == "uncertain":
            counts["uncertain_ai_count"] += 1
        elif truth == "real" and pred == "uncertain":
            counts["uncertain_real_count"] += 1
    return counts


def confidence_distribution(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    values = [
        row["confidence"]
        for row in rows
        if row.get("status") == "success" and isinstance(row.get("confidence"), (int, float))
    ]
    if not values:
        return None, None
    return round(sum(values) / len(values), 4), round(float(median(values)), 4)


def metrics_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_samples = len(rows)
    valid_rows = [row for row in rows if row.get("status") == "success"]
    valid_samples = len(valid_rows)
    error_count = total_samples - valid_samples
    ai_samples = sum(1 for row in valid_rows if row.get("ground_truth") == "ai")
    real_samples = sum(1 for row in valid_rows if row.get("ground_truth") == "real")
    counts = confusion_matrix(valid_rows)

    tp = counts["TP"]
    tn = counts["TN"]
    fp = counts["FP"]
    fn = counts["FN"]
    uncertain_count = counts["uncertain_ai_count"] + counts["uncertain_real_count"]
    clear_count = tp + tn + fp + fn
    correct_clear = tp + tn
    precision_ai = safe_divide(tp, tp + fp) or 0.0
    recall_ai = safe_divide(tp, tp + fn) or 0.0
    f1_ai = (
        round(2 * precision_ai * recall_ai / (precision_ai + recall_ai), 4)
        if precision_ai + recall_ai > 0
        else 0.0
    )
    real_precision = safe_divide(tn, tn + fn) or 0.0
    specificity = safe_divide(tn, tn + fp) or 0.0
    avg_confidence, med_confidence = confidence_distribution(valid_rows)

    confidence_by_label: dict[str, Any] = {}
    for label in ("ai", "real", "uncertain"):
        values = [
            row["confidence"]
            for row in valid_rows
            if normalize_label(row.get("predicted_label")) == label
            and isinstance(row.get("confidence"), (int, float))
        ]
        confidence_by_label[label] = {
            "count": len(values),
            "average_confidence": round(sum(values) / len(values), 4) if values else None,
        }

    risk_distribution = Counter(str(row.get("risk_level") or "unknown") for row in valid_rows)
    final_label_distribution = Counter(
        normalize_label(row.get("predicted_label")) for row in valid_rows
    )

    return {
        "total_samples": total_samples,
        "valid_samples": valid_samples,
        "error_count": error_count,
        "ai_samples": ai_samples,
        "real_samples": real_samples,
        "accuracy_strict": safe_divide(correct_clear, valid_samples),
        "precision_ai": precision_ai,
        "recall_ai": recall_ai,
        "f1_ai": f1_ai,
        "real_precision": real_precision,
        "specificity": specificity,
        "false_positive_rate": safe_divide(fp, real_samples),
        "false_negative_rate": safe_divide(fn, ai_samples),
        "uncertain_rate": safe_divide(uncertain_count, valid_samples),
        "coverage_rate": safe_divide(clear_count, valid_samples),
        "selective_accuracy": safe_divide(correct_clear, clear_count),
        "average_confidence": avg_confidence,
        "median_confidence": med_confidence,
        "confidence_by_label": confidence_by_label,
        "risk_level_distribution": dict(sorted(risk_distribution.items())),
        "final_label_distribution": dict(sorted(final_label_distribution.items())),
    }


def main_failure_type(rows: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    counts = confusion_matrix(rows)
    fp = counts["FP"]
    fn = counts["FN"]
    uncertain = counts["uncertain_ai_count"] + counts["uncertain_real_count"]
    if fp + fn + uncertain == 0:
        return "stable"
    if (metrics.get("uncertain_rate") or 0.0) >= 0.3 and uncertain >= max(fp, fn):
        return "high_uncertainty"
    if fp > 0 and fp >= max(fn, uncertain) * 2:
        return "real_images_flagged_as_ai"
    if fn > 0 and fn >= max(fp, uncertain) * 2:
        return "ai_images_missed_as_real"
    if (metrics.get("accuracy_strict") or 0.0) >= 0.85 and (metrics.get("uncertain_rate") or 0.0) <= 0.1:
        return "stable"
    return "mixed"


def scenario_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("scenario") or "unknown")].append(row)

    output: list[dict[str, Any]] = []
    for scenario_name, items in sorted(grouped.items()):
        valid_items = [row for row in items if row.get("status") == "success"]
        counts = confusion_matrix(valid_items)
        metrics = metrics_for_rows(items)
        output.append(
            {
                "scenario_name": scenario_name,
                "total": len(items),
                "ai_count": sum(1 for row in items if row.get("ground_truth") == "ai"),
                "real_count": sum(1 for row in items if row.get("ground_truth") == "real"),
                "strict_accuracy": metrics["accuracy_strict"],
                "selective_accuracy": metrics["selective_accuracy"],
                "uncertain_rate": metrics["uncertain_rate"],
                "false_positive_count": counts["FP"],
                "false_negative_count": counts["FN"],
                "false_positive_rate": metrics["false_positive_rate"],
                "false_negative_rate": metrics["false_negative_rate"],
                "average_confidence": metrics["average_confidence"],
                "main_failure_type": main_failure_type(valid_items, metrics),
            }
        )
    return output


def format_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in ("jpg", "png", "webp", "others")}
    for row in rows:
        grouped.setdefault(str(row.get("format_group") or "others"), []).append(row)

    output: list[dict[str, Any]] = []
    for group_name in ("jpg", "png", "webp", "others"):
        items = grouped.get(group_name, [])
        metrics = metrics_for_rows(items)
        output.append(
            {
                "format": group_name,
                "total": len(items),
                "strict_accuracy": metrics["accuracy_strict"],
                "selective_accuracy": metrics["selective_accuracy"],
                "uncertain_rate": metrics["uncertain_rate"],
                "false_positive_rate": metrics["false_positive_rate"],
                "false_negative_rate": metrics["false_negative_rate"],
                "average_confidence": metrics["average_confidence"],
            }
        )
    return output


def metric_definitions() -> dict[str, str]:
    return {
        "TP": "ground_truth=ai and predicted=ai",
        "TN": "ground_truth=real and predicted=real",
        "FP": "ground_truth=real and predicted=ai",
        "FN": "ground_truth=ai and predicted=real",
        "strict_accuracy": "(TP + TN) / valid_samples; uncertain is counted as incorrect.",
        "coverage_rate": "clear ai or real predictions / valid_samples",
        "selective_accuracy": "correct clear ai or real predictions / clear ai or real predictions",
        "uncertain_rate": "uncertain predictions / valid_samples",
        "precision_ai": "TP / (TP + FP)",
        "recall_ai": "TP / (TP + FN)",
        "f1_ai": "2 * precision_ai * recall_ai / (precision_ai + recall_ai)",
        "false_positive_rate": "FP / real_samples",
        "false_negative_rate": "FN / ai_samples",
    }


def compact_discovery_report(discovery: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_root": discovery.get("dataset_root"),
        "root_exists": discovery.get("root_exists"),
        "total_image_files_found_before_label_filter": discovery.get(
            "total_image_files_found_before_label_filter",
            0,
        ),
        "labeled_image_count": discovery.get("labeled_image_count", 0),
        "ai_count": discovery.get("ai_count", 0),
        "real_count": discovery.get("real_count", 0),
        "skipped_unknown_label_count": discovery.get("skipped_unknown_label_count", 0),
        "top_skipped_parent_dirs": discovery.get("top_skipped_parent_dirs", []),
        "top_all_parent_dirs": discovery.get("top_all_parent_dirs", []),
        "recognized_label_anchors": discovery.get("recognized_label_anchors", {}),
        "skipped_examples": discovery.get("skipped_examples", []),
        "first_level_directories": discovery.get("first_level_directories", []),
        "second_level_directories": discovery.get("second_level_directories", []),
        "image_directories": discovery.get("image_directories", []),
    }


def build_summary(
    rows: list[dict[str, Any]],
    dataset_root: Path,
    output_dir: Path,
    report_dir: Path,
    discovery: dict[str, Any],
) -> dict[str, Any]:
    overall = metrics_for_rows(rows)
    counts = confusion_matrix(rows)
    scenarios = scenario_metrics(rows)
    formats = format_metrics(rows)
    valid_samples = overall["valid_samples"]
    uncertain_total = counts["uncertain_ai_count"] + counts["uncertain_real_count"]

    return {
        "protocol_version": "benchmark_protocol_v2_day23",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": display_path(dataset_root),
        "output_files": {
            "results_json": display_path(output_dir / RESULTS_JSON),
            "summary_json": display_path(output_dir / SUMMARY_JSON),
            "results_csv": display_path(output_dir / RESULTS_CSV),
            "skipped_samples_csv": display_path(output_dir / SKIPPED_CSV),
            "dataset_discovery_json": display_path(output_dir / DISCOVERY_JSON),
            "report_md": display_path(report_dir / REPORT_MD),
        },
        "dataset_structure": {
            "ai_samples": sum(1 for row in rows if row.get("ground_truth") == "ai"),
            "real_samples": sum(1 for row in rows if row.get("ground_truth") == "real"),
            "total_image_files_found_before_label_filter": discovery.get(
                "total_image_files_found_before_label_filter",
                0,
            ),
            "labeled_image_count": discovery.get("labeled_image_count", len(rows)),
            "skipped_unknown_label_count": discovery.get("skipped_unknown_label_count", 0),
            "scenario_list": sorted({str(row.get("scenario")) for row in rows}),
            "format_list": sorted({str(row.get("file_ext")) for row in rows}),
            "benchmark_group_distribution": dict(
                sorted(Counter(str(row.get("benchmark_group") or "unknown_group") for row in rows).items())
            ),
            "found_ai_label_dirs": discovery.get("found_ai_label_dirs", []),
            "found_real_label_dirs": discovery.get("found_real_label_dirs", []),
        },
        "dataset_discovery": compact_discovery_report(discovery),
        "metric_definitions": metric_definitions(),
        "confusion_matrix": counts,
        "strict_binary_view": {
            "accuracy_strict": overall["accuracy_strict"],
            "valid_samples": valid_samples,
            "uncertain_counted_as_error": True,
        },
        "selective_view": {
            "coverage_rate": overall["coverage_rate"],
            "selective_accuracy": overall["selective_accuracy"],
            "uncertain_rate": overall["uncertain_rate"],
            "clear_prediction_count": counts["TP"] + counts["TN"] + counts["FP"] + counts["FN"],
        },
        "triage_view": {
            "ai_prediction_count": overall["final_label_distribution"].get("ai", 0),
            "real_prediction_count": overall["final_label_distribution"].get("real", 0),
            "uncertain_prediction_count": uncertain_total,
            "distribution": overall["final_label_distribution"],
        },
        "overall_metrics": overall,
        "scenario_metrics": scenarios,
        "format_metrics": formats,
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def value_text(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if i == 0 else "---:" for i, _ in enumerate(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def finding_lines(summary: dict[str, Any]) -> list[str]:
    overall = summary["overall_metrics"]
    counts = summary["confusion_matrix"]
    scenarios = summary["scenario_metrics"]
    formats = summary["format_metrics"]
    findings: list[str] = []

    if overall.get("valid_samples") == 0:
        return [
            "- No valid benchmark samples were found under the configured ai/ and real/ folders.",
            "- The protocol outputs were generated successfully, but performance conclusions require populated test images.",
        ]

    if (overall.get("false_positive_rate") or 0.0) >= 0.2:
        findings.append(
            f"- False positives are elevated: FP={counts['FP']}, FPR={pct(overall.get('false_positive_rate'))}."
        )
    else:
        findings.append(
            f"- False positives are currently contained: FP={counts['FP']}, FPR={pct(overall.get('false_positive_rate'))}."
        )

    if (overall.get("false_negative_rate") or 0.0) >= 0.2:
        findings.append(
            f"- False negatives are elevated: FN={counts['FN']}, FNR={pct(overall.get('false_negative_rate'))}."
        )
    else:
        findings.append(
            f"- False negatives are currently contained: FN={counts['FN']}, FNR={pct(overall.get('false_negative_rate'))}."
        )

    worst_scenarios = worst_items(scenarios, "scenario_name")
    if worst_scenarios:
        names = ", ".join(item["scenario_name"] for item in worst_scenarios[:3])
        findings.append(f"- Least stable scenarios by strict accuracy/uncertainty: {names}.")

    worst_formats = worst_items(formats, "format")
    if worst_formats:
        names = ", ".join(item["format"] for item in worst_formats[:3])
        findings.append(f"- Least stable formats by strict accuracy/uncertainty: {names}.")

    strict = overall.get("accuracy_strict")
    selective = overall.get("selective_accuracy")
    if strict is not None and selective is not None and selective > strict:
        findings.append(
            f"- Selective view is stronger than strict view: {pct(selective)} vs {pct(strict)}."
        )

    if (overall.get("uncertain_rate") or 0.0) >= 0.25:
        findings.append(f"- Uncertainty is high at {pct(overall.get('uncertain_rate'))}.")
    else:
        findings.append(f"- Uncertainty is manageable at {pct(overall.get('uncertain_rate'))}.")

    return findings


def bottleneck_lines(summary: dict[str, Any]) -> list[str]:
    overall = summary["overall_metrics"]
    bottlenecks = []
    if overall.get("valid_samples") == 0:
        return [
            "- The default benchmark folders contain no valid samples, so Day23 cannot yet produce performance conclusions.",
            "- Add images under data/test_images/ai and data/test_images/real, or point --dataset-root to a populated ai/real dataset.",
        ]
    if (overall.get("uncertain_rate") or 0.0) > 0:
        bottlenecks.append("- Some samples route to uncertain, reducing strict binary accuracy.")
    if (overall.get("false_positive_rate") or 0.0) > 0:
        bottlenecks.append("- Real-image false positives still need case-level review.")
    if (overall.get("false_negative_rate") or 0.0) > 0:
        bottlenecks.append("- AI-image misses still need scenario-level review.")
    if overall.get("error_count"):
        bottlenecks.append("- Detection errors occurred and should be checked before locking a baseline.")
    if not bottlenecks:
        bottlenecks.append("- No major bottleneck is visible in this benchmark run.")
    return bottlenecks


def worst_items(items: list[dict[str, Any]], name_key: str) -> list[dict[str, Any]]:
    def score(item: dict[str, Any]) -> tuple[float, float, int]:
        strict = item.get("strict_accuracy")
        strict_sort = float(strict) if strict is not None else -1.0
        uncertain = float(item.get("uncertain_rate") or 0.0)
        total = int(item.get("total") or 0)
        return (strict_sort, -uncertain, -total)

    return [
        item
        for item in sorted(items, key=score)
        if item.get("total", 0) > 0 and item.get(name_key) is not None
    ]


def build_report(summary: dict[str, Any]) -> str:
    overall = summary["overall_metrics"]
    counts = summary["confusion_matrix"]
    dataset = summary["dataset_structure"]
    discovery = summary.get("dataset_discovery", {})
    ai_dirs = dataset.get("found_ai_label_dirs", [])
    real_dirs = dataset.get("found_real_label_dirs", [])

    overall_rows = [
        ["total_samples", overall["total_samples"]],
        ["valid_samples", overall["valid_samples"]],
        ["error_count", overall["error_count"]],
        ["ai_samples", overall["ai_samples"]],
        ["real_samples", overall["real_samples"]],
        ["accuracy_strict", pct(overall["accuracy_strict"])],
        ["precision_ai", pct(overall["precision_ai"])],
        ["recall_ai", pct(overall["recall_ai"])],
        ["f1_ai", value_text(overall["f1_ai"])],
        ["specificity", pct(overall["specificity"])],
        ["false_positive_rate", pct(overall["false_positive_rate"])],
        ["false_negative_rate", pct(overall["false_negative_rate"])],
        ["uncertain_rate", pct(overall["uncertain_rate"])],
        ["coverage_rate", pct(overall["coverage_rate"])],
        ["selective_accuracy", pct(overall["selective_accuracy"])],
        ["average_confidence", value_text(overall["average_confidence"])],
        ["median_confidence", value_text(overall["median_confidence"])],
    ]

    scenario_rows = [
        [
            item["scenario_name"],
            item["total"],
            item["ai_count"],
            item["real_count"],
            pct(item["strict_accuracy"]),
            pct(item["selective_accuracy"]),
            pct(item["uncertain_rate"]),
            item["false_positive_count"],
            item["false_negative_count"],
            pct(item["false_positive_rate"]),
            pct(item["false_negative_rate"]),
            value_text(item["average_confidence"]),
            item["main_failure_type"],
        ]
        for item in summary["scenario_metrics"]
    ]

    format_rows = [
        [
            item["format"],
            item["total"],
            pct(item["strict_accuracy"]),
            pct(item["selective_accuracy"]),
            pct(item["uncertain_rate"]),
            pct(item["false_positive_rate"]),
            pct(item["false_negative_rate"]),
            value_text(item["average_confidence"]),
        ]
        for item in summary["format_metrics"]
    ]
    skipped_dir_rows = [
        [item["parent_dir"], item["count"]]
        for item in discovery.get("top_skipped_parent_dirs", [])[:10]
    ]
    if not skipped_dir_rows:
        skipped_dir_rows = [["none", 0]]

    return "\n\n".join(
        [
            "# Day23 Benchmark Protocol v2 Report",
            "## 1. Objective\n\nDay23 does not optimize detection weights, add pretrained models, or change the product/API output contract. The goal is to establish a reproducible Benchmark Protocol v2 for long-term regression tracking of the current AI image trust scanner.",
            "## 2. Dataset Structure\n\n"
            + markdown_table(
                ["Item", "Value"],
                [
                    ["ai samples", dataset["ai_samples"]],
                    ["real samples", dataset["real_samples"]],
                    [
                        "total images before label filter",
                        dataset.get("total_image_files_found_before_label_filter", 0),
                    ],
                    ["labeled images", dataset.get("labeled_image_count", 0)],
                    ["skipped unknown label images", dataset.get("skipped_unknown_label_count", 0)],
                    ["ai label dirs", ", ".join(ai_dirs[:12]) + (" ..." if len(ai_dirs) > 12 else "")],
                    ["real label dirs", ", ".join(real_dirs[:12]) + (" ..." if len(real_dirs) > 12 else "")],
                    ["scenarios", ", ".join(dataset["scenario_list"]) or "none"],
                    ["formats", ", ".join(dataset["format_list"]) or "none"],
                ],
            ),
            "## 3. Evaluation Views\n\n"
            "- strict_binary_view: uncertain outputs are counted as incorrect when computing strict accuracy.\n"
            "- selective_view: uncertain outputs are removed from binary accuracy; coverage_rate and uncertain_rate are reported separately.\n"
            "- triage_view: ai, real, and uncertain are treated as three product-routing buckets.",
            "## Dataset Discovery Diagnostics\n\n"
            + markdown_table(
                ["Item", "Value"],
                [
                    [
                        "total_image_files_found_before_label_filter",
                        discovery.get("total_image_files_found_before_label_filter", 0),
                    ],
                    ["labeled_image_count", discovery.get("labeled_image_count", 0)],
                    ["ai_count", discovery.get("ai_count", 0)],
                    ["real_count", discovery.get("real_count", 0)],
                    ["skipped_unknown_label_count", discovery.get("skipped_unknown_label_count", 0)],
                    [
                        "preprocessing_label_lost",
                        "yes"
                        if discovery.get("skipped_unknown_label_count", 0)
                        else "no visible skipped label-loss cluster",
                    ],
                ],
            )
            + "\n\nTop skipped directories:\n\n"
            + markdown_table(["Parent Directory", "Skipped Images"], skipped_dir_rows)
            + "\n\nSkipped reason: unknown ground-truth label. When transformed files lose ai/real in both output path and safe filename prefix, preserve ai/real in the output path or metadata before using them as benchmark samples.",
            "## 4. Overall Metrics\n\n" + markdown_table(["Metric", "Value"], overall_rows),
            "## 5. Confusion Matrix\n\n"
            + markdown_table(
                ["Ground Truth / Prediction", "AI", "Real", "Uncertain"],
                [
                    ["AI", counts["TP"], counts["FN"], counts["uncertain_ai_count"]],
                    ["Real", counts["FP"], counts["TN"], counts["uncertain_real_count"]],
                ],
            )
            + "\n\nMetric definitions: TP = ground_truth=ai and predicted=ai; TN = ground_truth=real and predicted=real; FP = ground_truth=real and predicted=ai; FN = ground_truth=ai and predicted=real. strict_accuracy = (TP + TN) / valid_samples. coverage_rate = clear ai or real predictions / valid_samples. selective_accuracy = correct clear predictions / clear predictions. uncertain_rate = uncertain predictions / valid_samples. precision_ai = TP / (TP + FP). recall_ai = TP / (TP + FN). f1_ai = 2 * precision_ai * recall_ai / (precision_ai + recall_ai). false_positive_rate = FP / real_samples. false_negative_rate = FN / ai_samples.",
            "## 6. Scenario Metrics\n\n"
            + markdown_table(
                [
                    "Scenario",
                    "Total",
                    "AI",
                    "Real",
                    "Strict Acc",
                    "Selective Acc",
                    "Uncertain",
                    "FP",
                    "FN",
                    "FPR",
                    "FNR",
                    "Avg Conf",
                    "Main Failure",
                ],
                scenario_rows,
            ),
            "## 7. Format Metrics\n\n"
            + markdown_table(
                [
                    "Format",
                    "Total",
                    "Strict Acc",
                    "Selective Acc",
                    "Uncertain",
                    "FPR",
                    "FNR",
                    "Avg Conf",
                ],
                format_rows,
            ),
            "## 8. Key Findings\n\n" + "\n".join(finding_lines(summary)),
            "## 9. Current Bottlenecks\n\n" + "\n".join(bottleneck_lines(summary)),
            "## 10. Recommended Day24 Direction\n\n"
            "- Build an Error Gallery + Misclassification Review UI.\n"
            "- Add FP/FN case browser filters by scenario and format.\n"
            "- Add difficult sample tagging for uncertain, false-positive, and false-negative cases.\n"
            "- Lock this benchmark output as the first Protocol v2 regression baseline.",
        ]
    ) + "\n"


def write_results_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "image_path",
        "filename",
        "ground_truth",
        "predicted_label",
        "final_label",
        "risk_level",
        "confidence",
        "decision_reason",
        "recommendation",
        "scenario",
        "file_ext",
        "format_group",
        "benchmark_group",
        "label_source",
        "label_anchor",
        "is_uncertain",
        "raw_score",
        "status",
        "error",
        "inference_time_ms",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: flatten_text(row.get(field))
                    if field in {"decision_reason", "recommendation", "error"}
                    else row.get(field)
                    for field in fields
                }
            )


def write_skipped_csv(skipped_samples: list[dict[str, Any]], path: Path) -> None:
    fields = ["image_path", "filename", "parent_dir", "relative_path", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in skipped_samples:
            writer.writerow({field: row.get(field, "") for field in fields})


def print_console_summary(summary: dict[str, Any]) -> None:
    overall = summary["overall_metrics"]
    counts = summary["confusion_matrix"]
    worst_scenarios = worst_items(summary["scenario_metrics"], "scenario_name")[:3]
    worst_formats = worst_items(summary["format_metrics"], "format")[:3]
    outputs = summary["output_files"]
    discovery = summary.get("dataset_discovery", {})

    print("\nDay23 Benchmark Protocol v2 Summary")
    print("===================================")
    print(
        "total image files found before label filter: "
        f"{discovery.get('total_image_files_found_before_label_filter', overall['total_samples'])}"
    )
    print(f"labeled image count: {discovery.get('labeled_image_count', overall['total_samples'])}")
    print(f"ai count: {discovery.get('ai_count', overall['ai_samples'])}")
    print(f"real count: {discovery.get('real_count', overall['real_samples'])}")
    print(f"skipped unknown label count: {discovery.get('skipped_unknown_label_count', 0)}")
    print(f"total samples: {overall['total_samples']}")
    print(f"valid samples: {overall['valid_samples']}")
    print(f"errors: {overall['error_count']}")
    print(f"strict accuracy: {pct(overall['accuracy_strict'])}")
    print(f"selective accuracy: {pct(overall['selective_accuracy'])}")
    print(f"uncertain rate: {pct(overall['uncertain_rate'])}")
    print(f"coverage rate: {pct(overall['coverage_rate'])}")
    print(f"TP / TN / FP / FN: {counts['TP']} / {counts['TN']} / {counts['FP']} / {counts['FN']}")
    print("worst scenarios:")
    for item in worst_scenarios:
        print(
            f"  - {item['scenario_name']}: strict={pct(item['strict_accuracy'])}, "
            f"uncertain={pct(item['uncertain_rate'])}, failure={item['main_failure_type']}"
        )
    if not worst_scenarios:
        print("  - none")
    print("worst formats:")
    for item in worst_formats:
        print(
            f"  - {item['format']}: strict={pct(item['strict_accuracy'])}, "
            f"uncertain={pct(item['uncertain_rate'])}"
        )
    if not worst_formats:
        print("  - none")
    print("top skipped dirs:")
    top_skipped = discovery.get("top_skipped_parent_dirs", [])
    for item in top_skipped[:10]:
        print(f"  - {item['parent_dir']}: {item['count']}")
    if not top_skipped:
        print("  - none")
    print("output files:")
    for key, value in outputs.items():
        print(f"  - {key}: {value}")


def print_zero_sample_diagnostics(dataset_root: Path, discovery: dict[str, Any]) -> None:
    print("\nDay23 Benchmark Protocol v2 Dataset Discovery")
    print("============================================")
    print("No labeled benchmark samples were found. Empty reports were not regenerated.")
    print(f"dataset-root: {display_path(dataset_root)}")
    print(f"root exists: {discovery.get('root_exists')}")
    print(f"total image files seen: {discovery.get('total_image_files_seen', 0)}")
    print(f"skipped unknown label images: {discovery.get('skipped_unknown_label_count', 0)}")
    print(f"found ai label dirs: {len(discovery.get('found_ai_label_dirs', []))}")
    for path in discovery.get("found_ai_label_dirs", [])[:20]:
        print(f"  - {path}")
    print(f"found real label dirs: {len(discovery.get('found_real_label_dirs', []))}")
    for path in discovery.get("found_real_label_dirs", [])[:20]:
        print(f"  - {path}")
    print("first-level directories:")
    for path in discovery.get("first_level_directories", [])[:50]:
        print(f"  - {path}")
    print("second-level directories:")
    for path in discovery.get("second_level_directories", [])[:80]:
        print(f"  - {path}")
    print("image-containing directories:")
    for item in discovery.get("image_directories", [])[:120]:
        print(f"  - {item['path']} ({item['image_count']} images)")
    if dataset_root.name.lower() != "data":
        print("suggestion: try --dataset-root data")


def main() -> int:
    args = parse_args()
    dataset_root = resolve_path(args.dataset_root)
    output_dir = resolve_path(args.output_dir)
    report_dir = resolve_path(args.report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    samples, discovery = discover_dataset_images(dataset_root)
    skipped_csv_path = output_dir / SKIPPED_CSV
    discovery_json_path = output_dir / DISCOVERY_JSON
    write_skipped_csv(discovery.get("skipped_samples", []), skipped_csv_path)
    discovery_json_path.write_text(
        json.dumps(json_safe(compact_discovery_report(discovery)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not samples:
        print_zero_sample_diagnostics(dataset_root, discovery)
        return 2

    rows = [detect_one(sample) for sample in samples]
    summary = build_summary(rows, dataset_root, output_dir, report_dir, discovery)

    results_json_path = output_dir / RESULTS_JSON
    summary_json_path = output_dir / SUMMARY_JSON
    results_csv_path = output_dir / RESULTS_CSV
    report_path = report_dir / REPORT_MD

    results_json_path.write_text(
        json.dumps(json_safe(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_json_path.write_text(
        json.dumps(json_safe(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_results_csv(rows, results_csv_path)
    report_path.write_text(build_report(summary), encoding="utf-8")

    print_console_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
