from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.decision_policy import load_decision_policy  # noqa: E402
from core.forensic_analyzer import analyze_forensics  # noqa: E402
from core.frequency_analyzer import analyze_frequency  # noqa: E402
from core.image_loader import load_image  # noqa: E402
from core.metadata_analyzer import analyze_metadata  # noqa: E402
from core.model_detector import detect_with_model  # noqa: E402
from core.score_fusion import fuse_scores, load_detector_weight_config  # noqa: E402


DAY14_ROOT = PROJECT_ROOT / "data" / "test_images" / "day14_expansion"
RAW_ROOT = DAY14_ROOT / "raw"
PAIRED_ROOT = DAY14_ROOT / "paired_format"
RESOLUTION_ROOT = DAY14_ROOT / "resolution_control"
METADATA_PATH = DAY14_ROOT / "metadata" / "day14_metadata.csv"
REPORTS_DIR = PROJECT_ROOT / "reports" / "day14"

RAW_RESULTS_CSV = REPORTS_DIR / "day14_raw_baseline_results.csv"
FORMAT_RESULTS_CSV = REPORTS_DIR / "day14_format_eval_results.csv"
RESOLUTION_RESULTS_CSV = REPORTS_DIR / "day14_resolution_eval_results.csv"
SUMMARY_JSON = REPORTS_DIR / "day14_summary_metrics.json"
SUMMARY_MD = REPORTS_DIR / "day14_dataset_expansion_report.md"

RESULT_FIELDS = [
    "image_id",
    "label",
    "scene_type",
    "variant",
    "current_format",
    "resolution_type",
    "width",
    "height",
    "score",
    "threshold",
    "pred_label",
    "final_label",
    "is_correct",
    "is_uncertain",
    "error_type",
    "source_path",
]

NEAR_THRESHOLD_LOW = 0.12
NEAR_THRESHOLD_HIGH = 0.20
VALID_FINAL_LABELS = {"ai", "real"}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def format_float(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def source_path_for(row: dict[str, str]) -> Path:
    split = row.get("split", "")
    label = row["label"]
    scene_type = row["scene_type"]
    filename = row["current_filename"]
    if split == "day14_main_eval":
        return RAW_ROOT / label / scene_type / filename
    if split == "day14_format_eval":
        folder = f"{label}_png" if row["variant"] == "png" else f"{label}_jpg"
        return PAIRED_ROOT / folder / filename
    if split == "day14_resolution_eval":
        folder = row["resolution_type"].replace("long", "long_")
        return RESOLUTION_ROOT / folder / filename
    raise ValueError(f"Unsupported split: {split}")


def pipeline_error_result(row: dict[str, str], source_path: Path, threshold: float, message: str) -> dict[str, Any]:
    return {
        "image_id": row["image_id"],
        "label": row["label"],
        "scene_type": row["scene_type"],
        "variant": row["variant"],
        "current_format": row["current_format"],
        "resolution_type": row["resolution_type"],
        "width": row.get("width", ""),
        "height": row.get("height", ""),
        "score": "",
        "threshold": format_float(threshold),
        "pred_label": "",
        "final_label": "",
        "is_correct": "false",
        "is_uncertain": "false",
        "error_type": f"pipeline_error:{message}",
        "source_path": display_path(source_path),
    }


def error_type_for(true_label: str, final_label: str) -> str:
    if final_label == "uncertain":
        return "uncertain"
    if true_label == "real" and final_label == "ai":
        return "false_positive"
    if true_label == "ai" and final_label == "real":
        return "false_negative"
    return ""


def is_hard_candidate(row: dict[str, Any]) -> bool:
    score = safe_float(row.get("score"))
    if score is None:
        return False
    true_label = row.get("label", "")
    final_label = row.get("final_label", "")
    near_threshold = NEAR_THRESHOLD_LOW <= score <= NEAR_THRESHOLD_HIGH
    if true_label == "ai":
        return final_label in {"real", "uncertain"} or near_threshold
    if true_label == "real":
        return final_label in {"ai", "uncertain"} or near_threshold
    return False


def evaluate_one(row: dict[str, str], threshold: float) -> dict[str, Any]:
    source_path = source_path_for(row)
    image_info = load_image(source_path)
    if not image_info.get("ok"):
        return pipeline_error_result(row, source_path, threshold, str(image_info.get("error") or "load_failed"))

    try:
        metadata_result = analyze_metadata(source_path)
        forensic_result = analyze_forensics(source_path)
        frequency_result = analyze_frequency(source_path)
        model_result = detect_with_model(source_path)
        final_result = fuse_scores(
            metadata_result=metadata_result,
            forensic_result=forensic_result,
            frequency_result=frequency_result,
            model_result=model_result,
        )
    except Exception as exc:
        return pipeline_error_result(row, source_path, threshold, str(exc))

    score = safe_float(final_result.get("final_score", final_result.get("raw_score")))
    final_label = str(final_result.get("final_label") or "")
    pred_label = str(final_result.get("binary_label_at_threshold") or "")
    result_threshold = safe_float(final_result.get("threshold"), threshold)
    is_uncertain = final_label == "uncertain"
    is_correct = final_label == row["label"]

    return {
        "image_id": row["image_id"],
        "label": row["label"],
        "scene_type": row["scene_type"],
        "variant": row["variant"],
        "current_format": row["current_format"],
        "resolution_type": row["resolution_type"],
        "width": int(image_info.get("width") or safe_int(row.get("width"))),
        "height": int(image_info.get("height") or safe_int(row.get("height"))),
        "score": format_float(score),
        "threshold": format_float(result_threshold),
        "pred_label": pred_label,
        "final_label": final_label,
        "is_correct": bool_text(is_correct),
        "is_uncertain": bool_text(is_uncertain),
        "error_type": error_type_for(row["label"], final_label),
        "source_path": display_path(source_path),
    }


def evaluate_split(rows: list[dict[str, str]], split: str, threshold: float) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("split") == split]
    output = []
    started = time.time()
    for index, row in enumerate(selected, 1):
        output.append(evaluate_one(row, threshold))
        if index % 100 == 0 or index == len(selected):
            elapsed = time.time() - started
            print(f"{split}: evaluated {index}/{len(selected)} images in {elapsed:.1f}s", flush=True)
    return output


def usable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if safe_float(row.get("score")) is not None and row.get("final_label")]


def accuracy(rows: list[dict[str, Any]]) -> float:
    usable = usable_rows(rows)
    return safe_ratio(sum(1 for row in usable if row.get("is_correct") == "true"), len(usable))


def grouped_accuracy(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usable_rows(rows):
        grouped[str(row.get(key, ""))].append(row)
    return {
        group: {
            "count": len(items),
            "correct_count": sum(1 for item in items if item.get("is_correct") == "true"),
            "accuracy": accuracy(items),
            "uncertain_count": sum(1 for item in items if item.get("final_label") == "uncertain"),
        }
        for group, items in sorted(grouped.items())
    }


def scene_label_counts(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(str(row.get("label", "")), str(row.get("scene_type", "")))] += 1
    return [
        {"label": label, "scene_type": scene, "count": str(count)}
        for (label, scene), count in sorted(counts.items())
    ]


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = usable_rows(rows)
    ai_rows = [row for row in usable if row.get("label") == "ai"]
    real_rows = [row for row in usable if row.get("label") == "real"]
    uncertain_count = sum(1 for row in usable if row.get("final_label") == "uncertain")
    return {
        "count": len(usable),
        "overall_accuracy": accuracy(usable),
        "ai_accuracy": accuracy(ai_rows),
        "real_accuracy": accuracy(real_rows),
        "per_scene_accuracy": grouped_accuracy(usable, "scene_type"),
        "per_format_accuracy": grouped_accuracy(usable, "current_format"),
        "per_resolution_accuracy": grouped_accuracy(usable, "resolution_type"),
        "false_positive_count": sum(
            1 for row in usable if row.get("label") == "real" and row.get("final_label") == "ai"
        ),
        "false_negative_count": sum(
            1 for row in usable if row.get("label") == "ai" and row.get("final_label") == "real"
        ),
        "uncertain_count": uncertain_count,
        "uncertain_rate": safe_ratio(uncertain_count, len(usable)),
        "hard_candidate_count": sum(1 for row in usable if is_hard_candidate(row)),
        "pipeline_error_count": len(rows) - len(usable),
    }


def format_flip_summary(format_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in usable_rows(format_rows):
        if row.get("variant") in {"png", "jpg_q95"}:
            by_id[str(row["image_id"])][str(row["variant"])] = row
    complete = {image_id: variants for image_id, variants in by_id.items() if {"png", "jpg_q95"} <= variants.keys()}
    flips = []
    for image_id, variants in sorted(complete.items()):
        png_label = variants["png"].get("final_label")
        jpg_label = variants["jpg_q95"].get("final_label")
        if png_label != jpg_label:
            flips.append(
                {
                    "image_id": image_id,
                    "label": variants["png"].get("label", ""),
                    "scene_type": variants["png"].get("scene_type", ""),
                    "png_final_label": png_label,
                    "jpg_q95_final_label": jpg_label,
                    "png_score": variants["png"].get("score", ""),
                    "jpg_q95_score": variants["jpg_q95"].get("score", ""),
                }
            )
    return {
        "complete_pair_count": len(complete),
        "flip_count": len(flips),
        "format_flip_rate": safe_ratio(len(flips), len(complete)),
        "flips": flips,
    }


def resolution_family(variant: str) -> str:
    return "jpg_q95" if variant.startswith("jpg_q95") else "png"


def resolution_flip_summary(format_rows: list[dict[str, Any]], resolution_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in usable_rows(format_rows + resolution_rows):
        variant = str(row.get("variant", ""))
        if variant == "native":
            continue
        family = resolution_family(variant)
        resolution = str(row.get("resolution_type", ""))
        if resolution in {"native", "long1024", "long768", "long512"}:
            by_group[(str(row["image_id"]), family)][resolution] = row

    required = {"native", "long1024", "long768", "long512"}
    complete = {key: values for key, values in by_group.items() if required <= values.keys()}
    flips = []
    for (image_id, family), variants in sorted(complete.items()):
        labels = {resolution: variants[resolution].get("final_label", "") for resolution in sorted(required)}
        if len(set(labels.values())) > 1:
            scores = {resolution: variants[resolution].get("score", "") for resolution in sorted(required)}
            sample = next(iter(variants.values()))
            flips.append(
                {
                    "image_id": image_id,
                    "format_family": family,
                    "label": sample.get("label", ""),
                    "scene_type": sample.get("scene_type", ""),
                    "final_labels": labels,
                    "scores": scores,
                }
            )
    return {
        "complete_group_count": len(complete),
        "flip_count": len(flips),
        "resolution_flip_rate": safe_ratio(len(flips), len(complete)),
        "flips": flips,
    }


def source_level_accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usable_rows(rows):
        by_id[str(row["image_id"])].append(row)
    per_source = []
    for image_id, items in sorted(by_id.items()):
        label = str(items[0].get("label", ""))
        correct_count = sum(1 for item in items if item.get("is_correct") == "true")
        final_labels = [str(item.get("final_label", "")) for item in items if item.get("final_label") in VALID_FINAL_LABELS]
        majority_label = Counter(final_labels).most_common(1)[0][0] if final_labels else "uncertain"
        per_source.append(
            {
                "image_id": image_id,
                "label": label,
                "variant_count": len(items),
                "correct_count": correct_count,
                "variant_accuracy": safe_ratio(correct_count, len(items)),
                "majority_final_label": majority_label,
                "majority_correct": majority_label == label,
                "all_variants_correct": correct_count == len(items),
            }
        )
    return {
        "source_count": len(per_source),
        "source_level_accuracy": round(mean(item["variant_accuracy"] for item in per_source), 6)
        if per_source
        else 0.0,
        "majority_source_accuracy": safe_ratio(
            sum(1 for item in per_source if item["majority_correct"]), len(per_source)
        ),
        "all_variants_correct_rate": safe_ratio(
            sum(1 for item in per_source if item["all_variants_correct"]), len(per_source)
        ),
    }


def top_error_clusters(rows: list[dict[str, Any]], error_type: str) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for row in usable_rows(rows):
        if row.get("error_type") == error_type:
            counter[(str(row.get("scene_type", "")), str(row.get("variant", "")), str(row.get("resolution_type", "")))] += 1
    return [
        {
            "scene_type": scene,
            "variant": variant,
            "resolution_type": resolution,
            "count": count,
        }
        for (scene, variant, resolution), count in counter.most_common(10)
    ]


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    if not rows:
        return "_None_"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def metric_summary_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"metric": "overall_accuracy", "value": metrics["overall_accuracy"]},
        {"metric": "ai_accuracy", "value": metrics["ai_accuracy"]},
        {"metric": "real_accuracy", "value": metrics["real_accuracy"]},
        {"metric": "false_positive_count", "value": metrics["false_positive_count"]},
        {"metric": "false_negative_count", "value": metrics["false_negative_count"]},
        {"metric": "uncertain_count", "value": metrics["uncertain_count"]},
        {"metric": "uncertain_rate", "value": metrics["uncertain_rate"]},
        {"metric": "hard_candidate_count", "value": metrics["hard_candidate_count"]},
    ]


def write_markdown_report(summary: dict[str, Any]) -> None:
    raw = summary["raw_baseline"]
    fmt = summary["format_eval"]
    res = summary["resolution_eval"]
    dataset_counts = summary["dataset_counts"]
    baseline_supported = (
        "Yes, as a regression reference only. The run used the configured baseline threshold "
        f"`{summary['threshold']:.2f}` without changing detector weights or final-label policy."
    )
    report = f"""# Day14 Dataset Expansion Baseline Report

## 1. Day14 Test Set Scale

- Native raw images: `{dataset_counts['raw_total']}`
- Paired format images: `{dataset_counts['format_total']}`
- Resolution-control images: `{dataset_counts['resolution_total']}`
- Total evaluated rows: `{dataset_counts['all_total']}`

## 2. AI/Real Quantity

{markdown_table(summary["label_count_table"], ["label", "raw", "format", "resolution", "total"])}

## 3. Scene Type Quantity

{markdown_table(summary["scene_count_table"], ["label", "scene_type", "count"])}

## 4. Raw Baseline Result

{markdown_table(metric_summary_rows(raw), ["metric", "value"])}

## 5. Paired Format Result

{markdown_table(metric_summary_rows(fmt), ["metric", "value"])}

## 6. Resolution Control Result

{markdown_table(metric_summary_rows(res), ["metric", "value"])}

## 7. Format Flip Rate Analysis

- Complete PNG/JPG pairs: `{summary['format_flip']['complete_pair_count']}`
- Flip count: `{summary['format_flip']['flip_count']}`
- `format_flip_rate`: `{summary['format_flip']['format_flip_rate']}`

## 8. Resolution Flip Rate Analysis

- Complete native/long-edge groups: `{summary['resolution_flip']['complete_group_count']}`
- Flip count: `{summary['resolution_flip']['flip_count']}`
- `resolution_flip_rate`: `{summary['resolution_flip']['resolution_flip_rate']}`

## 9. Main False Positive Clusters

{markdown_table(summary["false_positive_clusters"], ["scene_type", "variant", "resolution_type", "count"])}

## 10. Main False Negative Clusters

{markdown_table(summary["false_negative_clusters"], ["scene_type", "variant", "resolution_type", "count"])}

## 11. Uncertain Samples

- Raw uncertain count: `{raw['uncertain_count']}`
- Format uncertain count: `{fmt['uncertain_count']}`
- Resolution uncertain count: `{res['uncertain_count']}`
- All uncertain count: `{summary['all_metrics']['uncertain_count']}`

## 12. Baseline @ 0.15 Regression Reference

{baseline_supported}

## 13. Day15 Suggestions

- Review hard candidates by scene type before changing any detector threshold or score weights.
- Compare false-positive clusters against EXIF/missing-EXIF and low-light/weather conditions.
- Inspect format and resolution flip samples first; they are the most useful stress cases for regression stability.
- Keep Day14 metadata difficulty unchanged until baseline evidence is reviewed.
"""
    SUMMARY_MD.write_text(report, encoding="utf-8")


def main() -> int:
    if not METADATA_PATH.exists():
        raise SystemExit(f"Metadata not found: {METADATA_PATH}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    metadata_rows = read_csv_rows(METADATA_PATH)
    config = load_detector_weight_config()
    decision_policy = load_decision_policy(config)
    threshold = float(decision_policy["threshold"])

    print(f"Using configured baseline threshold: {threshold:.6f}", flush=True)
    raw_rows = evaluate_split(metadata_rows, "day14_main_eval", threshold)
    format_rows = evaluate_split(metadata_rows, "day14_format_eval", threshold)
    resolution_rows = evaluate_split(metadata_rows, "day14_resolution_eval", threshold)

    write_csv(RAW_RESULTS_CSV, RESULT_FIELDS, raw_rows)
    write_csv(FORMAT_RESULTS_CSV, RESULT_FIELDS, format_rows)
    write_csv(RESOLUTION_RESULTS_CSV, RESULT_FIELDS, resolution_rows)

    all_rows = raw_rows + format_rows + resolution_rows
    raw_metrics = metric_block(raw_rows)
    format_metrics = metric_block(format_rows)
    resolution_metrics = metric_block(resolution_rows)
    all_metrics = metric_block(all_rows)
    format_flip = format_flip_summary(format_rows)
    resolution_flip = resolution_flip_summary(format_rows, resolution_rows)
    source_accuracy = source_level_accuracy(all_rows)

    label_count_table = []
    for label in ("ai", "real"):
        raw_count = sum(1 for row in raw_rows if row.get("label") == label)
        format_count = sum(1 for row in format_rows if row.get("label") == label)
        resolution_count = sum(1 for row in resolution_rows if row.get("label") == label)
        label_count_table.append(
            {
                "label": label,
                "raw": raw_count,
                "format": format_count,
                "resolution": resolution_count,
                "total": raw_count + format_count + resolution_count,
            }
        )

    summary = {
        "threshold": threshold,
        "decision_policy": decision_policy,
        "dataset_counts": {
            "raw_total": len(raw_rows),
            "format_total": len(format_rows),
            "resolution_total": len(resolution_rows),
            "all_total": len(all_rows),
        },
        "label_count_table": label_count_table,
        "scene_count_table": scene_label_counts(all_rows),
        "raw_baseline": raw_metrics,
        "format_eval": format_metrics,
        "resolution_eval": resolution_metrics,
        "all_metrics": all_metrics,
        "overall_accuracy": raw_metrics["overall_accuracy"],
        "ai_accuracy": raw_metrics["ai_accuracy"],
        "real_accuracy": raw_metrics["real_accuracy"],
        "per_scene_accuracy": raw_metrics["per_scene_accuracy"],
        "per_format_accuracy": format_metrics["per_format_accuracy"],
        "per_resolution_accuracy": resolution_metrics["per_resolution_accuracy"],
        "false_positive_count": all_metrics["false_positive_count"],
        "false_negative_count": all_metrics["false_negative_count"],
        "uncertain_count": all_metrics["uncertain_count"],
        "uncertain_rate": all_metrics["uncertain_rate"],
        "format_flip_rate": format_flip["format_flip_rate"],
        "resolution_flip_rate": resolution_flip["resolution_flip_rate"],
        "source_level_accuracy": source_accuracy["source_level_accuracy"],
        "source_level_accuracy_detail": source_accuracy,
        "hard_candidate_count": all_metrics["hard_candidate_count"],
        "format_flip": {
            **format_flip,
            "flips": format_flip["flips"][:50],
        },
        "resolution_flip": {
            **resolution_flip,
            "flips": resolution_flip["flips"][:50],
        },
        "false_positive_clusters": top_error_clusters(all_rows, "false_positive"),
        "false_negative_clusters": top_error_clusters(all_rows, "false_negative"),
    }
    write_json(SUMMARY_JSON, summary)
    write_markdown_report(summary)

    print(json.dumps({
        "raw_count": len(raw_rows),
        "format_count": len(format_rows),
        "resolution_count": len(resolution_rows),
        "raw_overall_accuracy": raw_metrics["overall_accuracy"],
        "format_flip_rate": format_flip["format_flip_rate"],
        "resolution_flip_rate": resolution_flip["resolution_flip_rate"],
        "hard_candidate_count": all_metrics["hard_candidate_count"],
        "summary_json": display_path(SUMMARY_JSON),
        "summary_report": display_path(SUMMARY_MD),
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
