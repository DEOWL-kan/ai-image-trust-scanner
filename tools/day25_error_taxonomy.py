from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.error_taxonomy import (  # noqa: E402
    Day25InputError,
    ERROR_TAXONOMY,
    build_analysis,
    build_calibrated_analysis,
    json_default,
)


SAMPLES_JSON = "day25_error_taxonomy_samples.json"
SUMMARY_CSV = "day25_error_taxonomy_summary.csv"
RANKING_CSV = "day25_fix_priority_ranking.csv"
REPORT_MD = "day25_error_taxonomy_report.md"
CALIBRATED_SAMPLES_JSON = "day25_1_error_taxonomy_samples.json"
CALIBRATED_SUMMARY_CSV = "day25_1_error_taxonomy_summary.csv"
CALIBRATED_RANKING_CSV = "day25_1_fix_priority_ranking.csv"
CALIBRATED_REPORT_MD = "day25_1_error_taxonomy_calibrated_report.md"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                    for key, value in row.items()
                }
            )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in row) + " |")
    return "\n".join(lines)


def top_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return rows[:limit]


def samples_by_type(samples: list[dict[str, Any]], error_type: str, limit: int = 8) -> list[dict[str, Any]]:
    return [
        sample
        for sample in sorted(samples, key=lambda item: (-float(item.get("fix_priority_score") or 0), str(item.get("sample_id"))))
        if sample.get("error_type") == error_type
    ][:limit]


def render_sample_table(samples: list[dict[str, Any]]) -> str:
    if not samples:
        return "No samples found for this section."
    return table(
        ["sample_id", "error_type", "root_cause", "severity", "priority", "scenario", "format"],
        [
            [
                sample.get("sample_id"),
                sample.get("error_type"),
                sample.get("primary_root_cause"),
                sample.get("severity"),
                sample.get("fix_priority_score"),
                sample.get("scenario"),
                sample.get("format"),
            ]
            for sample in samples
        ],
    )


def calibrated_top_causes(samples: list[dict[str, Any]], error_type: str, limit: int = 8) -> str:
    selected = [sample for sample in samples if sample.get("error_type") == error_type]
    if not selected:
        return "No samples found for this section."
    counts: dict[str, dict[str, Any]] = {}
    for sample in selected:
        tag = str(sample.get("primary_root_cause") or "unknown")
        item = counts.setdefault(tag, {"count": 0, "strong": 0, "medium": 0, "weak": 0, "samples": []})
        item["count"] += 1
        item[str(sample.get("primary_root_cause_strength") or "weak")] += 1
        item["samples"].append(sample.get("sample_id"))
    rows = []
    for tag, item in sorted(counts.items(), key=lambda pair: (-pair[1]["count"], pair[0]))[:limit]:
        rows.append([tag, item["count"], item["strong"], item["medium"], item["weak"], ", ".join(item["samples"][:3])])
    return table(["primary_root_cause", "count", "strong", "medium", "weak", "representative_samples"], rows)


def render_strength_rule_summary() -> str:
    return "\n".join(
        [
            "- `strong`: direct flip evidence, high-confidence FP/FN evidence, high lift, or explicit score-margin evidence.",
            "- `medium`: elevated cohort lift, uncertain samples with supporting evidence, or relevant debug risk factors without direct flip proof.",
            "- `weak`: field/path/surface evidence only; weak generic tags cannot become primary unless no better calibrated evidence exists.",
            "- Primary selection prefers strong over medium over weak, then applies product-specific precedence such as `no_exif_jpeg` for real-photo FP and `realistic_ai` for AI->Real FN.",
        ]
    )


def render_before_after(original: dict[str, Any] | None, calibrated: dict[str, Any]) -> str:
    original_counts = {}
    if original:
        for row in original.get("taxonomy_summary", []):
            original_counts[str(row.get("root_cause"))] = row.get("sample_count", 0)
    calibrated_rows = {str(row.get("tag")): row for row in calibrated["taxonomy_summary"]}
    tags = sorted(set(original_counts) | set(calibrated_rows))
    rows = []
    for tag in tags:
        row = calibrated_rows.get(tag, {})
        weak = int(row.get("weak_count", 0) or 0)
        medium = int(row.get("medium_count", 0) or 0)
        strong = int(row.get("strong_count", 0) or 0)
        primary = int(row.get("primary_count", 0) or 0)
        explanation = "calibrated evidence required"
        if original_counts.get(tag, 0) and not strong and not primary:
            explanation = "mostly weak evidence after calibration"
        elif strong < original_counts.get(tag, 0):
            explanation = "surface signals downgraded unless supported by lift/flip/margin evidence"
        rows.append([tag, original_counts.get(tag, 0), weak, medium, strong, primary, explanation])
    return table(["tag", "Day25 count", "Day25.1 weak", "Day25.1 medium", "Day25.1 strong", "primary_count", "change explanation"], rows)


def render_folder_table(rows: list[dict[str, Any]], limit: int = 20) -> str:
    return table(
        ["folder", "total", "errors", "error_rate", "global_error_rate", "lift", "dominant_error_type", "source_folder_bias_strength"],
        [
            [
                row["folder"],
                row["total_samples"],
                row["error_samples"],
                row["error_rate"],
                row["global_error_rate"],
                row["lift"],
                row["dominant_error_type"],
                row["source_folder_bias_strength"],
            ]
            for row in rows[:limit]
        ],
    )


def render_format_table(rows: list[dict[str, Any]]) -> str:
    return table(
        ["format", "total", "errors", "error_rate", "FP", "FN", "uncertain", "lift", "format_bias_strength"],
        [
            [
                row["format"],
                row["total_samples"],
                row["error_samples"],
                row["error_rate"],
                row["fp_rate"],
                row["fn_rate"],
                row["uncertain_rate"],
                row["lift"],
                row["format_bias_strength"],
            ]
            for row in rows
        ],
    )


def render_summary_for_tags(summary: list[dict[str, Any]], tags: set[str]) -> str:
    rows = [row for row in summary if row.get("tag") in tags]
    if not rows:
        return "No calibrated samples found for these tags."
    return table(
        ["tag", "weak", "medium", "strong", "primary", "FP", "FN", "Uncertain", "recommended_fix"],
        [
            [
                row["tag"],
                row["weak_count"],
                row["medium_count"],
                row["strong_count"],
                row["primary_count"],
                row["fp_count"],
                row["fn_count"],
                row["uncertain_count"],
                row["recommended_fix_category"],
            ]
            for row in rows
        ],
    )


def render_calibrated_report(calibrated: dict[str, Any], original: dict[str, Any] | None = None) -> str:
    ranking_table = table(
        ["Rank", "Tag", "Affected", "Strong", "Primary", "Score", "Severity", "Fix Category", "Need Model"],
        [
            [
                row["rank"],
                row["tag"],
                row["affected_samples"],
                row["strong_count"],
                row["primary_count"],
                row["fix_priority_score"],
                row["severity"],
                row["recommended_fix_category"],
                "yes" if row["model_change_required"] else "no",
            ]
            for row in calibrated["fix_priority_ranking"]
        ],
    )
    summary_table = table(
        ["tag", "weak", "medium", "strong", "total", "strong_ratio", "primary", "FP", "FN", "Uncertain", "recommended_fix"],
        [
            [
                row["tag"],
                row["weak_count"],
                row["medium_count"],
                row["strong_count"],
                row["total_count"],
                row["strong_ratio"],
                row["primary_count"],
                row["fp_count"],
                row["fn_count"],
                row["uncertain_count"],
                row["recommended_fix_category"],
            ]
            for row in calibrated["taxonomy_summary"]
        ],
    )
    samples = calibrated["samples"]
    return f"""# Day25.1 Error Taxonomy Calibrated Report

Generated: {calibrated["generated_at"]}

## 1. Day25.1 Summary

- Records loaded: {calibrated["total_records_loaded"]}
- Error samples analyzed: {calibrated["total_error_samples"]}
- Source records file: `{calibrated["records_file"]}`
- Global error rate: {calibrated["calibration_context"]["global_error_rate"]}
- Day26 recommendation: {calibrated["day26_recommendation"]}

## 2. Why Calibration Was Needed

Day25 correctly produced a system-wide taxonomy, but generic surface signals were too broad: `format_bias`, `metadata_dependency`, and `source_folder_bias` could be assigned from ordinary file/path/EXIF presence. Day25.1 separates weak surface evidence from medium/strong evidence so root causes are more diagnostic.

## 3. Evidence Strength Rules

{render_strength_rule_summary()}

## 4. Before vs After Root Cause Distribution

{render_before_after(original, calibrated)}

## 5. Calibrated FP Root Cause Analysis

{calibrated_top_causes(samples, "FP")}

## 6. Calibrated FN Root Cause Analysis

{calibrated_top_causes(samples, "FN")}

## 7. Calibrated Uncertain Root Cause Analysis

{calibrated_top_causes(samples, "Uncertain")}

## 8. Folder-level Bias Analysis

{render_folder_table(calibrated["folder_bias_analysis"])}

## 9. Format-level Bias Analysis

{render_format_table(calibrated["format_bias_analysis"])}

## 10. Metadata Dependency Analysis

{render_summary_for_tags(calibrated["taxonomy_summary"], {"metadata_dependency", "no_exif_jpeg"})}

## 11. Score Overlap and Uncertain Boundary Analysis

{render_summary_for_tags(calibrated["taxonomy_summary"], {"score_overlap", "uncertain_boundary"})}

## 12. Resolution Flip Analysis

{render_summary_for_tags(calibrated["taxonomy_summary"], {"resolution_flip"})}

## 13. Realistic AI Miss Analysis

{render_summary_for_tags(calibrated["taxonomy_summary"], {"realistic_ai"})}

## 14. Calibrated Fix Priority Ranking

{ranking_table}

## 15. Day26 Recommendation

{calibrated["day26_recommendation"]}

## 16. Whether Model Change Is Needed

Model-change-required root causes: {calibrated["model_change_required_count"]}.

## 17. Limitations

- Calibration is deterministic evidence scoring, not causal proof.
- Weak evidence is preserved in JSON for auditability but excluded from generic primary selection.
- Flip detection uses available base-image naming patterns and benchmark evidence; richer explicit pair IDs would improve precision.
- No detector weights, uncertain thresholds, or model-training paths were changed.
"""


def render_report(analysis: dict[str, Any]) -> str:
    summary = analysis["taxonomy_summary"]
    ranking = analysis["fix_priority_ranking"]
    samples = analysis["samples"]
    detected_files = analysis["input_files_detected"]["files"][:25]
    error_distribution = table(
        ["Root Cause", "Samples", "Share", "Main Scenarios", "Risk", "Recommended Fix", "Model Change", "Day26"],
        [
            [
                row["root_cause"],
                row["sample_count"],
                f"{row['percentage']}%",
                row["main_scenarios"],
                row["risk_level"],
                row["recommended_fix_category"],
                "yes" if row["model_change_needed"] else "no",
                row["day26_priority"],
            ]
            for row in summary
        ],
    )
    ranking_table = table(
        ["Rank", "Root Cause", "Affected", "Score", "Severity", "Fix Category", "Need Model", "Day26"],
        [
            [
                row["rank"],
                row["root_cause"],
                row["affected_samples"],
                row["fix_priority_score"],
                row["severity"],
                row["recommended_fix_category"],
                "yes" if row["model_change_needed"] else "no",
                row["day26_priority"],
            ]
            for row in ranking
        ],
    )
    taxonomy_lines = "\n".join(f"- `{key}`: {value}" for key, value in ERROR_TAXONOMY.items())
    input_lines = "\n".join(
        f"- `{item['relative_path']}` ({item['kind']}, {item['size_bytes']} bytes)"
        for item in detected_files
    )
    root_cause_table = table(
        ["Root Cause", "Count", "Share", "Representative Samples"],
        [
            [
                row["root_cause"],
                row["sample_count"],
                f"{row['percentage']}%",
                ", ".join(row["representative_samples"]),
            ]
            for row in summary
        ],
    )
    representative = render_sample_table(analysis["representative_samples"])
    fp_samples = render_sample_table(samples_by_type(samples, "FP"))
    fn_samples = render_sample_table(samples_by_type(samples, "FN"))
    uncertain_samples = render_sample_table(samples_by_type(samples, "Uncertain"))
    model_needed = [row for row in ranking if row["model_change_needed"]]
    no_model_first = [row for row in ranking if not row["model_change_needed"]]
    return f"""# Day25 Error Taxonomy Report

Generated: {analysis["generated_at"]}

## 1. Day25 Summary

- Records loaded: {analysis["total_records_loaded"]}
- Error samples analyzed: {analysis["total_error_samples"]}
- Source records file: `{analysis["records_file"]}`
- Day26 recommendation: {analysis["day26_recommendation"]}

## 2. Input Files Detected

{input_lines or "No relevant files detected."}

## 3. Error Taxonomy Definition

{taxonomy_lines}

## 4. Root Cause Tagging Method

The analyzer normalizes each benchmark or batch-result sample into a common schema, classifies FP / FN / Uncertain / Correct / Unknown from expected and final labels, then scans `debug_evidence`, decision reasons, recommendations, review notes, source folder, file format, scenario, confidence, score, and path text for deterministic evidence. Folder-level concentration is computed before tagging so repeatable source-folder clusters can be labeled as `source_folder_bias`. Scores near the boundary or uncertain-layer interceptions are tagged separately as `score_overlap` and `uncertain_boundary`.

## 5. Error Distribution Table

{error_distribution}

## 6. Root Cause Ranking

{root_cause_table}

## 7. FP Root Cause Analysis

{fp_samples}

## 8. FN Root Cause Analysis

{fn_samples}

## 9. Uncertain Root Cause Analysis

{uncertain_samples}

## 10. Representative Samples

{representative}

## 11. Fix Priority Ranking

{ranking_table}

## 12. Day26 Recommendation

{analysis["day26_recommendation"]}

Start with the highest-ranked non-model fix when possible:
{table(["Root Cause", "Score", "Fix Category", "Recommended Fix"], [[row["root_cause"], row["fix_priority_score"], row["recommended_fix_category"], row["recommended_fix"]] for row in no_model_first[:5]]) if no_model_first else "No non-model fix candidates were ranked."}

## 13. Whether Model Change Is Needed

Model-change-required root causes: {len(model_needed)}.

{table(["Root Cause", "Affected", "Score"], [[row["root_cause"], row["affected_samples"], row["fix_priority_score"]] for row in model_needed]) if model_needed else "No Day26 model change is recommended. Keep detector weights and uncertain_decision_v21 thresholds unchanged."}

## 14. Limitations

- Root-cause tags are deterministic evidence tags, not causal proof.
- `unknown` remains visible when evidence is insufficient.
- Existing benchmark evidence may contain missing scenario or difficulty fields.
- The report intentionally does not change detector weights, uncertain thresholds, or training/model configuration.
"""


def write_outputs(analysis: dict[str, Any], reports_dir: Path) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    samples_path = reports_dir / SAMPLES_JSON
    summary_path = reports_dir / SUMMARY_CSV
    ranking_path = reports_dir / RANKING_CSV
    report_path = reports_dir / REPORT_MD
    write_json(samples_path, analysis["samples"])
    write_csv(summary_path, analysis["taxonomy_summary"])
    write_csv(ranking_path, analysis["fix_priority_ranking"])
    report_path.write_text(render_report(analysis), encoding="utf-8")
    return {
        "samples_json": samples_path,
        "summary_csv": summary_path,
        "ranking_csv": ranking_path,
        "report_md": report_path,
    }


def write_calibrated_outputs(
    calibrated: dict[str, Any],
    reports_dir: Path,
    original: dict[str, Any] | None = None,
) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    samples_path = reports_dir / CALIBRATED_SAMPLES_JSON
    summary_path = reports_dir / CALIBRATED_SUMMARY_CSV
    ranking_path = reports_dir / CALIBRATED_RANKING_CSV
    report_path = reports_dir / CALIBRATED_REPORT_MD
    write_json(samples_path, calibrated["samples"])
    write_csv(summary_path, calibrated["taxonomy_summary"])
    write_csv(ranking_path, calibrated["fix_priority_ranking"])
    report_path.write_text(render_calibrated_report(calibrated, original), encoding="utf-8")
    return {
        "calibrated_samples_json": samples_path,
        "calibrated_summary_csv": summary_path,
        "calibrated_ranking_csv": ranking_path,
        "calibrated_report_md": report_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day25 error taxonomy, root cause tagging, and fix priority ranking.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=None)
    parser.add_argument("--calibrated", action="store_true", help="Generate Day25.1 calibrated evidence-strength outputs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    reports_dir = args.reports_dir.resolve() if args.reports_dir else project_root / "reports"
    try:
        analysis = build_calibrated_analysis(project_root) if args.calibrated else build_analysis(project_root)
        original_analysis = build_analysis(project_root) if args.calibrated else None
    except Day25InputError as exc:
        print(f"Day25 input error: {exc}", file=sys.stderr)
        return 2
    outputs = write_calibrated_outputs(analysis, reports_dir, original_analysis) if args.calibrated else write_outputs(analysis, reports_dir)
    print("Day25.1 Calibrated Error Taxonomy completed." if args.calibrated else "Day25 Error Taxonomy completed.")
    print(f"Records loaded: {analysis['total_records_loaded']}")
    print(f"Error samples analyzed: {analysis['total_error_samples']}")
    print("Outputs:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    if args.calibrated:
        print("Top 5 strong root causes:")
        for row in top_rows(analysis["taxonomy_summary"], 5):
            print(f"- {row['tag']}: strong={row['strong_count']}, medium={row['medium_count']}, weak={row['weak_count']}, primary={row['primary_count']}")
        print("Top 5 calibrated fix priorities:")
        for row in top_rows(analysis["fix_priority_ranking"], 5):
            print(f"- #{row['rank']} {row['tag']}: score {row['fix_priority_score']} via {row['recommended_fix_category']}")
    else:
        print("Top 5 root causes:")
        for row in top_rows(analysis["taxonomy_summary"], 5):
            print(f"- {row['root_cause']}: {row['sample_count']} samples ({row['percentage']}%)")
        print("Top 5 fix priorities:")
        for row in top_rows(analysis["fix_priority_ranking"], 5):
            print(f"- #{row['rank']} {row['root_cause']}: score {row['fix_priority_score']} via {row['recommended_fix_category']}")
    print(f"Day26 recommendation: {analysis['day26_recommendation']}")
    print(f"Model change required count: {analysis['model_change_required_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
