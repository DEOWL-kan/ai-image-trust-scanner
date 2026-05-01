from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.score_fusion import load_detector_weight_config  # noqa: E402


PREDICTIONS_CSV = PROJECT_ROOT / "reports" / "day8" / "day8_predictions.csv"
IMAGE_REPORT_DIR = PROJECT_ROOT / "reports" / "day8" / "image_reports"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "day9"
CONFIG_PATH = PROJECT_ROOT / "configs" / "detector_weights.json"
BASELINE_ACTIVE_WEIGHT = 0.80
BASELINE_EXPERIMENT_WEIGHT = 2.00
THRESHOLDS = {
    "balanced": 0.15,
    "conservative": 0.18,
}
CSV_FIELDS = [
    "profile_name",
    "threshold",
    "accuracy",
    "precision",
    "recall",
    "specificity",
    "f1",
    "fp",
    "fn",
    "tp",
    "tn",
    "notes",
]


@dataclass(frozen=True)
class Sample:
    filename: str
    ground_truth: str
    report: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day9 feature-weight ablation experiments.")
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
        help="Day8 per-image reports. Default: reports/day8/image_reports",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Detector weight config. Default: configs/detector_weights.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory. Default: reports/day9",
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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def read_samples(predictions_csv: Path, image_report_dir: Path) -> list[Sample]:
    if not predictions_csv.exists():
        raise FileNotFoundError(f"Predictions CSV not found: {predictions_csv}")
    with predictions_csv.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    samples: list[Sample] = []
    for row in rows:
        filename = row.get("filename", "")
        if not filename:
            continue
        report_path = image_report_dir / f"{Path(filename).stem}_report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Image report not found: {report_path}")
        samples.append(
            Sample(
                filename=filename,
                ground_truth=row.get("ground_truth", ""),
                report=json.loads(report_path.read_text(encoding="utf-8")),
            )
        )
    if not samples:
        raise ValueError("No samples were loaded for Day9 weight ablation.")
    return samples


def component_scores(report: dict[str, Any]) -> dict[str, float]:
    raw = report.get("final_result", {}).get("component_scores", {})
    return {
        "metadata": safe_float(raw.get("metadata_score")),
        "forensic": safe_float(raw.get("forensic_score")),
        "frequency": safe_float(raw.get("frequency_score")),
        "model": safe_float(raw.get("model_score")),
    }


def ai_tool_metadata_signal(report: dict[str, Any]) -> float:
    software = str(report.get("metadata_result", {}).get("software") or "").lower()
    terms = ("openai", "chatgpt", "dall", "midjourney", "stable diffusion", "comfyui", "firefly")
    return 1.0 if any(term in software for term in terms) else 0.0


def metadata_signal(report: dict[str, Any]) -> float:
    metadata = report.get("metadata_result", {})
    if ai_tool_metadata_signal(report):
        return 1.0
    if not metadata.get("checked"):
        return 0.20
    return 0.18 if not metadata.get("has_exif") else 0.0


def edge_signal(report: dict[str, Any]) -> float:
    edge_density = safe_float(report.get("forensic_result", {}).get("edge_density"))
    low_edge = clamp((0.065 - edge_density) / 0.065)
    high_edge = clamp((edge_density - 0.22) / 0.18)
    return max(low_edge, high_edge * 0.6)


def noise_signal(report: dict[str, Any]) -> float:
    noise = safe_float(report.get("forensic_result", {}).get("noise_estimate"))
    return clamp((4.0 - noise) / 4.0)


def blur_signal(report: dict[str, Any]) -> float:
    laplacian = safe_float(report.get("forensic_result", {}).get("laplacian_variance"))
    return clamp((350.0 - laplacian) / 350.0)


def texture_signal(report: dict[str, Any]) -> float:
    return clamp((edge_signal(report) + noise_signal(report) + blur_signal(report)) / 3.0)


def compression_signal(report: dict[str, Any]) -> float:
    image_info = report.get("image_info", {})
    metadata = report.get("metadata_result", {})
    image_format = str(image_info.get("format") or "").upper()
    if image_format in {"JPEG", "JPG"} and not metadata.get("has_exif"):
        return 0.30
    if image_format == "PNG" and not metadata.get("has_exif"):
        return 0.06
    if image_format == "WEBP":
        return 0.20
    return 0.0


def color_signal(report: dict[str, Any]) -> float:
    stds = report.get("forensic_result", {}).get("color_channel_std", {})
    values = [safe_float(stds.get(key)) for key in ("red", "green", "blue")]
    avg_std = sum(values) / len(values) if values else 0.0
    return clamp((42.0 - avg_std) / 42.0)


def frequency_signal(report: dict[str, Any]) -> float:
    return clamp(safe_float(report.get("frequency_result", {}).get("frequency_score")))


def concept_signals(report: dict[str, Any]) -> dict[str, float]:
    return {
        "texture_weight": texture_signal(report),
        "edge_weight": edge_signal(report),
        "noise_weight": noise_signal(report),
        "compression_weight": compression_signal(report),
        "metadata_weight": metadata_signal(report),
        "color_weight": color_signal(report),
        "blur_penalty_weight": blur_signal(report),
        "frequency_weight": frequency_signal(report),
    }


def has_natural_real_context(report: dict[str, Any]) -> bool:
    image_info = report.get("image_info", {})
    metadata = report.get("metadata_result", {})
    forensic = report.get("forensic_result", {})
    image_format = str(image_info.get("format") or "").upper()
    has_exif = bool(metadata.get("has_exif"))
    noise = safe_float(forensic.get("noise_estimate"))
    laplacian = safe_float(forensic.get("laplacian_variance"))
    edge_density = safe_float(forensic.get("edge_density"))
    brightness_std = safe_float(forensic.get("brightness_std"))
    return (
        image_format in {"JPEG", "JPG"}
        and (has_exif or (noise >= 4.0 and laplacian >= 350 and brightness_std >= 35 and 0.035 <= edge_density <= 0.22))
    )


def balanced_v2_score(report: dict[str, Any], profile: dict[str, Any]) -> float:
    baseline_score = safe_float(report.get("final_result", {}).get("final_score"))
    scores = component_scores(report)
    fusion_weights = profile.get("fusion_weights", {})
    component_score = sum(
        scores[key] * safe_float(fusion_weights.get(key))
        for key in ("metadata", "forensic", "frequency", "model")
    ) / BASELINE_ACTIVE_WEIGHT
    blended = (baseline_score * 0.84) + (component_score * 0.16)

    image_info = report.get("image_info", {})
    metadata = report.get("metadata_result", {})
    image_format = str(image_info.get("format") or "").upper()
    if image_format in {"JPEG", "JPG"} and not metadata.get("has_exif"):
        blended -= min(0.018, scores["frequency"] * 0.018)
    if has_natural_real_context(report):
        blended -= min(0.012, scores["forensic"] * 0.05)
    return round(clamp(blended), 6)


def profile_score(report: dict[str, Any], profile_name: str, profile: dict[str, Any]) -> float:
    baseline_score = safe_float(report.get("final_result", {}).get("final_score"))
    if profile_name in {"baseline", "review_safe_candidate"}:
        return round(clamp(baseline_score), 6)
    if profile_name == "balanced_v2_candidate":
        return balanced_v2_score(report, profile)

    scores = component_scores(report)
    fusion_weights = profile.get("fusion_weights", {})
    component_score = sum(
        scores[key] * safe_float(fusion_weights.get(key))
        for key in ("metadata", "forensic", "frequency", "model")
    ) / BASELINE_ACTIVE_WEIGHT

    signals = concept_signals(report)
    experiment_weights = profile.get("experiment_weights", {})
    concept_score = sum(
        signals[key] * safe_float(experiment_weights.get(key))
        for key in signals
    ) / BASELINE_EXPERIMENT_WEIGHT

    # Blend the existing Day8 component score with experimental concept signals.
    # This keeps the ablation comparable while allowing feature-level profiles to move scores.
    return round(clamp((component_score * 0.72) + (concept_score * 0.28)), 6)


def predicted_label(score: float, threshold: float) -> str:
    return "AI-generated" if score >= threshold else "Real"


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def f1(precision: float, recall: float) -> float:
    return round((2 * precision * recall) / (precision + recall), 4) if precision + recall else 0.0


def evaluate_profile(
    samples: list[Sample],
    profile_name: str,
    profile: dict[str, Any],
    threshold: float,
) -> dict[str, Any]:
    tp = tn = fp = fn = low_confidence = 0
    low_confidence_margin = safe_float(
        profile.get("experiment_weights", {}).get("low_confidence_margin"),
        0.03,
    )
    for sample in samples:
        score = profile_score(sample.report, profile_name, profile)
        prediction = predicted_label(score, threshold)
        if abs(score - threshold) <= low_confidence_margin:
            low_confidence += 1
        if sample.ground_truth == "AI-generated" and prediction == "AI-generated":
            tp += 1
        elif sample.ground_truth == "AI-generated" and prediction == "Real":
            fn += 1
        elif sample.ground_truth == "Real" and prediction == "AI-generated":
            fp += 1
        elif sample.ground_truth == "Real" and prediction == "Real":
            tn += 1

    total = tp + tn + fp + fn
    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    specificity = safe_ratio(tn, tn + fp)
    return {
        "profile_name": profile_name,
        "threshold": f"{threshold:.2f}",
        "accuracy": f"{safe_ratio(tp + tn, total):.4f}",
        "precision": f"{precision:.4f}",
        "recall": f"{recall:.4f}",
        "specificity": f"{specificity:.4f}",
        "f1": f"{f1(precision, recall):.4f}",
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "tn": tn,
        "notes": f"{profile.get('notes', '')} low_confidence_cases={low_confidence}",
    }


def sort_float(row: dict[str, Any], key: str) -> float:
    return safe_float(row.get(key), 0.0)


def choose_balanced(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        [row for row in rows if row["threshold"] == f"{THRESHOLDS['balanced']:.2f}"],
        key=lambda row: (
            -sort_float(row, "accuracy"),
            abs(int(row["fp"]) - int(row["fn"])),
            -sort_float(row, "f1"),
            int(row["fp"]) + int(row["fn"]),
        ),
    )[0]


def choose_conservative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        [row for row in rows if row["threshold"] == f"{THRESHOLDS['conservative']:.2f}"],
        key=lambda row: (int(row["fp"]), -sort_float(row, "specificity"), -sort_float(row, "f1"), int(row["fn"])),
    )[0]


def conservative_stress_test(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row["profile_name"] == "reduce_false_positive" and row["threshold"] == f"{THRESHOLDS['conservative']:.2f}":
            return row
    return choose_conservative(rows)


def choose_current_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        rows,
        key=lambda row: (-sort_float(row, "accuracy"), -sort_float(row, "f1"), int(row["fp"]) + int(row["fn"])),
    )[0]


def row_line(row: dict[str, Any]) -> str:
    return (
        f"{row['profile_name']} @ {row['threshold']} "
        f"(accuracy {row['accuracy']}, precision {row['precision']}, recall {row['recall']}, "
        f"specificity {row['specificity']}, F1 {row['f1']}, FP {row['fp']}, FN {row['fn']})"
    )


def render_summary(rows: list[dict[str, Any]], output_dir: Path, config_path: Path) -> str:
    balanced = choose_balanced(rows)
    stress_test = conservative_stress_test(rows)
    current = choose_current_dataset(rows)

    lines = [
        "# Day9 Weight Ablation Summary",
        "",
        "## Scope",
        "",
        "- This is a configurable feature-weight experiment on the current 60-image Day8 test set.",
        "- It does not change the production/default detector decision path.",
        f"- Config source: `{display_path(config_path)}`",
        "- Dataset size: 30 AI images and 30 real images.",
        "- Results are small-scale stage results, not production-grade model claims.",
        "",
        "## Experiment Results",
        "",
        "| Profile | Threshold | Accuracy | Precision | Recall | Specificity | F1 | FP | FN | TP | TN |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['profile_name']} | {row['threshold']} | {row['accuracy']} | {row['precision']} | "
            f"{row['recall']} | {row['specificity']} | {row['f1']} | {row['fp']} | "
            f"{row['fn']} | {row['tp']} | {row['tn']} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Reading",
            "",
            f"- Best balanced-mode candidate: {row_line(balanced)}.",
            f"- Conservative stress-test profile: {row_line(stress_test)}.",
            "- The conservative stress-test lowers false positives by sacrificing all AI recall, so it is not suitable as a default conservative mode.",
            f"- Best metric row on the current 60-image test set: {row_line(current)}.",
            "- Default recommendation remains `baseline @ 0.15` because candidate gains are diagnostic only and must be validated outside this test set.",
            "",
            "## Interpretation",
            "",
            "- `baseline` preserves the Day8 score behavior and remains the regression reference.",
            "- `balanced_v2_candidate` lightly reduces frequency, forensic, and compression influence while keeping missing EXIF weak.",
            "- `review_safe_candidate` preserves baseline binary scores but expands low-confidence routing for uncertain review.",
            "- `reduce_false_positive` intentionally lowers weak provenance, compression/context, and blur-like signals to reduce real-image false positives.",
            "- `improve_ai_recall` intentionally raises smooth-texture, local-consistency, frequency, and edge-anomaly signals to reduce AI false negatives.",
            "- In this run, `reduce_false_positive` is only a conservative stress-test candidate because it lowers FP by sacrificing all AI recall.",
            "- In this run, `improve_ai_recall` proves which signals can reduce FN, but its FP count is too high for a balanced default.",
            "- If a profile improves one metric while worsening another, treat it as an operating-mode tradeoff rather than a universal improvement.",
            "",
            "## Overfitting Risk",
            "",
            "- Overfitting risk is high because this experiment uses only 60 samples: 30 AI and 30 real.",
            "- Do not tune the default detector directly to the best row in this table.",
            "- Record these results as Day9 ablation evidence, then validate candidate profiles on a separate holdout set before changing defaults.",
            "- None of these results should be described as production-grade detection performance.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(output_dir / 'day9_weight_ablation.csv')}`",
            f"- `{display_path(output_dir / 'day9_weight_ablation_summary.md')}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run(
    predictions_csv: Path,
    image_report_dir: Path,
    config_path: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    predictions_csv = resolve_path(predictions_csv)
    image_report_dir = resolve_path(image_report_dir)
    config_path = resolve_path(config_path)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_detector_weight_config(config_path)
    profiles = config.get("profiles", {})
    required = [
        "baseline",
        "balanced_v2_candidate",
        "review_safe_candidate",
        "reduce_false_positive",
        "improve_ai_recall",
    ]
    missing = [name for name in required if name not in profiles]
    if missing:
        raise ValueError(f"Detector weight config is missing profiles: {', '.join(missing)}")

    samples = read_samples(predictions_csv, image_report_dir)
    rows: list[dict[str, Any]] = []
    for profile_name in required:
        profile = profiles[profile_name]
        for threshold in THRESHOLDS.values():
            rows.append(evaluate_profile(samples, profile_name, profile, threshold))

    write_csv(output_dir / "day9_weight_ablation.csv", rows)
    (output_dir / "day9_weight_ablation_summary.md").write_text(
        render_summary(rows, output_dir, config_path),
        encoding="utf-8",
    )
    return rows


def main() -> int:
    args = parse_args()
    try:
        rows = run(args.predictions, args.image_report_dir, args.config, args.output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Day9 weight ablation failed: {exc}", file=sys.stderr)
        return 1

    for row in rows:
        print(row_line(row))
    print(f"CSV: {display_path(resolve_path(args.output_dir) / 'day9_weight_ablation.csv')}")
    print(f"Summary: {display_path(resolve_path(args.output_dir) / 'day9_weight_ablation_summary.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
