from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_THRESHOLD = 0.15
DEFAULT_UNCERTAINTY_MARGIN = 0.03


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
            "threshold": DEFAULT_THRESHOLD,
            "uncertainty_margin": DEFAULT_UNCERTAINTY_MARGIN,
        }

    policy = config.get("decision_policy", {})
    threshold = safe_float(policy.get("baseline_threshold"), DEFAULT_THRESHOLD)
    margin = safe_float(policy.get("uncertainty_margin"), DEFAULT_UNCERTAINTY_MARGIN)
    return {
        "threshold": threshold,
        "uncertainty_margin": margin,
    }


def binary_label_at_threshold(raw_score: float, threshold: float) -> str:
    return "ai" if raw_score >= threshold else "real"


def decide_final_label(
    raw_score: float,
    threshold: float = DEFAULT_THRESHOLD,
    uncertainty_margin: float = DEFAULT_UNCERTAINTY_MARGIN,
) -> dict[str, Any]:
    confidence_distance = abs(raw_score - threshold)
    binary_label = binary_label_at_threshold(raw_score, threshold)

    if raw_score >= threshold + uncertainty_margin:
        final_label = "ai"
        decision_status = "decided"
        decision_reason = "score_above_threshold_margin"
    elif raw_score <= threshold - uncertainty_margin:
        final_label = "real"
        decision_status = "decided"
        decision_reason = "score_below_threshold_margin"
    else:
        final_label = "uncertain"
        decision_status = "uncertain"
        decision_reason = "score_inside_uncertain_band"

    return {
        "raw_score": round(float(raw_score), 6),
        "threshold": round(float(threshold), 6),
        "uncertainty_margin": round(float(uncertainty_margin), 6),
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
