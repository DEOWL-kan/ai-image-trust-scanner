from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRODUCT_LABELS = {"likely_ai", "likely_real", "uncertain"}
RISK_LEVELS = {"high", "medium", "low"}

AI_RECOMMENDATION = (
    "建议谨慎使用该图片。若用于新闻、证据、交易或身份验证场景，应要求提供原图、拍摄来源或额外证明。"
)
REAL_RECOMMENDATION = (
    "当前结果更接近真实图片，但不应作为唯一真实性证明。高风险场景仍建议结合来源、EXIF 和人工审核。"
)
UNCERTAIN_RECOMMENDATION = (
    "当前图片处于不确定区间。建议上传原始分辨率图片、保留 EXIF 的原图，或结合人工复核和更多证据。"
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _get(raw_result: dict[str, Any], *keys: str) -> Any:
    """Read a field from flat Day16 rows or nested single-image reports."""
    nested_candidates = [
        raw_result,
        _as_dict(raw_result.get("final_result")),
        _as_dict(raw_result.get("fusion")),
        _as_dict(raw_result.get("risk")),
        _as_dict(raw_result.get("image_info")),
        _as_dict(raw_result.get("metadata_result")),
        _as_dict(raw_result.get("metadata")),
    ]
    for key in keys:
        for candidate in nested_candidates:
            if key in candidate:
                return candidate.get(key)
    return None


def _map_final_label(raw_result: dict[str, Any]) -> str:
    raw_label = (
        _get(raw_result, "final_label_v21")
        or _get(raw_result, "final_label")
        or _get(raw_result, "decision_status")
        or _get(raw_result, "binary_label_at_threshold")
        or _get(raw_result, "raw_label_at_0_15")
    )
    label = str(raw_label or "").strip().lower()
    if label in {"likely_ai", "ai", "artificial", "generated", "very_high", "high"}:
        return "likely_ai"
    if label in {"likely_real", "real", "authentic", "camera", "low"}:
        return "likely_real"
    if label in {"uncertain", "unknown", "undetermined", "review"}:
        return "uncertain"

    score = _safe_float(
        _get(raw_result, "original_score")
        or _get(raw_result, "final_score")
        or _get(raw_result, "raw_score")
        or _get(raw_result, "mean_score")
    )
    threshold = _safe_float(_get(raw_result, "threshold", "baseline_threshold")) or 0.15
    if score is None:
        return "uncertain"
    return "likely_ai" if score >= threshold else "likely_real"


def _raw_base_label(raw_result: dict[str, Any]) -> str | None:
    label = _get(raw_result, "raw_label_at_0_15", "binary_label_at_threshold")
    if label in (None, ""):
        return None
    return str(label)


def _format_info(raw_result: dict[str, Any], image_path: str | None) -> dict[str, Any]:
    path = image_path or _get(raw_result, "image_path")
    extension = _get(raw_result, "format", "extension")
    if not extension and path:
        extension = Path(str(path)).suffix.lower().lstrip(".")
    width = _get(raw_result, "width", "original_width")
    height = _get(raw_result, "height", "original_height")
    return {
        "format": str(extension or "").lower() or None,
        "image_path": str(path) if path else None,
        "width": _safe_int(width, 0) or None,
        "height": _safe_int(height, 0) or None,
    }


def _exif_info(raw_result: dict[str, Any]) -> dict[str, Any]:
    has_exif = _safe_bool(_get(raw_result, "has_exif"))
    return {
        "has_exif": has_exif,
        "software": _get(raw_result, "software"),
        "metadata_checked": _get(raw_result, "checked"),
    }


def _multi_resolution(raw_result: dict[str, Any]) -> dict[str, Any]:
    ai_votes = _safe_int(_get(raw_result, "ai_vote_count"))
    real_votes = _safe_int(_get(raw_result, "real_vote_count"))
    raw_votes = _get(raw_result, "raw_label_votes", "resize_raw_label_votes")
    if isinstance(raw_votes, str) and raw_votes:
        try:
            parsed = json.loads(raw_votes)
            if isinstance(parsed, dict):
                ai_votes = _safe_int(parsed.get("ai"), ai_votes)
                real_votes = _safe_int(parsed.get("real"), real_votes)
        except json.JSONDecodeError:
            pass

    return {
        "available": any(
            _get(raw_result, key) not in (None, "")
            for key in (
                "mean_score",
                "score_range",
                "score_std",
                "resolution_flip_count",
                "resize_delta",
            )
        ),
        "original_score": _safe_float(_get(raw_result, "original_score", "raw_score_at_0_15")),
        "resize_mean_score": _safe_float(_get(raw_result, "resize_mean_score")),
        "resize_delta": _safe_float(_get(raw_result, "resize_delta")),
        "mean_score": _safe_float(_get(raw_result, "mean_score")),
        "median_score": _safe_float(_get(raw_result, "median_score")),
        "min_score": _safe_float(_get(raw_result, "min_score")),
        "max_score": _safe_float(_get(raw_result, "max_score")),
        "score_std": _safe_float(_get(raw_result, "score_std")),
        "score_range": _safe_float(_get(raw_result, "score_range")),
        "resolution_flip_count": _safe_int(_get(raw_result, "resolution_flip_count")),
        "ai_vote_count": ai_votes,
        "real_vote_count": real_votes,
        "consistency_status": _get(raw_result, "consistency_status"),
    }


def _uncertainty_flags(raw_result: dict[str, Any], multi_resolution: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    reason = str(_get(raw_result, "decision_reason_v21", "decision_reason") or "").lower()
    if reason:
        flags.append(reason)
    if multi_resolution.get("resolution_flip_count", 0) > 0:
        flags.append("resolution_flip")
    if (multi_resolution.get("score_range") or 0.0) > 0.06:
        flags.append("large_score_range")
    if (multi_resolution.get("score_std") or 0.0) > 0.035:
        flags.append("large_score_std")
    if "weak_vote" in reason:
        flags.append("weak_vote_majority")
    if "near_threshold" in reason:
        flags.append("near_threshold_band")
    if "resize_biased" in reason or (multi_resolution.get("resize_delta") or 0.0) > 0.055:
        flags.append("resize_bias")
    return sorted(set(flags))


def _risk_and_stability_factors(
    raw_result: dict[str, Any],
    final_label: str,
    format_info: dict[str, Any],
    exif_info: dict[str, Any],
    multi_resolution: dict[str, Any],
    uncertainty_flags: list[str],
) -> tuple[list[str], list[str]]:
    risk_factors: list[str] = []
    stability_factors: list[str] = []
    image_format = str(format_info.get("format") or "").lower()

    if image_format in {"jpg", "jpeg"}:
        risk_factors.append("jpeg_container_or_compression")
    if exif_info.get("has_exif") is False:
        risk_factors.append("missing_exif")
    if multi_resolution.get("resolution_flip_count", 0) > 0:
        risk_factors.append("resolution_instability")
    if "resize_bias" in uncertainty_flags:
        risk_factors.append("resize_bias")
    if final_label == "uncertain":
        risk_factors.append("uncertain_decision")
    if final_label == "likely_ai":
        risk_factors.append("ai_like_score_pattern")

    if multi_resolution.get("available") and multi_resolution.get("resolution_flip_count", 0) == 0:
        stability_factors.append("multi_resolution_label_consistency")
    if (multi_resolution.get("score_range") or 0.0) <= 0.06 and multi_resolution.get("available"):
        stability_factors.append("low_multi_resolution_score_range")
    if final_label == "likely_real" and _raw_base_label(raw_result) in {"real", "likely_real"}:
        stability_factors.append("baseline_label_supports_real")
    if final_label == "likely_ai" and _raw_base_label(raw_result) in {"ai", "likely_ai"}:
        stability_factors.append("baseline_label_supports_ai")

    return sorted(set(risk_factors)), sorted(set(stability_factors))


def _score_margin(raw_result: dict[str, Any]) -> float | None:
    score = _safe_float(
        _get(raw_result, "original_score")
        or _get(raw_result, "final_score")
        or _get(raw_result, "raw_score")
        or _get(raw_result, "mean_score")
    )
    threshold = _safe_float(_get(raw_result, "threshold", "baseline_threshold")) or 0.15
    return None if score is None else round(abs(score - threshold), 6)


def _risk_level(final_label: str, risk_factors: list[str], stability_factors: list[str]) -> str:
    unstable = any(
        item in risk_factors
        for item in ("resolution_instability", "resize_bias", "uncertain_decision")
    )
    format_risk_count = sum(
        1 for item in risk_factors if item in {"jpeg_container_or_compression", "missing_exif"}
    )

    if final_label == "uncertain":
        return "medium"
    if final_label == "likely_ai":
        return "medium" if unstable else "high"
    if final_label == "likely_real":
        if unstable or format_risk_count >= 2:
            return "medium"
        return "low"
    return "medium"


def _confidence(
    final_label: str,
    risk_factors: list[str],
    stability_factors: list[str],
    score_margin: float | None,
) -> float:
    stable_count = len(stability_factors)
    instability_count = sum(
        1 for item in risk_factors if item in {"resolution_instability", "resize_bias", "uncertain_decision"}
    )
    format_risk_count = sum(
        1 for item in risk_factors if item in {"jpeg_container_or_compression", "missing_exif"}
    )
    margin_bonus = min(score_margin or 0.0, 0.08)

    if final_label == "uncertain":
        value = 0.52 - (0.03 * instability_count) + min(margin_bonus, 0.03)
        return round(_clamp(value, 0.45, 0.60), 2)
    if final_label == "likely_ai":
        value = 0.76 + (0.025 * stable_count) + margin_bonus - (0.055 * instability_count)
        return round(_clamp(value, 0.62 if instability_count else 0.76, 0.90), 2)
    if final_label == "likely_real":
        value = 0.73 + (0.025 * stable_count) + margin_bonus - (0.045 * format_risk_count) - (0.06 * instability_count)
        high = 0.72 if format_risk_count or instability_count else 0.86
        low = 0.60 if format_risk_count or instability_count else 0.72
        return round(_clamp(value, low, high), 2)
    return 0.5


def _decision_reason(
    final_label: str,
    risk_factors: list[str],
    stability_factors: list[str],
    uncertainty_flags: list[str],
) -> list[str]:
    reasons: list[str] = []
    if final_label == "likely_ai":
        reasons.append("图像检测结果更接近 AI 生成或强生成式处理的模式。")
    elif final_label == "likely_real":
        reasons.append("图像检测结果更接近真实图片的规则基线表现。")
    else:
        reasons.append("图像处于不确定区间，当前证据不足以给出稳定的 AI / Real 判断。")

    if "multi_resolution_label_consistency" in stability_factors:
        reasons.append("多分辨率检测结果保持一致。")
    if "resolution_instability" in risk_factors:
        reasons.append("不同分辨率下的检测结果存在翻转或不稳定。")
    if "jpeg_container_or_compression" in risk_factors:
        reasons.append("图片为 JPEG/JPG 容器，压缩痕迹可能影响规则判断。")
    if "missing_exif" in risk_factors:
        reasons.append("元数据或 EXIF 证据缺失，因此结果需要谨慎理解。")
    if any(flag for flag in uncertainty_flags if "near_threshold" in flag):
        reasons.append("核心分数接近决策边界，系统未将其视为强证据。")
    return reasons


def _recommendation(final_label: str) -> str:
    if final_label == "likely_ai":
        return AI_RECOMMENDATION
    if final_label == "likely_real":
        return REAL_RECOMMENDATION
    return UNCERTAIN_RECOMMENDATION


def _user_summary(final_label: str) -> str:
    if final_label == "likely_ai":
        return "这张图片更可能是 AI 生成或经过强生成式处理的图片。该结论来自规则检测和一致性信号，仍应作为辅助判断。"
    if final_label == "likely_real":
        return "这张图片当前更接近真实图片的检测表现。它不能单独证明图片真实，高风险场景仍需要来源和人工复核。"
    return "这张图片目前处于不确定区间。建议上传原始图片或结合更多来源证据后再判断。"


def _technical_explanation(
    final_label: str,
    risk_level: str,
    confidence: float,
    raw_result: dict[str, Any],
    multi_resolution: dict[str, Any],
    risk_factors: list[str],
    stability_factors: list[str],
    uncertainty_flags: list[str],
) -> str:
    base_label = _raw_base_label(raw_result) or "unknown"
    uncertain_label = _get(raw_result, "final_label_v21", "final_label") or "unknown"
    score = (
        _safe_float(_get(raw_result, "original_score"))
        or _safe_float(_get(raw_result, "final_score"))
        or _safe_float(_get(raw_result, "mean_score"))
    )
    multi_text = (
        "已使用 multi-resolution consistency / uncertain decision layer 信息"
        if multi_resolution.get("available")
        else "未发现可用的 multi-resolution consistency 字段"
    )
    format_text = ", ".join(risk_factors) if risk_factors else "无明显格式/元数据风险字段"
    stable_text = ", ".join(stability_factors) if stability_factors else "未发现明确稳定性字段"
    flag_text = ", ".join(uncertainty_flags) if uncertainty_flags else "无额外 uncertainty flag"
    return (
        f"Product layer mapped the raw label `{uncertain_label}` and baseline label `{base_label}` "
        f"to `{final_label}`. It used rule-based score fields, metadata/format fields, "
        f"and Day16.1 uncertain decision evidence when present; {multi_text}. "
        f"Observed score={score}, risk_level={risk_level}, decision_confidence={confidence} "
        f"(rule-based decision confidence, not model probability). "
        f"Risk factors: {format_text}. Stability factors: {stable_text}. "
        f"Uncertainty flags: {flag_text}."
    )


def build_product_output(
    raw_result: dict[str, Any],
    image_path: str | None = None,
    debug: bool = True,
) -> dict[str, Any]:
    """Wrap detector output in a stable product/API schema.

    `confidence` is a rule-based decision confidence derived from consistency
    and risk signals. It is not a trained model probability.
    """
    source = raw_result if isinstance(raw_result, dict) else {}
    final_label = _map_final_label(source)
    format_info = _format_info(source, image_path)
    exif_info = _exif_info(source)
    multi = _multi_resolution(source)
    uncertainty_flags = _uncertainty_flags(source, multi)
    risk_factors, stability_factors = _risk_and_stability_factors(
        source,
        final_label,
        format_info,
        exif_info,
        multi,
        uncertainty_flags,
    )
    margin = _score_margin(source)
    risk = _risk_level(final_label, risk_factors, stability_factors)
    confidence = _confidence(final_label, risk_factors, stability_factors, margin)

    debug_evidence: dict[str, Any] = {
        "raw_score": (
            _safe_float(_get(source, "original_score"))
            or _safe_float(_get(source, "final_score"))
            or _safe_float(_get(source, "raw_score"))
            or _safe_float(_get(source, "mean_score"))
        ),
        "base_label": _raw_base_label(source),
        "uncertain_label": _get(source, "final_label_v21", "final_label"),
        "threshold_used": _safe_float(_get(source, "threshold", "baseline_threshold")) or 0.15,
        "score_margin": margin,
        "uncertainty_flags": uncertainty_flags,
        "multi_resolution": multi,
        "format_info": format_info,
        "exif_info": exif_info,
        "risk_factors": risk_factors,
        "stability_factors": stability_factors,
    }
    if debug:
        debug_evidence["raw_result"] = source

    output = {
        "final_label": final_label,
        "risk_level": risk,
        "confidence": confidence,
        "decision_reason": _decision_reason(
            final_label,
            risk_factors,
            stability_factors,
            uncertainty_flags,
        ),
        "recommendation": _recommendation(final_label),
        "user_facing_summary": _user_summary(final_label),
        "technical_explanation": _technical_explanation(
            final_label,
            risk,
            confidence,
            source,
            multi,
            risk_factors,
            stability_factors,
            uncertainty_flags,
        ),
        "debug_evidence": debug_evidence,
    }

    if output["final_label"] not in PRODUCT_LABELS:
        output["final_label"] = "uncertain"
    if output["risk_level"] not in RISK_LEVELS:
        output["risk_level"] = "medium"
    output["confidence"] = round(_clamp(float(output["confidence"]), 0.0, 1.0), 2)
    return output
