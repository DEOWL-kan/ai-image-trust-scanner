from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIRNAME = "reports"
SCAN_DIR_NAMES = ("reports", "data", "outputs", "artifacts", "backend", "frontend")
TEXT_EXTENSIONS = {".json", ".csv", ".md"}

ERROR_TAXONOMY: dict[str, str] = {
    "format_bias": "格式相关偏差，例如 PNG/JPEG 转换后判断明显变化，或某格式集中误判",
    "resolution_flip": "分辨率缩放后 label 或 risk_level 发生不稳定变化",
    "no_exif_jpeg": "无 EXIF 的真实 JPEG 被误判为 AI 或高风险",
    "high_compression": "高压缩、社交平台压缩、低质量 JPEG 导致误判",
    "low_texture": "低纹理、纯色背景、天空、墙面、雾天、水面等细节不足场景",
    "realistic_ai": "高真实感 AI 图，纹理、光照、构图接近真实照片，导致 FN 或 uncertain",
    "source_folder_bias": "样本来源文件夹或采集方式导致模型学到来源偏差，而不是图像真实性",
    "metadata_dependency": "过度依赖 EXIF、文件格式、文件名、路径、编码信息等非视觉证据",
    "score_overlap": "AI / Real 分数分布重叠，样本处于决策边界附近",
    "uncertain_boundary": "结果不是明确 FP/FN，而是被 uncertain 层拦截或置信度不足",
    "unknown": "无法从现有 evidence 判断原因",
}

RECOMMENDATION_BY_TAG: dict[str, str] = {
    "format_bias": "data_pipeline_fix",
    "resolution_flip": "benchmark_protocol_fix",
    "no_exif_jpeg": "metadata_handling_fix",
    "high_compression": "decision_policy_patch",
    "low_texture": "decision_policy_patch",
    "realistic_ai": "model_training_needed",
    "source_folder_bias": "data_pipeline_fix",
    "metadata_dependency": "metadata_handling_fix",
    "score_overlap": "uncertainty_policy_fix",
    "uncertain_boundary": "uncertainty_policy_fix",
    "unknown": "no_action_yet",
}

FIX_DESCRIPTION: dict[str, str] = {
    "decision_policy_patch": "改产品级决策策略，不改模型",
    "data_pipeline_fix": "修数据集/格式/来源偏差",
    "metadata_handling_fix": "降低或校准 metadata 依赖",
    "uncertainty_policy_fix": "优化 uncertain 输出和用户解释",
    "benchmark_protocol_fix": "补测试协议或分场景指标",
    "model_training_needed": "后续接预训练模型或训练模型",
    "no_action_yet": "样本不足，暂不处理",
}

SEVERITY_WEIGHT = {"critical": 30, "high": 22, "medium": 12, "low": 5}
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
STRENGTH_SCORE = {"weak": 25, "medium": 60, "strong": 90}
STRENGTH_RANK = {"weak": 1, "medium": 2, "strong": 3}


class Day25InputError(RuntimeError):
    """Raised when Day25 cannot find enough upstream evidence to analyze."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_default(value: Any) -> str:
    return str(value)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def get_nested(source: Any, dotted_key: str, default: Any = None) -> Any:
    current = source
    for part in dotted_key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def first_value(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = get_nested(source, key) if "." in key else source.get(key)
        if value not in (None, ""):
            return value
    return default


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 1.0 < number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 4)


def normalize_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    if label in {"ai", "ai_generated", "likely_ai", "generated", "artificial", "synthetic"}:
        return "ai"
    if label in {"real", "real_photo", "likely_real", "photo", "camera", "authentic"}:
        return "real"
    if label in {"uncertain", "unknown", "review", "needs_review", "inconclusive"}:
        return "uncertain"
    return "unknown"


def classify_error_type(expected_label: Any, predicted_label: Any, record: dict[str, Any] | None = None) -> str:
    record = record or {}
    expected = normalize_label(expected_label)
    predicted = normalize_label(predicted_label)
    if predicted == "uncertain" or bool(record.get("is_uncertain")):
        return "Uncertain"
    if expected == "real" and predicted == "ai":
        return "FP"
    if expected == "ai" and predicted == "real":
        return "FN"
    if expected in {"ai", "real"} and expected == predicted:
        return "Correct"
    return "Unknown"


def compact_text(value: Any, limit: int = 320) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=json_default)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def text_blob(*values: Any) -> str:
    return " ".join(compact_text(value, limit=4000).lower() for value in values if value not in (None, ""))


def has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def infer_format(record: dict[str, Any], path_text: str) -> str:
    fmt = first_value(record, "format", "format_group", "image_format", "file_ext", "ext")
    if not fmt:
        fmt = Path(path_text).suffix.lower().lstrip(".")
    return str(fmt or "unknown").lower().replace("jpeg", "jpg")


def infer_resolution(record: dict[str, Any], scenario: str, path_text: str) -> str:
    width = first_value(
        record,
        "width",
        "image_width",
        "image_info.width",
        "debug_evidence.format_info.width",
        "debug_evidence.raw_debug_evidence.format_info.width",
        "debug_evidence.feature_summary.raw_debug_evidence.format_info.width",
        "debug_evidence.raw_result.image_info.width",
        "debug_evidence.feature_summary.raw_debug_evidence.raw_result.image_info.width",
    )
    height = first_value(
        record,
        "height",
        "image_height",
        "image_info.height",
        "debug_evidence.format_info.height",
        "debug_evidence.raw_debug_evidence.format_info.height",
        "debug_evidence.feature_summary.raw_debug_evidence.format_info.height",
        "debug_evidence.raw_result.image_info.height",
        "debug_evidence.feature_summary.raw_debug_evidence.raw_result.image_info.height",
    )
    text = f"{scenario} {path_text}".lower()
    for marker in ("long_512", "long_768", "long_1024", "long_1536", "long_edge_512", "long_edge_768", "long_edge_1024", "long_edge_1536"):
        if marker in text:
            return marker.replace("long_edge_", "long_")
    try:
        if width and height:
            return f"{int(width)}x{int(height)}"
    except (TypeError, ValueError):
        pass
    return "unknown"


def stable_sample_id(record: dict[str, Any], index: int, source_file: Path) -> str:
    explicit = first_value(record, "id", "sample_id")
    if explicit:
        return str(explicit)
    path_text = str(first_value(record, "image_path", "file_path", "path", "source_path", "filename", default=f"sample_{index}"))
    digest = hashlib.sha1(f"{source_file}|{path_text}|{index}".encode("utf-8")).hexdigest()[:16]
    return digest


def detect_input_files(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    detected: list[dict[str, Any]] = []
    for dirname in SCAN_DIR_NAMES:
        root = project_root / dirname
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            rel = path.relative_to(project_root).as_posix()
            lowered = rel.lower()
            score = 0
            for keyword, weight in (
                ("day24", 80),
                ("error_gallery", 70),
                ("error_review", 70),
                ("benchmark", 45),
                ("day23", 45),
                ("batch", 25),
                ("api_history", 20),
                ("confusion", 20),
                ("scenario", 15),
                ("summary", 10),
                ("result", 10),
            ):
                if keyword in lowered:
                    score += weight
            if score:
                detected.append(
                    {
                        "path": str(path),
                        "relative_path": rel,
                        "size_bytes": path.stat().st_size,
                        "score": score,
                        "kind": classify_input_file(path),
                    }
                )
    detected.sort(key=lambda item: (-int(item["score"]), item["relative_path"]))
    return {
        "files": detected,
        "day24_files": [item for item in detected if "day24" in item["relative_path"].lower()],
        "benchmark_files": [item for item in detected if item["kind"] == "benchmark_results"],
        "review_files": [item for item in detected if item["kind"] == "review_notes"],
        "summary_files": [item for item in detected if item["kind"] == "summary"],
    }


def classify_input_file(path: Path) -> str:
    name = path.name.lower()
    rel = str(path).lower()
    if "review" in name and path.suffix.lower() == ".json":
        return "review_notes"
    if "benchmark" in rel and "results" in name and path.suffix.lower() in {".json", ".csv"}:
        return "benchmark_results"
    if "summary" in name:
        return "summary"
    if "batch" in name or "api_history" in rel:
        return "batch_history"
    if "report" in name:
        return "report"
    return "evidence"


def choose_records_file(detected: dict[str, Any], project_root: Path) -> Path | None:
    candidates = []
    for item in detected["files"]:
        path = Path(item["path"])
        name = path.name.lower()
        if path.suffix.lower() not in {".json", ".csv"}:
            continue
        if item["kind"] in {"review_notes", "summary", "report"}:
            continue
        bonus = 0
        if item["kind"] == "benchmark_results":
            bonus += 100
        if path.suffix.lower() == ".json":
            bonus += 10
        if "day23_benchmark_results" in name:
            bonus += 80
        if "day24" in name and ("sample" in name or "error" in name):
            bonus += 40
        candidates.append((int(item["score"]) + bonus, str(path), path))
    if not candidates:
        default_path = project_root / "data" / "benchmark_outputs" / "day23" / "day23_benchmark_results.json"
        return default_path if default_path.exists() else None
    return sorted(candidates, key=lambda item: (-item[0], item[1]))[0][2]


def load_records(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    if path.suffix.lower() == ".json":
        data = load_json(path, [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("items", "results", "samples", "errors"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_review_map(detected: dict[str, Any]) -> dict[str, Any]:
    for item in detected["review_files"]:
        data = load_json(Path(item["path"]), {})
        reviews = data.get("reviews") if isinstance(data, dict) else None
        if isinstance(reviews, dict):
            return reviews
    return {}


def normalize_record(record: dict[str, Any], index: int, source_file: Path, review: dict[str, Any] | None = None) -> dict[str, Any]:
    path_text = str(first_value(record, "image_path", "file_path", "path", "source_path", default="") or "")
    filename = str(first_value(record, "filename", "file_name", default=Path(path_text).name or f"sample_{index}"))
    expected = normalize_label(first_value(record, "expected_label", "true_label", "ground_truth", "label", "target_label"))
    predicted = normalize_label(first_value(record, "predicted_label", "final_label", "prediction", "decision", "label_pred"))
    scenario = str(first_value(record, "scenario", "scene", "category", default="unknown") or "unknown")
    source_folder = str(first_value(record, "source_folder", "parent_folder", default=Path(path_text).parent.as_posix() or "unknown")).replace("\\", "/")
    fmt = infer_format(record, path_text or filename)
    confidence = safe_float(first_value(record, "confidence", "decision_confidence"))
    score = safe_float(first_value(record, "ai_score", "score", "raw_score", "probability", "ai_probability"))
    error_type = classify_error_type(expected, predicted, record)
    sample_id = stable_sample_id(record, index, source_file)
    review = review or {}
    return {
        "sample_id": sample_id,
        "image_path": path_text or None,
        "filename": filename,
        "expected_label": expected,
        "predicted_label": predicted,
        "final_label": predicted,
        "error_type": error_type,
        "confidence": confidence,
        "score": score,
        "risk_level": str(first_value(record, "risk_level", "risk", default="unknown") or "unknown").lower(),
        "scenario": scenario,
        "source_folder": source_folder,
        "format": fmt,
        "resolution": infer_resolution(record, scenario, path_text),
        "debug_evidence": first_value(record, "debug_evidence", "debug", default={}) or {},
        "decision_reason": first_value(record, "decision_reason", "reason", "decision_reasons"),
        "recommendation_raw": first_value(record, "recommendation", "recommended_action"),
        "review": review,
        "source_file": str(source_file),
        "benchmark_index": index,
    }


def has_missing_exif(item: dict[str, Any], corpus: str) -> bool:
    evidence = item.get("debug_evidence")
    nested_candidates = (
        "exif_info.has_exif",
        "feature_summary.raw_debug_evidence.exif_info.has_exif",
        "raw_debug_evidence.exif_info.has_exif",
        "raw_result.metadata_result.has_exif",
        "feature_summary.raw_debug_evidence.raw_result.metadata_result.has_exif",
    )
    if isinstance(evidence, dict):
        for key in nested_candidates:
            value = get_nested(evidence, key)
            if value is False:
                return True
    return "missing_exif" in corpus or "no exif" in corpus or "has_exif\": false" in corpus


def flatten_strings(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(flatten_strings(item))
        return output
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(flatten_strings(item))
        return output
    return [str(value)]


def nested_list_values(source: Any, keys: tuple[str, ...]) -> list[str]:
    output: list[str] = []
    if not isinstance(source, dict):
        return output
    for key in keys:
        value = get_nested(source, key)
        if isinstance(value, list):
            output.extend(str(item) for item in value)
    return output


def has_resolution_instability(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    paths = (
        "multi_resolution",
        "raw_debug_evidence.multi_resolution",
        "feature_summary.raw_debug_evidence.multi_resolution",
    )
    for path in paths:
        value = get_nested(evidence, path)
        if not isinstance(value, dict):
            continue
        flip_count = safe_float(value.get("resolution_flip_count")) or 0.0
        score_range = safe_float(value.get("score_range")) or 0.0
        resize_delta = safe_float(value.get("resize_delta")) or 0.0
        status = str(value.get("consistency_status") or "").lower()
        if bool(value.get("available")) and (flip_count > 0 or score_range >= 0.08 or resize_delta >= 0.08 or "inconsistent" in status):
            return True
    return False


def group_context(items: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {"source_folder": {}, "format": {}}
    for field in output:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            grouped[str(item.get(field) or "unknown")].append(item)
        for key, values in grouped.items():
            errors = [item for item in values if item.get("error_type") in {"FP", "FN", "Uncertain"}]
            output[field][key] = {
                "total": len(values),
                "errors": len(errors),
                "error_rate": round(len(errors) / len(values), 4) if values else 0.0,
            }
    return output


def tag_root_causes(item: dict[str, Any], groups: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    review = item.get("review") or {}
    manual_tag = review.get("manual_tag")
    evidence = item.get("debug_evidence")
    evidence_signals = " ".join(
        nested_list_values(
            evidence,
            (
                "feature_summary.risk_factors",
                "feature_summary.stability_factors",
                "feature_summary.raw_debug_evidence.risk_factors",
                "feature_summary.raw_debug_evidence.stability_factors",
                "feature_summary.raw_debug_evidence.uncertainty_flags",
                "raw_debug_evidence.risk_factors",
                "raw_debug_evidence.stability_factors",
                "raw_debug_evidence.uncertainty_flags",
                "uncertainty_flags",
                "risk_factors",
                "stability_factors",
            ),
        )
    ).lower()
    path_signal = text_blob(
        item.get("image_path"),
        item.get("filename"),
        item.get("scenario"),
        item.get("source_folder"),
        item.get("decision_reason"),
        item.get("recommendation_raw"),
        review.get("reviewer_note"),
        manual_tag,
        evidence_signals,
    )
    corpus = text_blob(
        item.get("image_path"),
        item.get("filename"),
        item.get("scenario"),
        item.get("source_folder"),
        item.get("format"),
        item.get("debug_evidence"),
        item.get("decision_reason"),
        item.get("recommendation_raw"),
        review.get("reviewer_note"),
        manual_tag,
    )
    tags: list[str] = []
    if manual_tag in ERROR_TAXONOMY and manual_tag != "unknown":
        tags.append(str(manual_tag))
    format_stats = groups.get("format", {}).get(str(item.get("format") or "unknown"), {})
    if (
        has_any(path_signal, ("format", "jpeg_q", "paired_format", "codec", "mime", "jpg", "jpeg", "png", "webp"))
        or "jpeg_container_or_compression" in evidence_signals
        or (format_stats.get("total", 0) >= 20 and format_stats.get("error_rate", 0.0) >= 0.65)
    ):
        tags.append("format_bias")
    if (
        has_resolution_instability(evidence)
        or has_any(path_signal, ("resolution_control", "long_edge", "long_512", "long_768", "long_1024", "long_1536"))
        or has_any(evidence_signals, ("resolution_flip", "resize_delta", "unstable_resolution"))
    ):
        tags.append("resolution_flip")
    if (
        item.get("expected_label") == "real"
        and item.get("format") in {"jpg", "jpeg"}
        and item.get("error_type") in {"FP", "Uncertain"}
        and (item.get("risk_level") in {"high", "critical"} or item.get("predicted_label") == "ai" or item.get("error_type") == "FP")
        and has_missing_exif(item, corpus)
    ):
        tags.append("no_exif_jpeg")
    if has_any(path_signal, ("compression", "quality", "artifact", "block", "social media", "wechat", "low quality", "jpeg_q85", "q85")):
        tags.append("high_compression")
    if has_any(path_signal, ("sky", "wall", "water", "fog", "plain", "minimal", "smooth", "low texture", "low_texture", "低纹理", "天空", "墙", "水面", "雾")):
        tags.append("low_texture")
    if (
        item.get("expected_label") == "ai"
        and item.get("error_type") in {"FN", "Uncertain"}
        and has_any(path_signal, ("photorealistic", "realistic", "smartphone", "ordinary", "真实感", "逼真", "photo-like"))
    ):
        tags.append("realistic_ai")
    folder_stats = groups.get("source_folder", {}).get(str(item.get("source_folder") or "unknown"), {})
    if folder_stats.get("total", 0) >= 5 and folder_stats.get("error_rate", 0.0) >= 0.6:
        tags.append("source_folder_bias")
    metadata_terms = ("exif", "metadata", "filename", "path", "folder", "format", "mime", "codec", "container")
    visual_terms = ("texture", "edge", "noise", "lighting", "composition", "face", "object", "视觉")
    if has_any(path_signal, metadata_terms) and (not has_any(path_signal, visual_terms) or has_any(path_signal, ("missing_exif", "metadata_checked"))):
        tags.append("metadata_dependency")
    confidence = item.get("confidence")
    score = item.get("score")
    if (confidence is not None and float(confidence) <= 0.6) or (score is not None and 0.12 <= float(score) <= 0.2):
        tags.append("score_overlap")
    if item.get("error_type") == "Uncertain" or has_any(evidence_signals, ("uncertain_decision", "score_inside_uncertain_band")):
        tags.append("uncertain_boundary")

    unique_tags = [tag for tag in dict.fromkeys(tags) if tag in ERROR_TAXONOMY]
    return unique_tags or ["unknown"]


def choose_primary_root_cause(tags: list[str]) -> str:
    order = (
        "realistic_ai",
        "no_exif_jpeg",
        "metadata_dependency",
        "resolution_flip",
        "format_bias",
        "high_compression",
        "source_folder_bias",
        "low_texture",
        "score_overlap",
        "uncertain_boundary",
        "unknown",
    )
    for tag in order:
        if tag in tags:
            return tag
    return tags[0] if tags else "unknown"


def severity_for(item: dict[str, Any]) -> str:
    error_type = item.get("error_type")
    confidence = float(item.get("confidence") or 0.0)
    risk_level = str(item.get("risk_level") or "").lower()
    if error_type in {"FP", "FN"} and (confidence >= 0.85 or risk_level in {"high", "critical"}):
        return "critical"
    if error_type in {"FP", "FN"}:
        return "high"
    if error_type == "Uncertain":
        return "medium"
    return "low"


def product_impact_weight(error_type: str) -> int:
    if error_type in {"FP", "FN"}:
        return 20
    if error_type == "Uncertain":
        return 12
    return 2


def feasibility_weight(primary: str) -> int:
    if RECOMMENDATION_BY_TAG.get(primary) == "model_training_needed":
        return 2
    if primary == "unknown":
        return 1
    return 10


def score_samples(samples: list[dict[str, Any]]) -> None:
    primary_counts = Counter(sample["primary_root_cause"] for sample in samples)
    total = max(1, len(samples))
    scenario_by_tag: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        scenario_by_tag[sample["primary_root_cause"]].add(str(sample.get("scenario") or "unknown"))
    for sample in samples:
        primary = sample["primary_root_cause"]
        count_weight = round(min(30.0, primary_counts[primary] / total * 30.0), 2)
        repeatability = min(10, len(scenario_by_tag[primary]) * 2)
        score = (
            count_weight
            + SEVERITY_WEIGHT[sample["severity"]]
            + product_impact_weight(sample["error_type"])
            + repeatability
            + feasibility_weight(primary)
        )
        sample["fix_priority_score"] = round(max(0, min(100, score)), 2)


def recommendation_for(primary: str) -> str:
    category = RECOMMENDATION_BY_TAG.get(primary, "no_action_yet")
    return f"{category}: {FIX_DESCRIPTION[category]}"


def canonical_base_id(item: dict[str, Any]) -> str:
    path_text = str(item.get("image_path") or item.get("filename") or "")
    stem = Path(path_text).stem.lower()
    stem = re.sub(r"__(jpeg|jpg|png|webp)_?q?\d*$", "", stem)
    stem = re.sub(r"__(jpeg|jpg|png|webp)$", "", stem)
    stem = re.sub(r"[_-](jpeg|jpg|png|webp)[_-]?q?\d*$", "", stem)
    stem = re.sub(r"[_-]long[_-]?(edge[_-]?)?\d+$", "", stem)
    return f"{item.get('expected_label') or 'unknown'}::{stem or path_text.lower()}"


def extract_debug_number(item: dict[str, Any], *paths: str) -> float | None:
    evidence = item.get("debug_evidence")
    for path in paths:
        value = get_nested(evidence, path) if isinstance(evidence, dict) else None
        number = safe_float(value)
        if number is not None:
            return number
    return None


def extract_raw_score_threshold_margin(item: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    raw_score = item.get("score")
    if raw_score is None:
        raw_score = extract_debug_number(
            item,
            "raw_score",
            "raw_debug_evidence.raw_score",
            "feature_summary.raw_debug_evidence.raw_score",
        )
    threshold = extract_debug_number(
        item,
        "threshold_used",
        "raw_debug_evidence.threshold_used",
        "feature_summary.raw_debug_evidence.threshold_used",
    )
    margin = extract_debug_number(
        item,
        "score_margin",
        "raw_debug_evidence.score_margin",
        "feature_summary.raw_debug_evidence.score_margin",
    )
    if margin is None and raw_score is not None and threshold is not None:
        margin = abs(float(raw_score) - float(threshold))
    return raw_score, threshold, margin


def component_scores_empty(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return True
    for path in (
        "feature_summary.component_scores",
        "component_scores",
        "raw_debug_evidence.component_scores",
        "feature_summary.raw_debug_evidence.component_scores",
    ):
        value = get_nested(evidence, path)
        if isinstance(value, dict):
            return not bool(value)
    return True


def visual_evidence_present(text: str) -> bool:
    return has_any(text, ("texture", "edge", "noise", "lighting", "composition", "face", "object", "visual", "forensic"))


def errorish(item: dict[str, Any]) -> bool:
    return item.get("error_type") in {"FP", "FN", "Uncertain", "Unknown"}


def high_risk_uncertain(item: dict[str, Any]) -> bool:
    return item.get("error_type") == "Uncertain" and str(item.get("risk_level") or "").lower() in {"high", "critical"}


def strength_entry(strength: str, score: int, reasons: list[str], signals: list[str]) -> dict[str, Any]:
    return {
        "strength": strength,
        "score": max(0, min(100, int(score))),
        "reasons": reasons,
        "signals": signals,
    }


def add_evidence(
    evidence: dict[str, dict[str, Any]],
    tag: str,
    strength: str,
    score: int,
    reason: str,
    signals: list[str],
) -> None:
    existing = evidence.get(tag)
    if existing and int(existing.get("score") or 0) >= score:
        existing.setdefault("reasons", []).append(reason)
        existing.setdefault("signals", []).extend(signals)
        existing["signals"] = list(dict.fromkeys(existing["signals"]))
        return
    evidence[tag] = strength_entry(strength, score, [reason], list(dict.fromkeys(signals)))


def build_calibration_context(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    errors = [item for item in items if errorish(item)]
    global_error_rate = len(errors) / total if total else 0.0

    def grouped_stats(field: str, values: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in values:
            grouped[str(item.get(field) or "unknown")].append(item)
        stats: dict[str, dict[str, Any]] = {}
        for key, group in grouped.items():
            error_group = [item for item in group if errorish(item)]
            counts = Counter(str(item.get("error_type") or "Unknown") for item in error_group)
            dominant = counts.most_common(1)[0] if counts else ("None", 0)
            error_rate = len(error_group) / len(group) if group else 0.0
            stats[key] = {
                "total_samples": len(group),
                "error_samples": len(error_group),
                "error_rate": round(error_rate, 4),
                "fp_rate": round(counts.get("FP", 0) / len(group), 4) if group else 0.0,
                "fn_rate": round(counts.get("FN", 0) / len(group), 4) if group else 0.0,
                "uncertain_rate": round(counts.get("Uncertain", 0) / len(group), 4) if group else 0.0,
                "global_error_rate": round(global_error_rate, 4),
                "lift": round(error_rate / global_error_rate, 4) if global_error_rate else 0.0,
                "dominant_error_type": dominant[0],
                "dominant_error_share": round(dominant[1] / len(error_group), 4) if error_group else 0.0,
            }
        return stats

    folder_stats = grouped_stats("source_folder", items)
    format_stats = grouped_stats("format", items)
    resolution_stats = grouped_stats("resolution", items)
    format_by_expected: dict[str, dict[str, Any]] = {}
    expected_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        expected_groups[str(item.get("expected_label") or "unknown")].append(item)
    for expected, group in expected_groups.items():
        expected_global = sum(1 for item in group if errorish(item)) / len(group) if group else 0.0
        for fmt, stats in grouped_stats("format", group).items():
            local = dict(stats)
            local["expected_label"] = expected
            local["expected_global_error_rate"] = round(expected_global, 4)
            local["expected_lift"] = round(float(stats["error_rate"]) / expected_global, 4) if expected_global else 0.0
            format_by_expected[f"{expected}::{fmt}"] = local

    base_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        base_groups[canonical_base_id(item)].append(item)
    format_flip_bases: set[str] = set()
    resolution_flip_bases: set[str] = set()
    for base_id, group in base_groups.items():
        labels = {str(item.get("final_label") or item.get("predicted_label") or "unknown") for item in group}
        risks = {str(item.get("risk_level") or "unknown") for item in group}
        formats = {str(item.get("format") or "unknown") for item in group}
        resolutions = {str(item.get("resolution") or "unknown") for item in group}
        if len(group) > 1 and len(formats) > 1 and (len(labels) > 1 or len(risks) > 1):
            format_flip_bases.add(base_id)
        if len(group) > 1 and len(resolutions) > 1 and (len(labels) > 1 or len(risks) > 1):
            resolution_flip_bases.add(base_id)

    return {
        "global_error_rate": round(global_error_rate, 4),
        "folder_stats": folder_stats,
        "format_stats": format_stats,
        "format_by_expected": format_by_expected,
        "resolution_stats": resolution_stats,
        "format_flip_bases": format_flip_bases,
        "resolution_flip_bases": resolution_flip_bases,
    }


def folder_bias_strength(stats: dict[str, Any]) -> str:
    if (
        stats.get("total_samples", 0) >= 10
        and float(stats.get("lift") or 0.0) >= 1.5
        and float(stats.get("dominant_error_share") or 0.0) >= 0.6
    ):
        return "strong"
    if stats.get("total_samples", 0) >= 10 and (
        float(stats.get("lift") or 0.0) >= 1.2 or float(stats.get("dominant_error_share") or 0.0) >= 0.6
    ):
        return "medium"
    return "weak"


def format_bias_strength(stats: dict[str, Any]) -> str:
    if float(stats.get("lift") or stats.get("expected_lift") or 0.0) >= 1.5:
        return "strong"
    if float(stats.get("lift") or stats.get("expected_lift") or 0.0) >= 1.2:
        return "medium"
    return "weak"


def add_calibrated_evidence(item: dict[str, Any], context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    raw_debug = item.get("debug_evidence")
    evidence_signals = " ".join(
        nested_list_values(
            raw_debug,
            (
                "feature_summary.risk_factors",
                "feature_summary.stability_factors",
                "feature_summary.raw_debug_evidence.risk_factors",
                "feature_summary.raw_debug_evidence.stability_factors",
                "feature_summary.raw_debug_evidence.uncertainty_flags",
                "raw_debug_evidence.risk_factors",
                "raw_debug_evidence.stability_factors",
                "raw_debug_evidence.uncertainty_flags",
                "uncertainty_flags",
                "risk_factors",
                "stability_factors",
            ),
        )
    ).lower()
    review = item.get("review") or {}
    path_signal = text_blob(
        item.get("image_path"),
        item.get("filename"),
        item.get("scenario"),
        item.get("source_folder"),
        item.get("decision_reason"),
        item.get("recommendation_raw"),
        review.get("reviewer_note"),
        evidence_signals,
    )
    has_missing = has_missing_exif(item, path_signal + " " + text_blob(raw_debug))
    base_id = canonical_base_id(item)
    fmt = str(item.get("format") or "unknown")
    folder = str(item.get("source_folder") or "unknown")
    expected = str(item.get("expected_label") or "unknown")
    folder_stats = context["folder_stats"].get(folder, {})
    format_stats = context["format_stats"].get(fmt, {})
    expected_format_stats = context["format_by_expected"].get(f"{expected}::{fmt}", {})
    resolution_stats = context["resolution_stats"].get(str(item.get("resolution") or "unknown"), {})
    raw_score, threshold, margin = extract_raw_score_threshold_margin(item)
    confidence = item.get("confidence")
    confidence_number = float(confidence) if confidence is not None else None

    if fmt != "unknown" or has_any(path_signal, ("jpg", "jpeg", "png", "webp")):
        add_evidence(evidence, "format_bias", "weak", 20, "Only file format/path information is present.", [fmt])
    if "jpeg_container_or_compression" in evidence_signals:
        add_evidence(evidence, "format_bias", "medium", 55, "JPEG container/compression appears in debug risk factors without direct flip proof.", ["jpeg_container_or_compression"])
    if has_any(path_signal, ("format_control", "paired_format")) and float(expected_format_stats.get("expected_lift") or format_stats.get("lift") or 0.0) >= 1.2:
        add_evidence(evidence, "format_bias", "medium", 65, "Format-control cohort has elevated error lift.", [f"lift={expected_format_stats.get('expected_lift') or format_stats.get('lift')}"])
    if base_id in context["format_flip_bases"]:
        add_evidence(evidence, "format_bias", "strong", 92, "Same base image has format-variant final_label/risk_level flip.", ["format_variant_flip"])
    if float(expected_format_stats.get("expected_lift") or 0.0) >= 1.5:
        add_evidence(evidence, "format_bias", "strong", 88, "Format error lift is >= 1.5 within the same expected label.", [f"expected_lift={expected_format_stats.get('expected_lift')}"])
    if "jpeg_container_or_compression" in evidence_signals and item.get("error_type") in {"FP", "FN"} | ({"Uncertain"} if high_risk_uncertain(item) else set()):
        add_evidence(evidence, "format_bias", "strong", 86, "Format/compression risk factor appears on FP/FN or high-risk uncertain sample.", ["jpeg_container_or_compression"])

    if has_missing or has_any(path_signal, ("metadata", "exif", "filename", "path")):
        add_evidence(evidence, "metadata_dependency", "weak", 20, "Metadata or EXIF signal exists, but causality is not established.", ["metadata_or_exif_present"])
    if has_missing and item.get("error_type") == "Uncertain":
        add_evidence(evidence, "metadata_dependency", "medium", 58, "Missing EXIF is present on an uncertain result.", ["missing_exif", "uncertain"])
    if has_missing and item.get("format") == "png" and item.get("error_type") == "Uncertain":
        add_evidence(evidence, "metadata_dependency", "medium", 55, "PNG/no-EXIF uncertain sample suggests metadata sensitivity but not a hard FP.", ["png_no_exif_uncertain"])
    if has_missing and component_scores_empty(raw_debug) and item.get("error_type") in {"FP", "FN"}:
        add_evidence(evidence, "metadata_dependency", "strong", 82, "Missing EXIF appears while visual component scores are empty.", ["missing_exif", "empty_component_scores"])
    elif has_missing and component_scores_empty(raw_debug) and high_risk_uncertain(item):
        add_evidence(evidence, "metadata_dependency", "strong", 78, "Missing EXIF appears with empty visual component scores on a high-risk uncertain result.", ["missing_exif", "empty_component_scores", "high_risk_uncertain"])
    if (
        item.get("expected_label") == "real"
        and item.get("final_label") == "ai"
        and (confidence_number or 0.0) >= 0.75
        and has_missing
        and not visual_evidence_present(path_signal)
    ):
        add_evidence(evidence, "metadata_dependency", "strong", 88, "High-confidence real->AI FP is driven mainly by non-visual metadata signals.", ["real_fp", "missing_exif"])

    if (
        item.get("expected_label") == "real"
        and item.get("format") in {"jpg", "jpeg"}
        and has_missing
    ):
        add_evidence(evidence, "no_exif_jpeg", "weak", 30, "JPEG has missing EXIF, but strong FP conditions are not all met.", ["jpg", "missing_exif"])
        if item.get("final_label") == "uncertain":
            add_evidence(evidence, "no_exif_jpeg", "medium", 62, "Real JPEG with missing EXIF is intercepted as uncertain.", ["real_jpg_missing_exif_uncertain"])
        if item.get("final_label") == "ai" and ((confidence_number or 0.0) >= 0.75 or item.get("risk_level") == "high"):
            add_evidence(evidence, "no_exif_jpeg", "strong", 94, "Real JPEG missing EXIF becomes high-confidence/high-risk AI FP.", ["real_jpg_missing_exif_fp"])
            add_evidence(evidence, "metadata_dependency", "strong", 86, "No-EXIF JPEG FP is a concrete metadata-dependency case.", ["no_exif_jpeg_fp"])

    if folder != "unknown":
        add_evidence(evidence, "source_folder_bias", "weak", 18, "Source folder is known, but folder-level lift is required for stronger evidence.", [folder])
        strength = folder_bias_strength(folder_stats)
        if strength == "medium":
            add_evidence(evidence, "source_folder_bias", "medium", 58, "Folder error lift or dominant error concentration is elevated.", [f"lift={folder_stats.get('lift')}", f"dominant={folder_stats.get('dominant_error_type')}"])
        elif strength == "strong":
            add_evidence(evidence, "source_folder_bias", "strong", 84, "Folder error lift >= 1.5 and dominant error share >= 60%.", [f"lift={folder_stats.get('lift')}", f"dominant_share={folder_stats.get('dominant_error_share')}"])

    if margin is not None:
        if margin <= 0.01:
            add_evidence(evidence, "score_overlap", "strong", 92, "Raw score is within 0.01 of threshold.", [f"margin={round(margin, 4)}"])
        elif margin <= 0.03:
            add_evidence(evidence, "score_overlap", "medium", 66, "Raw score is within 0.03 of threshold.", [f"margin={round(margin, 4)}"])
    if confidence_number is not None and 0.48 <= confidence_number <= 0.52:
        add_evidence(evidence, "score_overlap", "strong", 90, "Confidence is in the 0.48-0.52 boundary band.", [f"confidence={confidence_number}"])
    elif item.get("final_label") == "uncertain" and confidence_number is not None and confidence_number <= 0.6:
        add_evidence(evidence, "score_overlap", "medium", 62, "Uncertain result has confidence <= 0.6.", [f"confidence={confidence_number}"])

    if item.get("final_label") == "uncertain":
        add_evidence(evidence, "uncertain_boundary", "weak", 28, "Final label is uncertain.", ["final_label=uncertain"])
        score_strength = evidence.get("score_overlap", {}).get("strength")
        if score_strength in {"medium", "strong"}:
            add_evidence(evidence, "uncertain_boundary", "strong", 88, "Uncertain result is backed by medium/strong score-overlap evidence.", [f"score_overlap={score_strength}"])
        elif "uncertain_decision" in evidence_signals:
            add_evidence(evidence, "uncertain_boundary", "medium", 58, "Debug evidence contains uncertain_decision.", ["uncertain_decision"])

    if has_any(path_signal, ("resolution_control", "long_edge", "long_512", "long_768", "long_1024", "long_1536")):
        add_evidence(evidence, "resolution_flip", "weak", 22, "Resolution path/bucket is present without flip evidence.", [str(item.get("resolution") or "unknown")])
    if base_id in context["resolution_flip_bases"] or has_resolution_instability(raw_debug):
        add_evidence(evidence, "resolution_flip", "strong", 90, "Same base image or multi-resolution evidence shows label/risk instability.", ["resolution_flip"])
    elif has_any(path_signal, ("resolution_control", "multi_resolution", "resize", "scale", "consistency")) and float(resolution_stats.get("lift") or 0.0) >= 1.2:
        add_evidence(evidence, "resolution_flip", "medium", 62, "Resolution-control bucket has elevated error lift.", [f"lift={resolution_stats.get('lift')}"])

    if has_any(path_signal, ("jpg", "jpeg")):
        add_evidence(evidence, "high_compression", "weak", 18, "JPEG presence alone is weak compression evidence.", ["jpeg"])
    if "jpeg_container_or_compression" in evidence_signals or has_any(path_signal, ("q95", "q85", "compression", "artifact", "block", "low quality", "wechat", "social media")):
        add_evidence(evidence, "high_compression", "medium", 58, "Compression/container signal is present.", ["compression_signal"])
    if (
        (has_any(path_signal, ("q85", "compression artifact", "block", "low quality")) or "jpeg_container_or_compression" in evidence_signals)
        and item.get("error_type") in {"FP", "FN"}
        and (item.get("risk_level") in {"high", "critical"} or has_any(path_signal, ("q85", "low quality")))
    ):
        add_evidence(evidence, "high_compression", "strong", 84, "Low-quality/compression signal is attached to FP/FN.", ["compression_fp_fn"])

    if (
        item.get("expected_label") == "ai"
        and item.get("final_label") in {"real", "uncertain"}
        and has_any(path_signal, ("photorealistic", "realistic", "smartphone", "ordinary", "real-life", "natural lighting", "photo-like", "真实感", "手机拍摄", "普通照片"))
    ):
        strength = "strong" if item.get("final_label") == "real" else "medium"
        score = 94 if strength == "strong" else 64
        add_evidence(evidence, "realistic_ai", strength, score, "AI sample has realistic/smartphone/ordinary-photo evidence.", ["realistic_ai_text"])
    elif item.get("expected_label") == "ai" and item.get("final_label") == "real":
        add_evidence(evidence, "realistic_ai", "weak", 32, "AI sample was predicted real, but realistic text evidence is absent.", ["ai_to_real"])

    if has_any(path_signal, ("sky", "wall", "water", "fog", "plain", "minimal", "smooth", "low texture", "low_texture", "低纹理", "天空", "墙面", "水面", "雾天")) and errorish(item):
        add_evidence(evidence, "low_texture", "strong", 82, "Low-texture scene/path evidence is present on an error or uncertain result.", ["low_texture_scene"])

    return evidence or {"unknown": strength_entry("weak", 10, ["No calibrated evidence passed the rules."], ["insufficient_evidence"])}


def choose_calibrated_primary(item: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    strong_or_medium = {
        tag: data
        for tag, data in evidence.items()
        if data.get("strength") in {"strong", "medium"} and tag != "unknown"
    }
    candidates = strong_or_medium or {"unknown": strength_entry("weak", 10, ["Only weak root-cause evidence was available."], ["weak_only"])}
    priority_bonus = {
        "no_exif_jpeg": 8 if item.get("expected_label") == "real" and item.get("error_type") == "FP" else 0,
        "realistic_ai": 8 if item.get("expected_label") == "ai" and item.get("error_type") == "FN" else 0,
        "resolution_flip": 6 if evidence.get("resolution_flip", {}).get("strength") == "strong" else 0,
        "score_overlap": 7 if item.get("error_type") == "Uncertain" else 0,
        "uncertain_boundary": 5 if item.get("error_type") == "Uncertain" else 0,
    }
    generic_penalty = {"format_bias": -3, "metadata_dependency": -2, "source_folder_bias": -4}

    def sort_key(pair: tuple[str, dict[str, Any]]) -> tuple[int, int, int, str]:
        tag, data = pair
        strength_rank = STRENGTH_RANK.get(str(data.get("strength")), 0)
        adjusted_score = int(data.get("score") or 0) + priority_bonus.get(tag, 0) + generic_penalty.get(tag, 0)
        return (strength_rank, adjusted_score, int(data.get("score") or 0), tag)

    primary, entry = max(candidates.items(), key=sort_key)
    return primary, entry


def calibration_notes_for(primary: str, evidence: dict[str, dict[str, Any]]) -> str:
    weak_tags = sorted(tag for tag, data in evidence.items() if data.get("strength") == "weak" and tag != primary)
    if not weak_tags:
        return "Primary root cause was selected from the strongest calibrated evidence."
    return f"Weak tags not selected as primary: {', '.join(weak_tags)}."


def score_calibrated_samples(samples: list[dict[str, Any]]) -> None:
    primary_counts = Counter(sample["primary_root_cause"] for sample in samples)
    total = max(1, len(samples))
    for sample in samples:
        strength = str(sample.get("primary_root_cause_strength") or "weak")
        base = {"strong": 55, "medium": 38, "weak": 18}.get(strength, 10)
        count_weight = min(20, primary_counts[sample["primary_root_cause"]] / total * 20)
        impact = product_impact_weight(str(sample.get("error_type") or "Unknown"))
        score = base + count_weight + min(15, impact) + (5 if sample["primary_root_cause"] != "unknown" else 0)
        sample["fix_priority_score"] = round(max(0, min(100, score)), 2)


def analyze_records_calibrated(records: list[dict[str, Any]], source_file: Path, reviews: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reviews = reviews or {}
    normalized = []
    for index, record in enumerate(records):
        sample_id = stable_sample_id(record, index, source_file)
        normalized.append(normalize_record(record, index, source_file, reviews.get(sample_id)))
    context = build_calibration_context(normalized)
    samples = []
    for item in normalized:
        evidence = add_calibrated_evidence(item, context)
        tags = [tag for tag in evidence if tag != "unknown"] or ["unknown"]
        primary, primary_entry = choose_calibrated_primary(item, evidence)
        root_confidence = round(float(primary_entry.get("score") or 0) / 100.0, 4)
        severity = severity_for(item)
        samples.append(
            {
                "sample_id": item["sample_id"],
                "image_path": item["image_path"],
                "expected_label": item["expected_label"],
                "predicted_label": item["predicted_label"],
                "final_label": item["final_label"],
                "error_type": item["error_type"],
                "confidence": item["confidence"],
                "risk_level": item["risk_level"],
                "scenario": item["scenario"],
                "source_folder": item["source_folder"],
                "format": item["format"],
                "resolution": item["resolution"],
                "root_cause_tags": tags,
                "root_cause_evidence": evidence,
                "primary_root_cause": primary,
                "primary_root_cause_strength": primary_entry.get("strength", "weak"),
                "root_cause_confidence": root_confidence,
                "calibration_notes": calibration_notes_for(primary, evidence),
                "severity": severity,
                "fix_priority_score": 0,
                "recommendation": recommendation_for(primary),
                "debug_evidence_summary": compact_text(item.get("debug_evidence")),
                "review_note_summary": compact_text((item.get("review") or {}).get("reviewer_note")),
            }
        )
    score_calibrated_samples(samples)
    return samples, context


def calibrated_root_cause_summary(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    all_tags = sorted({tag for sample in samples for tag in sample.get("root_cause_evidence", {})})
    for tag in all_tags:
        values = [sample for sample in samples if tag in sample.get("root_cause_evidence", {})]
        if not values:
            continue
        strength_counts = Counter(sample["root_cause_evidence"][tag]["strength"] for sample in values)
        primary_values = [sample for sample in values if sample.get("primary_root_cause") == tag]
        error_counts = Counter(str(sample.get("error_type") or "Unknown") for sample in values)
        category = RECOMMENDATION_BY_TAG.get(tag, "no_action_yet")
        rows.append(
            {
                "tag": tag,
                "weak_count": strength_counts.get("weak", 0),
                "medium_count": strength_counts.get("medium", 0),
                "strong_count": strength_counts.get("strong", 0),
                "total_count": len(values),
                "strong_ratio": round(strength_counts.get("strong", 0) / len(values), 4) if values else 0.0,
                "affected_samples": len(values),
                "primary_count": len(primary_values),
                "fp_count": error_counts.get("FP", 0),
                "fn_count": error_counts.get("FN", 0),
                "uncertain_count": error_counts.get("Uncertain", 0),
                "representative_samples": [
                    sample["sample_id"]
                    for sample in sorted(values, key=lambda sample: sample["root_cause_evidence"][tag]["score"], reverse=True)[:3]
                ],
                "recommended_fix": FIX_DESCRIPTION.get(category, FIX_DESCRIPTION["no_action_yet"]),
                "recommended_fix_category": category,
                "model_change_required": category == "model_training_needed",
            }
        )
    rows.sort(key=lambda row: (-int(row["strong_count"]), -int(row["primary_count"]), -int(row["total_count"]), str(row["tag"])))
    return rows


def calibrated_priority_ranking(samples: list[dict[str, Any]], summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = max(1, len(samples))
    rows = []
    for row in summary:
        tag = str(row["tag"])
        values = [sample for sample in samples if tag in sample.get("root_cause_evidence", {})]
        primary_values = [sample for sample in values if sample.get("primary_root_cause") == tag]
        max_severity = max((sample["severity"] for sample in values), key=lambda value: SEVERITY_RANK[value])
        error_counts = Counter(str(sample.get("error_type") or "Unknown") for sample in values)
        impact = 0
        if error_counts.get("FP", 0):
            impact = max(impact, 20)
        if error_counts.get("FN", 0):
            impact = max(impact, 18)
        if error_counts.get("Uncertain", 0):
            impact = max(impact, 12)
        scenarios = {str(sample.get("scenario") or "unknown") for sample in values}
        score = (
            min(25, int(row["strong_count"]) / total * 25)
            + min(20, int(row["primary_count"]) / total * 20)
            + {"critical": 25, "high": 18, "medium": 10, "low": 3}[max_severity]
            + impact
            + min(5, len(scenarios))
            + min(5, feasibility_weight(tag))
        )
        rows.append(
            {
                "rank": 0,
                "tag": tag,
                "affected_samples": row["affected_samples"],
                "strong_count": row["strong_count"],
                "primary_count": row["primary_count"],
                "main_error_type": error_counts.most_common(1)[0][0] if error_counts else "Unknown",
                "severity": max_severity,
                "fix_priority_score": round(max(0, min(100, score)), 2),
                "recommended_fix_category": row["recommended_fix_category"],
                "recommended_fix": row["recommended_fix"],
                "model_change_required": row["model_change_required"],
                "day26_priority": "yes" if score >= 35 and row["recommended_fix_category"] != "no_action_yet" else "no",
            }
        )
    rows.sort(key=lambda row: (-float(row["fix_priority_score"]), -int(row["strong_count"]), -int(row["primary_count"]), str(row["tag"])))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def folder_bias_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for folder, stats in context["folder_stats"].items():
        if stats["total_samples"] < 2:
            continue
        rows.append({"folder": folder, **stats, "source_folder_bias_strength": folder_bias_strength(stats)})
    rows.sort(key=lambda row: (-float(row["lift"]), -int(row["error_samples"]), row["folder"]))
    return rows


def format_bias_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fmt, stats in context["format_stats"].items():
        rows.append({"format": fmt, **stats, "format_bias_strength": format_bias_strength(stats)})
    rows.sort(key=lambda row: (-float(row["lift"]), -int(row["error_samples"]), row["format"]))
    return rows


def calibrated_day26_recommendation(ranking: list[dict[str, Any]]) -> str:
    non_model = [row for row in ranking if not row["model_change_required"] and row["day26_priority"] == "yes"]
    if not non_model:
        return "Keep Day26 focused on evidence collection; no calibrated non-model fix outranks the rest."
    top = non_model[0]
    if top["recommended_fix_category"] in {"decision_policy_patch", "uncertainty_policy_fix"}:
        return f"Proceed with Decision Policy Patch v1 focused on {top['tag']} and calibrated user-facing explanations."
    return f"Prioritize {top['tag']} via {top['recommended_fix_category']} before model work."


def build_calibrated_analysis(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    project_root = Path(project_root)
    detected = detect_input_files(project_root)
    if not detected["day24_files"]:
        raise Day25InputError(
            "Day25.1 needs Day24 evidence, but no Day24 report/review files were found under reports/data/outputs/artifacts/backend/frontend."
        )
    records_file = choose_records_file(detected, project_root)
    records = load_records(records_file)
    if not records:
        raise Day25InputError(
            "No benchmark or batch result records were found. Expected a JSON/CSV result file with sample-level labels."
        )
    reviews = load_review_map(detected)
    samples, context = analyze_records_calibrated(records, records_file or project_root, reviews)
    error_samples = [sample for sample in samples if sample["error_type"] in {"FP", "FN", "Uncertain", "Unknown"}]
    summary = calibrated_root_cause_summary(error_samples)
    ranking = calibrated_priority_ranking(error_samples, summary)
    return {
        "status": "ok",
        "version": "day25_1_calibrated",
        "generated_at": now_iso(),
        "input_files_detected": detected,
        "records_file": str(records_file) if records_file else None,
        "total_records_loaded": len(records),
        "total_error_samples": len(error_samples),
        "taxonomy_definition": ERROR_TAXONOMY,
        "samples": error_samples,
        "taxonomy_summary": summary,
        "root_cause_distribution": summary,
        "fix_priority_ranking": ranking,
        "representative_samples": representative_samples(error_samples),
        "folder_bias_analysis": folder_bias_rows(context),
        "format_bias_analysis": format_bias_rows(context),
        "calibration_context": {
            "global_error_rate": context["global_error_rate"],
            "format_flip_base_count": len(context["format_flip_bases"]),
            "resolution_flip_base_count": len(context["resolution_flip_bases"]),
        },
        "model_change_required_count": sum(1 for row in ranking if row["model_change_required"]),
        "day26_recommendation": calibrated_day26_recommendation(ranking),
    }


def analyze_records(records: list[dict[str, Any]], source_file: Path, reviews: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    reviews = reviews or {}
    normalized = []
    for index, record in enumerate(records):
        sample_id = stable_sample_id(record, index, source_file)
        normalized.append(normalize_record(record, index, source_file, reviews.get(sample_id)))
    groups = group_context(normalized)
    analyzed = []
    for item in normalized:
        tags = tag_root_causes(item, groups)
        primary = choose_primary_root_cause(tags)
        severity = severity_for(item)
        analyzed.append(
            {
                "sample_id": item["sample_id"],
                "image_path": item["image_path"],
                "expected_label": item["expected_label"],
                "predicted_label": item["predicted_label"],
                "final_label": item["final_label"],
                "error_type": item["error_type"],
                "confidence": item["confidence"],
                "risk_level": item["risk_level"],
                "scenario": item["scenario"],
                "source_folder": item["source_folder"],
                "format": item["format"],
                "resolution": item["resolution"],
                "root_cause_tags": tags,
                "primary_root_cause": primary,
                "severity": severity,
                "fix_priority_score": 0,
                "recommendation": recommendation_for(primary),
                "debug_evidence_summary": compact_text(item.get("debug_evidence")),
                "review_note_summary": compact_text((item.get("review") or {}).get("reviewer_note")),
            }
        )
    score_samples(analyzed)
    return analyzed


def root_cause_summary(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        tags = sample.get("root_cause_tags")
        if not isinstance(tags, list) or not tags:
            tags = [sample.get("primary_root_cause") or "unknown"]
        for tag in tags:
            grouped[str(tag or "unknown")].append(sample)
    total = max(1, len(samples))
    rows = []
    for root_cause, values in grouped.items():
        severity = max((sample["severity"] for sample in values), key=lambda value: SEVERITY_RANK[value])
        scenarios = Counter(str(sample.get("scenario") or "unknown") for sample in values)
        error_types = Counter(str(sample.get("error_type") or "Unknown") for sample in values)
        category = RECOMMENDATION_BY_TAG.get(root_cause, "no_action_yet")
        rows.append(
            {
                "root_cause": root_cause,
                "description": ERROR_TAXONOMY[root_cause],
                "sample_count": len(values),
                "percentage": round(len(values) / total * 100, 2),
                "main_scenarios": ", ".join(name for name, _ in scenarios.most_common(3)),
                "error_types": ", ".join(f"{name}:{count}" for name, count in error_types.most_common()),
                "risk_level": severity,
                "recommended_fix_category": category,
                "recommended_fix": FIX_DESCRIPTION[category],
                "model_change_needed": category == "model_training_needed",
                "day26_priority": "yes" if category != "no_action_yet" and severity in {"critical", "high", "medium"} else "no",
                "representative_samples": [sample["sample_id"] for sample in sorted(values, key=lambda sample: sample["fix_priority_score"], reverse=True)[:3]],
            }
        )
    rows.sort(key=lambda row: (-int(row["sample_count"]), -SEVERITY_RANK[str(row["risk_level"])], str(row["root_cause"])))
    return rows


def fix_priority_ranking(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        tags = sample.get("root_cause_tags")
        if not isinstance(tags, list) or not tags:
            tags = [sample.get("primary_root_cause") or "unknown"]
        for tag in tags:
            grouped[str(tag or "unknown")].append(sample)
    total = max(1, len(samples))
    rows = []
    for root_cause, values in grouped.items():
        max_severity = max((sample["severity"] for sample in values), key=lambda value: SEVERITY_RANK[value])
        category = RECOMMENDATION_BY_TAG.get(root_cause, "no_action_yet")
        scenarios = {str(sample.get("scenario") or "unknown") for sample in values}
        error_types = Counter(str(sample.get("error_type") or "Unknown") for sample in values)
        score = (
            min(30, len(values) / total * 30)
            + SEVERITY_WEIGHT[max_severity]
            + max(product_impact_weight(error_type) for error_type in error_types)
            + min(10, len(scenarios) * 2)
            + feasibility_weight(root_cause)
        )
        rows.append(
            {
                "rank": 0,
                "root_cause": root_cause,
                "affected_samples": len(values),
                "percentage": round(len(values) / total * 100, 2),
                "main_error_type": error_types.most_common(1)[0][0],
                "severity": max_severity,
                "fix_priority_score": round(max(0, min(100, score)), 2),
                "recommended_fix_category": category,
                "recommended_fix": FIX_DESCRIPTION[category],
                "model_change_needed": category == "model_training_needed",
                "day26_priority": "yes" if category != "no_action_yet" and round(score, 2) >= 40 else "no",
            }
        )
    rows.sort(key=lambda row: (-float(row["fix_priority_score"]), -int(row["affected_samples"]), str(row["root_cause"])))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def representative_samples(samples: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": sample["sample_id"],
            "image_path": sample["image_path"],
            "error_type": sample["error_type"],
            "primary_root_cause": sample["primary_root_cause"],
            "severity": sample["severity"],
            "fix_priority_score": sample["fix_priority_score"],
            "scenario": sample["scenario"],
            "format": sample["format"],
            "confidence": sample["confidence"],
        }
        for sample in sorted(samples, key=lambda sample: (-float(sample["fix_priority_score"]), sample["sample_id"]))[:limit]
    ]


def build_analysis(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    project_root = Path(project_root)
    detected = detect_input_files(project_root)
    if not detected["day24_files"]:
        raise Day25InputError(
            "Day25 needs Day24 evidence, but no Day24 report/review files were found under reports/data/outputs/artifacts/backend/frontend."
        )
    records_file = choose_records_file(detected, project_root)
    records = load_records(records_file)
    if not records:
        raise Day25InputError(
            "No benchmark or batch result records were found. Expected a JSON/CSV result file with sample-level labels."
        )
    reviews = load_review_map(detected)
    samples = analyze_records(records, records_file or project_root, reviews)
    error_samples = [sample for sample in samples if sample["error_type"] in {"FP", "FN", "Uncertain", "Unknown"}]
    summary = root_cause_summary(error_samples)
    ranking = fix_priority_ranking(error_samples)
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "input_files_detected": detected,
        "records_file": str(records_file) if records_file else None,
        "total_records_loaded": len(records),
        "total_error_samples": len(error_samples),
        "taxonomy_definition": ERROR_TAXONOMY,
        "samples": error_samples,
        "taxonomy_summary": summary,
        "root_cause_distribution": summary,
        "fix_priority_ranking": ranking,
        "representative_samples": representative_samples(error_samples),
        "model_change_required_count": sum(1 for row in ranking if row["model_change_needed"]),
        "day26_recommendation": day26_recommendation(ranking),
    }


def day26_recommendation(ranking: list[dict[str, Any]]) -> str:
    non_model = [row for row in ranking if not row["model_change_needed"] and row["day26_priority"] == "yes"]
    if non_model:
        top = non_model[0]
        return f"Prioritize {top['root_cause']} via {top['recommended_fix_category']} before any model work."
    if ranking:
        top = ranking[0]
        return f"Prioritize evidence collection for {top['root_cause']} and keep model changes deferred unless later benchmarks confirm it."
    return "No actionable Day26 item found because no error samples were available."


def api_payload(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    analysis = build_analysis(project_root)
    return {
        "status": "ok",
        "generated_at": analysis["generated_at"],
        "taxonomy_summary": analysis["taxonomy_summary"],
        "root_cause_distribution": analysis["root_cause_distribution"],
        "fix_priority_ranking": analysis["fix_priority_ranking"],
        "representative_samples": analysis["representative_samples"],
        "model_change_required_count": analysis["model_change_required_count"],
        "day26_recommendation": analysis["day26_recommendation"],
    }


def calibrated_api_payload(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    analysis = build_calibrated_analysis(project_root)
    return {
        "status": "ok",
        "version": analysis["version"],
        "generated_at": analysis["generated_at"],
        "taxonomy_summary": analysis["taxonomy_summary"],
        "root_cause_distribution": analysis["root_cause_distribution"],
        "fix_priority_ranking": analysis["fix_priority_ranking"],
        "representative_samples": analysis["representative_samples"],
        "folder_bias_analysis": analysis["folder_bias_analysis"][:50],
        "format_bias_analysis": analysis["format_bias_analysis"],
        "model_change_required_count": analysis["model_change_required_count"],
        "day26_recommendation": analysis["day26_recommendation"],
    }
