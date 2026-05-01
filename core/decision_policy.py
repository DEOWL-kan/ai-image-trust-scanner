from __future__ import annotations

from pathlib import Path
from typing import Any


BASELINE_THRESHOLD = 0.15
FINAL_REAL_THRESHOLD = 0.12
FINAL_AI_THRESHOLD = 0.18

DEFAULT_THRESHOLD = BASELINE_THRESHOLD
DEFAULT_UNCERTAINTY_MARGIN = round(BASELINE_THRESHOLD - FINAL_REAL_THRESHOLD, 6)


def safe_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_decision_policy(config: dict[str, Any] | None = None) -> dict[str, float]:
    if not config:
        return {
            "threshold": BASELINE_THRESHOLD,
            "baseline_threshold": BASELINE_THRESHOLD,
            "final_real_threshold": FINAL_REAL_THRESHOLD,
            "final_ai_threshold": FINAL_AI_THRESHOLD,
            "uncertainty_margin": DEFAULT_UNCERTAINTY_MARGIN,
        }

    policy = config.get("decision_policy", {})
    threshold = safe_float(policy.get("baseline_threshold"), BASELINE_THRESHOLD)
    final_real_threshold = safe_float(policy.get("final_real_threshold"), FINAL_REAL_THRESHOLD)
    final_ai_threshold = safe_float(policy.get("final_ai_threshold"), FINAL_AI_THRESHOLD)
    margin = safe_float(
        policy.get("uncertainty_margin"),
        round(threshold - final_real_threshold, 6),
    )
    return {
        "threshold": threshold,
        "baseline_threshold": threshold,
        "final_real_threshold": final_real_threshold,
        "final_ai_threshold": final_ai_threshold,
        "uncertainty_margin": margin,
    }


def binary_label_at_threshold(raw_score: float, threshold: float) -> str:
    return "ai" if raw_score >= threshold else "real"


def _final_label_for_score(score: float, final_real_threshold: float, final_ai_threshold: float) -> str:
    if score >= final_ai_threshold:
        return "ai"
    if score <= final_real_threshold:
        return "real"
    return "uncertain"


def get_final_label(score: float) -> str:
    return _final_label_for_score(score, FINAL_REAL_THRESHOLD, FINAL_AI_THRESHOLD)


def decide_final_label(
    raw_score: float,
    threshold: float = BASELINE_THRESHOLD,
    uncertainty_margin: float = DEFAULT_UNCERTAINTY_MARGIN,
    final_real_threshold: float = FINAL_REAL_THRESHOLD,
    final_ai_threshold: float = FINAL_AI_THRESHOLD,
) -> dict[str, Any]:
    confidence_distance = abs(raw_score - threshold)
    binary_label = binary_label_at_threshold(raw_score, threshold)
    final_label = _final_label_for_score(raw_score, final_real_threshold, final_ai_threshold)

    if final_label == "ai":
        decision_status = "decided"
        decision_reason = "score_at_or_above_final_ai_threshold"
    elif final_label == "real":
        decision_status = "decided"
        decision_reason = "score_at_or_below_final_real_threshold"
    else:
        decision_status = "uncertain"
        decision_reason = "score_inside_uncertain_band"

    return {
        "raw_score": round(float(raw_score), 6),
        "threshold": round(float(threshold), 6),
        "baseline_threshold": round(float(threshold), 6),
        "uncertainty_margin": round(float(uncertainty_margin), 6),
        "final_real_threshold": round(float(final_real_threshold), 6),
        "final_ai_threshold": round(float(final_ai_threshold), 6),
        "binary_label_at_threshold": binary_label,
        "final_label": final_label,
        "decision_status": decision_status,
        "confidence_distance": round(float(confidence_distance), 6),
        "decision_reason": decision_reason,
    }


def display_path(path: str | Path, project_root: Path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path)
