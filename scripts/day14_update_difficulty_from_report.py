from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAY14_ROOT = PROJECT_ROOT / "data" / "test_images" / "day14_expansion"
METADATA_PATH = DAY14_ROOT / "metadata" / "day14_metadata.csv"
REPORTS_DIR = PROJECT_ROOT / "reports" / "day14"
RAW_RESULTS_CSV = REPORTS_DIR / "day14_raw_baseline_results.csv"
FORMAT_RESULTS_CSV = REPORTS_DIR / "day14_format_eval_results.csv"
RESOLUTION_RESULTS_CSV = REPORTS_DIR / "day14_resolution_eval_results.csv"
SUMMARY_JSON = REPORTS_DIR / "day14_summary_metrics.json"

UPDATE_REPORT_MD = REPORTS_DIR / "day14_difficulty_update_report.md"
HARD_SAMPLES_CSV = REPORTS_DIR / "day14_hard_samples.csv"
HARD_SOURCE_IMAGES_CSV = REPORTS_DIR / "day14_hard_source_images.csv"
STABILITY_ISSUE_SOURCES_CSV = REPORTS_DIR / "day14_stability_issue_sources.csv"

NEW_FIELDS = [
    "source_difficulty",
    "source_difficulty_source",
    "source_difficulty_reason",
    "variant_difficulty",
    "variant_difficulty_source",
    "variant_difficulty_reason",
    "stability_issue",
    "stability_issue_type",
    "needs_manual_review",
]

HARD_SAMPLE_FIELDS = [
    "image_id",
    "label",
    "scene_type",
    "variant",
    "current_filename",
    "current_format",
    "resolution_type",
    "score",
    "final_label",
    "source_difficulty",
    "source_difficulty_source",
    "source_difficulty_reason",
    "variant_difficulty",
    "variant_difficulty_source",
    "variant_difficulty_reason",
    "review_reason",
    "stability_issue_type",
    "needs_manual_review",
    "source_path",
]

HARD_SOURCE_FIELDS = [
    "image_id",
    "label",
    "scene_type",
    "raw_score",
    "raw_final_label",
    "source_difficulty",
    "source_difficulty_source",
    "source_difficulty_reason",
    "stability_issue_type",
    "hard_variant_count",
    "needs_manual_review",
]

STABILITY_FIELDS = [
    "image_id",
    "label",
    "scene_type",
    "stability_issue_type",
    "format_png_final_label",
    "format_jpg_q95_final_label",
    "resolution_flip_families",
    "needs_manual_review",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def eval_filename(row: dict[str, str]) -> str:
    source_path = row.get("source_path", "")
    if source_path:
        return Path(source_path).name
    return row.get("current_filename", "")


def result_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("image_id", ""),
        row.get("variant", ""),
        row.get("resolution_type", ""),
        eval_filename(row),
    )


def metadata_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("image_id", ""),
        row.get("variant", ""),
        row.get("resolution_type", ""),
        row.get("current_filename", ""),
    )


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def near(score: float | None, low: float, high: float) -> bool:
    return score is not None and low <= score <= high


def resolution_family(variant: str) -> str:
    return "jpg_q95" if variant.startswith("jpg_q95") else "png"


def combine_issue_type(has_format_flip: bool, has_resolution_flip: bool) -> str:
    if has_format_flip and has_resolution_flip:
        return "format_and_resolution_flip"
    if has_format_flip:
        return "format_flip"
    if has_resolution_flip:
        return "resolution_flip"
    return "none"


def load_eval_results() -> tuple[list[dict[str, str]], dict[tuple[str, str, str, str], dict[str, str]]]:
    rows = []
    for path in (RAW_RESULTS_CSV, FORMAT_RESULTS_CSV, RESOLUTION_RESULTS_CSV):
        rows.extend(read_csv(path))
    by_key = {}
    for row in rows:
        by_key[result_key(row)] = row
    return rows, by_key


def format_flip_by_source(format_rows: list[dict[str, str]]) -> tuple[set[str], dict[str, dict[str, str]]]:
    variants: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in format_rows:
        if row.get("variant") in {"png", "jpg_q95"}:
            variants[row["image_id"]][row["variant"]] = row
    flip_sources = set()
    details = {}
    for image_id, items in variants.items():
        if {"png", "jpg_q95"} <= set(items):
            png_label = items["png"].get("final_label", "")
            jpg_label = items["jpg_q95"].get("final_label", "")
            details[image_id] = {
                "format_png_final_label": png_label,
                "format_jpg_q95_final_label": jpg_label,
            }
            if png_label != jpg_label:
                flip_sources.add(image_id)
    return flip_sources, details


def resolution_flip_by_source(
    format_rows: list[dict[str, str]], resolution_rows: list[dict[str, str]]
) -> tuple[set[str], dict[str, list[str]]]:
    grouped: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in format_rows + resolution_rows:
        variant = row.get("variant", "")
        if variant not in {
            "png",
            "jpg_q95",
            "png_long1024",
            "jpg_q95_long1024",
            "png_long768",
            "jpg_q95_long768",
            "png_long512",
            "jpg_q95_long512",
        }:
            continue
        family = resolution_family(variant)
        resolution_type = row.get("resolution_type", "")
        grouped[(row.get("image_id", ""), family)][resolution_type] = row.get("final_label", "")

    flip_sources = set()
    flip_families: dict[str, list[str]] = defaultdict(list)
    required = {"native", "long1024", "long768", "long512"}
    for (image_id, family), labels_by_res in grouped.items():
        if required <= set(labels_by_res) and len(set(labels_by_res.values())) > 1:
            flip_sources.add(image_id)
            flip_families[image_id].append(family)
    return flip_sources, {key: sorted(value) for key, value in flip_families.items()}


def source_difficulty_for(
    label: str,
    raw_result: dict[str, str] | None,
    has_format_flip: bool,
    has_resolution_flip: bool,
) -> tuple[str, str, str]:
    if raw_result is None:
        return "unknown", "unmatched_eval", "Raw native baseline result was not found."

    final_label = raw_result.get("final_label", "")
    score = safe_float(raw_result.get("score"))
    has_flip = has_format_flip or has_resolution_flip
    if label == "ai":
        if final_label == "real":
            return "hard", "baseline_error", "AI native image predicted as real."
        if final_label == "uncertain":
            return "hard", "baseline_uncertain", "AI native image entered uncertain zone."
        if near(score, 0.12, 0.20):
            return "hard", "baseline_score", "AI native score near decision boundary."
        if has_flip:
            return "hard", "stability_flip", "AI image label changed across format or resolution variants."
        if final_label == "ai" and score is not None and score >= 0.25:
            return "easy", "baseline_score", "AI image predicted correctly with high confidence and stable variants."
        return "medium", "baseline_score", "AI image predicted correctly but confidence or stability is not strong enough."

    if final_label == "ai":
        return "hard", "baseline_error", "Real native image predicted as AI."
    if final_label == "uncertain":
        return "hard", "baseline_uncertain", "Real native image entered uncertain zone."
    if near(score, 0.10, 0.18):
        return "hard", "baseline_score", "Real native score near decision boundary."
    if has_flip:
        return "hard", "stability_flip", "Real image label changed across format or resolution variants."
    if final_label == "real" and score is not None and score <= 0.08:
        return "easy", "baseline_score", "Real image predicted correctly with low AI score and stable variants."
    return "medium", "baseline_score", "Real image predicted correctly but confidence or stability is not strong enough."


def variant_difficulty_for(label: str, result: dict[str, str] | None) -> tuple[str, str, str]:
    if result is None:
        return "unknown", "unmatched_eval", "Evaluation result was not found for this metadata row."

    final_label = result.get("final_label", "")
    score = safe_float(result.get("score"))
    if label == "ai":
        if final_label == "real":
            return "hard", "baseline_error", "AI variant predicted as real."
        if final_label == "uncertain":
            return "hard", "baseline_uncertain", "AI variant entered uncertain zone."
        if near(score, 0.12, 0.20):
            return "hard", "baseline_score", "AI variant score near decision boundary."
        if final_label == "ai" and score is not None and score >= 0.25:
            return "easy", "baseline_score", "AI variant predicted correctly with high confidence."
        return "medium", "baseline_score", "AI variant predicted correctly but confidence is not strong enough."

    if final_label == "ai":
        return "hard", "baseline_error", "Real variant predicted as AI."
    if final_label == "uncertain":
        return "hard", "baseline_uncertain", "Real variant entered uncertain zone."
    if near(score, 0.10, 0.18):
        return "hard", "baseline_score", "Real variant score near decision boundary."
    if final_label == "real" and score is not None and score <= 0.08:
        return "easy", "baseline_score", "Real variant predicted correctly with low AI score."
    return "medium", "baseline_score", "Real variant predicted correctly but confidence is not strong enough."


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    if not rows:
        return "_None_"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def counter_rows(counter: Counter[Any], key_name: str = "key") -> list[dict[str, Any]]:
    return [{key_name: key, "count": value} for key, value in counter.most_common()]


def paired_counter_rows(counter: Counter[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"label": key[0], "scene_type": key[1], "count": value}
        for key, value in counter.most_common()
    ]


def main() -> int:
    metadata_rows = read_csv(METADATA_PATH)
    original_fields = list(metadata_rows[0].keys()) if metadata_rows else []
    output_fields = original_fields + [field for field in NEW_FIELDS if field not in original_fields]

    raw_rows = read_csv(RAW_RESULTS_CSV)
    format_rows = read_csv(FORMAT_RESULTS_CSV)
    resolution_rows = read_csv(RESOLUTION_RESULTS_CSV)
    eval_rows, eval_by_key = load_eval_results()
    summary_json = read_json(SUMMARY_JSON)

    format_flip_sources, format_flip_details = format_flip_by_source(format_rows)
    resolution_flip_sources, resolution_flip_families = resolution_flip_by_source(format_rows, resolution_rows)
    raw_by_image_id = {row["image_id"]: row for row in raw_rows}

    metadata_keys = {metadata_key(row) for row in metadata_rows}
    eval_keys = {result_key(row) for row in eval_rows}
    unmatched_eval_rows = sorted(eval_keys - metadata_keys)

    source_info: dict[str, dict[str, str]] = {}
    metadata_by_image: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in metadata_rows:
        metadata_by_image[row["image_id"]].append(row)

    for image_id, rows in metadata_by_image.items():
        label = rows[0]["label"]
        scene_type = rows[0]["scene_type"]
        has_format_flip = image_id in format_flip_sources
        has_resolution_flip = image_id in resolution_flip_sources
        issue_type = combine_issue_type(has_format_flip, has_resolution_flip)
        difficulty, source, reason = source_difficulty_for(
            label=label,
            raw_result=raw_by_image_id.get(image_id),
            has_format_flip=has_format_flip,
            has_resolution_flip=has_resolution_flip,
        )
        source_info[image_id] = {
            "image_id": image_id,
            "label": label,
            "scene_type": scene_type,
            "source_difficulty": difficulty,
            "source_difficulty_source": source,
            "source_difficulty_reason": reason,
            "stability_issue": "true" if issue_type != "none" else "false",
            "stability_issue_type": issue_type,
        }

    updated_rows = []
    hard_samples = []
    unmatched_metadata_rows = []
    for row in metadata_rows:
        updated = dict(row)
        key = metadata_key(row)
        result = eval_by_key.get(key)
        if result is None:
            unmatched_metadata_rows.append(key)
        src = source_info[row["image_id"]]
        variant_diff, variant_source, variant_reason = variant_difficulty_for(row["label"], result)
        needs_review = (
            src["source_difficulty"] == "hard"
            or variant_diff == "hard"
            or src["stability_issue"] == "true"
            or result is None
        )

        updated["source_difficulty"] = src["source_difficulty"]
        updated["source_difficulty_source"] = src["source_difficulty_source"]
        updated["source_difficulty_reason"] = src["source_difficulty_reason"]
        updated["variant_difficulty"] = variant_diff
        updated["variant_difficulty_source"] = variant_source
        updated["variant_difficulty_reason"] = variant_reason
        updated["stability_issue"] = src["stability_issue"]
        updated["stability_issue_type"] = src["stability_issue_type"]
        updated["needs_manual_review"] = "true" if needs_review else "false"
        if "difficulty" in updated:
            updated["difficulty"] = src["source_difficulty"]
        updated_rows.append(updated)

        if needs_review:
            hard_samples.append(
                {
                    "image_id": row["image_id"],
                    "label": row["label"],
                    "scene_type": row["scene_type"],
                    "variant": row["variant"],
                    "current_filename": row["current_filename"],
                    "current_format": row["current_format"],
                    "resolution_type": row["resolution_type"],
                    "score": result.get("score", "") if result else "",
                    "final_label": result.get("final_label", "") if result else "",
                    "source_difficulty": src["source_difficulty"],
                    "source_difficulty_source": src["source_difficulty_source"],
                    "source_difficulty_reason": src["source_difficulty_reason"],
                    "variant_difficulty": variant_diff,
                    "variant_difficulty_source": variant_source,
                    "variant_difficulty_reason": variant_reason,
                    "review_reason": variant_reason if variant_diff == "hard" else src["source_difficulty_reason"],
                    "stability_issue_type": src["stability_issue_type"],
                    "needs_manual_review": "true",
                    "source_path": result.get("source_path", "") if result else "",
                }
            )

    hard_source_rows = []
    for image_id, src in sorted(source_info.items()):
        raw_result = raw_by_image_id.get(image_id, {})
        if src["source_difficulty"] == "hard" or src["stability_issue"] == "true":
            hard_variant_count = sum(
                1
                for row in updated_rows
                if row["image_id"] == image_id and row.get("variant_difficulty") == "hard"
            )
            hard_source_rows.append(
                {
                    "image_id": image_id,
                    "label": src["label"],
                    "scene_type": src["scene_type"],
                    "raw_score": raw_result.get("score", ""),
                    "raw_final_label": raw_result.get("final_label", ""),
                    "source_difficulty": src["source_difficulty"],
                    "source_difficulty_source": src["source_difficulty_source"],
                    "source_difficulty_reason": src["source_difficulty_reason"],
                    "stability_issue_type": src["stability_issue_type"],
                    "hard_variant_count": hard_variant_count,
                    "needs_manual_review": "true",
                }
            )

    stability_rows = []
    for image_id, src in sorted(source_info.items()):
        if src["stability_issue_type"] == "none":
            continue
        details = format_flip_details.get(image_id, {})
        stability_rows.append(
            {
                "image_id": image_id,
                "label": src["label"],
                "scene_type": src["scene_type"],
                "stability_issue_type": src["stability_issue_type"],
                "format_png_final_label": details.get("format_png_final_label", ""),
                "format_jpg_q95_final_label": details.get("format_jpg_q95_final_label", ""),
                "resolution_flip_families": ";".join(resolution_flip_families.get(image_id, [])),
                "needs_manual_review": "true",
            }
        )

    write_csv(METADATA_PATH, output_fields, updated_rows)
    write_csv(HARD_SAMPLES_CSV, HARD_SAMPLE_FIELDS, hard_samples)
    write_csv(HARD_SOURCE_IMAGES_CSV, HARD_SOURCE_FIELDS, hard_source_rows)
    write_csv(STABILITY_ISSUE_SOURCES_CSV, STABILITY_FIELDS, stability_rows)

    source_counter = Counter((info["label"], info["source_difficulty"]) for info in source_info.values())
    variant_counter = Counter(row["variant_difficulty"] for row in updated_rows)
    hard_by_scene = Counter((row["label"], row["scene_type"]) for row in hard_samples)
    hard_by_label = Counter(row["label"] for row in hard_samples)
    hard_by_reason = Counter(row["review_reason"] for row in hard_samples)
    stability_counter = Counter(row["stability_issue_type"] for row in stability_rows)

    format_only_count = sum(1 for row in stability_rows if row["stability_issue_type"] == "format_flip")
    resolution_only_count = sum(1 for row in stability_rows if row["stability_issue_type"] == "resolution_flip")
    both_count = sum(1 for row in stability_rows if row["stability_issue_type"] == "format_and_resolution_flip")

    top_review = sorted(
        hard_source_rows,
        key=lambda row: (
            -int(row["hard_variant_count"]),
            row["label"],
            row["scene_type"],
            row["image_id"],
        ),
    )[:30]

    stats = {
        "source_easy_ai_count": source_counter.get(("ai", "easy"), 0),
        "source_medium_ai_count": source_counter.get(("ai", "medium"), 0),
        "source_hard_ai_count": source_counter.get(("ai", "hard"), 0),
        "source_easy_real_count": source_counter.get(("real", "easy"), 0),
        "source_medium_real_count": source_counter.get(("real", "medium"), 0),
        "source_hard_real_count": source_counter.get(("real", "hard"), 0),
        "variant_easy_count": variant_counter.get("easy", 0),
        "variant_medium_count": variant_counter.get("medium", 0),
        "variant_hard_count": variant_counter.get("hard", 0),
        "hard_by_scene_type": paired_counter_rows(hard_by_scene),
        "hard_by_label": counter_rows(hard_by_label, "label"),
        "hard_by_reason": counter_rows(hard_by_reason, "reason"),
        "format_flip_source_count": len(format_flip_sources),
        "resolution_flip_source_count": len(resolution_flip_sources),
        "format_and_resolution_flip_source_count": both_count,
        "format_only_flip_source_count": format_only_count,
        "resolution_only_flip_source_count": resolution_only_count,
        "needs_manual_review_count": sum(1 for row in updated_rows if row["needs_manual_review"] == "true"),
        "metadata_total_rows": len(updated_rows),
        "unmatched_metadata_rows": len(unmatched_metadata_rows),
        "unmatched_eval_rows": len(unmatched_eval_rows),
    }

    warning_lines = []
    if unmatched_metadata_rows:
        warning_lines.append(f"- Unmatched metadata rows: {len(unmatched_metadata_rows)}")
    if unmatched_eval_rows:
        warning_lines.append(f"- Unmatched eval rows: {len(unmatched_eval_rows)}")
    if not warning_lines:
        warning_lines.append("- None")

    report = f"""# Day14 Difficulty Update Report

## 1. Update Goal

Update `day14_metadata.csv` with source-level and variant-level difficulty fields derived only from Day14 baseline evaluation outputs, then produce hard sample and stability issue review lists.

## 2. Rules Used

- Source difficulty uses raw native result plus format and resolution stability flips.
- Variant difficulty uses that variant's own `final_label`, `score`, and `is_uncertain` state.
- AI near-boundary scores use `0.12` to `0.20`.
- Real near-boundary scores use `0.10` to `0.18`.
- Existing `difficulty` is synchronized to `source_difficulty` for backward compatibility.

## 3. Why No Subjective Image Judging

`difficulty` here means how difficult the current detector finds the sample, not whether the image looks realistic, attractive, or visually complex. The update uses only baseline CSV results so the labels are reproducible and auditable.

## 4. Source-Level Difficulty Distribution

| label | easy | medium | hard |
| --- | --- | --- | --- |
| ai | {stats["source_easy_ai_count"]} | {stats["source_medium_ai_count"]} | {stats["source_hard_ai_count"]} |
| real | {stats["source_easy_real_count"]} | {stats["source_medium_real_count"]} | {stats["source_hard_real_count"]} |

## 5. Variant-Level Difficulty Distribution

| difficulty | count |
| --- | --- |
| easy | {stats["variant_easy_count"]} |
| medium | {stats["variant_medium_count"]} |
| hard | {stats["variant_hard_count"]} |

## 6. Hard Source Images Distribution

{markdown_table(paired_counter_rows(Counter((row["label"], row["scene_type"]) for row in hard_source_rows)), ["label", "scene_type", "count"])}

## 7. Hard Samples By Scene Type

{markdown_table(stats["hard_by_scene_type"], ["label", "scene_type", "count"])}

## 8. Hard Samples By Label

{markdown_table(stats["hard_by_label"], ["label", "count"])}

## 9. Stability Issue Distribution

| stability_issue_type | source_count |
| --- | --- |
| format_flip | {format_only_count} |
| resolution_flip | {resolution_only_count} |
| format_and_resolution_flip | {both_count} |
| any_format_flip | {len(format_flip_sources)} |
| any_resolution_flip | {len(resolution_flip_sources)} |

## 10. Top 30 Image IDs For Manual Review

{markdown_table(top_review, ["image_id", "label", "scene_type", "raw_score", "raw_final_label", "source_difficulty_source", "stability_issue_type", "hard_variant_count"])}

## 11. Warnings

{chr(10).join(warning_lines)}

## 12. Day15 Suggestions

- Start with `day14_stability_issue_sources.csv`, because resolution flips dominate Day14 instability.
- Review Real false-positive hard sources before changing threshold or score weights.
- Keep format flip investigation secondary; PNG/JPG flips were much smaller than resolution flips.
- Use `source_difficulty` for dataset balancing and `variant_difficulty` for stress-test slicing.
"""
    UPDATE_REPORT_MD.write_text(report, encoding="utf-8")

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
