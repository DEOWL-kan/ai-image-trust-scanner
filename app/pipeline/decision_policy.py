from __future__ import annotations

from pathlib import Path
from statistics import median, pstdev
from typing import Any


BASELINE_THRESHOLD = 0.15
FINAL_REAL_THRESHOLD = 0.12
FINAL_AI_THRESHOLD = 0.18

DEFAULT_THRESHOLD = BASELINE_THRESHOLD
DEFAULT_UNCERTAINTY_MARGIN = round(BASELINE_THRESHOLD - FINAL_REAL_THRESHOLD, 6)

UNCERTAIN_V2_DEFAULTS = {
    "baseline_threshold": BASELINE_THRESHOLD,
    "real_safe_threshold": FINAL_REAL_THRESHOLD,
    "ai_safe_threshold": FINAL_AI_THRESHOLD,
    "score_std_limit": 0.035,
    "score_range_limit": 0.06,
}

UNCERTAIN_V21_DEFAULTS = {
    "baseline_threshold": BASELINE_THRESHOLD,
    "ai_safe_threshold": FINAL_AI_THRESHOLD,
    "real_original_safe_threshold": 0.145,
    "real_min_safe_threshold": 0.13,
    "ai_original_guard_threshold": 0.155,
    "score_std_limit": 0.035,
    "score_range_limit": 0.06,
    "resize_delta_limit": 0.055,
}


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


def load_uncertain_v2_policy(config: dict[str, Any] | None = None) -> dict[str, float]:
    """Load Day16 uncertain decision v2 thresholds from config or defaults."""
    policy = (config or {}).get("uncertain_decision_v2", {})
    return {
        "baseline_threshold": safe_float(
            policy.get("baseline_threshold"),
            UNCERTAIN_V2_DEFAULTS["baseline_threshold"],
        ),
        "real_safe_threshold": safe_float(
            policy.get("real_safe_threshold"),
            UNCERTAIN_V2_DEFAULTS["real_safe_threshold"],
        ),
        "ai_safe_threshold": safe_float(
            policy.get("ai_safe_threshold"),
            UNCERTAIN_V2_DEFAULTS["ai_safe_threshold"],
        ),
        "score_std_limit": safe_float(
            policy.get("score_std_limit"),
            UNCERTAIN_V2_DEFAULTS["score_std_limit"],
        ),
        "score_range_limit": safe_float(
            policy.get("score_range_limit"),
            UNCERTAIN_V2_DEFAULTS["score_range_limit"],
        ),
    }


def load_uncertain_v21_policy(config: dict[str, Any] | None = None) -> dict[str, float]:
    """Load Day16.1 uncertain decision v2.1 thresholds from config or defaults."""
    policy = (config or {}).get("uncertain_decision_v21", {})
    return {
        key: safe_float(policy.get(key), default)
        for key, default in UNCERTAIN_V21_DEFAULTS.items()
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


def make_uncertain_decision_v2(
    scores: list[float],
    raw_labels: list[str],
    baseline_threshold: float = BASELINE_THRESHOLD,
    real_safe_threshold: float = FINAL_REAL_THRESHOLD,
    ai_safe_threshold: float = FINAL_AI_THRESHOLD,
    score_std_limit: float = UNCERTAIN_V2_DEFAULTS["score_std_limit"],
    score_range_limit: float = UNCERTAIN_V2_DEFAULTS["score_range_limit"],
) -> dict[str, Any]:
    """Aggregate multi-resolution scores into a Day16 final label.

    The baseline threshold remains the raw binary reference. This layer only
    decides whether the multi-resolution evidence is stable enough for a
    definite final label.
    """
    usable_scores = [float(score) for score in scores]
    usable_labels = [label for label in raw_labels if label in {"ai", "real"}]
    if not usable_scores or not usable_labels:
        return {
            "mean_score": "",
            "min_score": "",
            "max_score": "",
            "score_std": "",
            "score_range": "",
            "raw_label_votes": {"ai": 0, "real": 0},
            "resolution_flip_count": 0,
            "consistency_status": "no_valid_scores",
            "final_label": "uncertain",
            "decision_reason": "no_valid_scores",
            "baseline_threshold": round(float(baseline_threshold), 6),
            "real_safe_threshold": round(float(real_safe_threshold), 6),
            "ai_safe_threshold": round(float(ai_safe_threshold), 6),
            "score_std_limit": round(float(score_std_limit), 6),
            "score_range_limit": round(float(score_range_limit), 6),
        }

    mean_score = sum(usable_scores) / len(usable_scores)
    min_score = min(usable_scores)
    max_score = max(usable_scores)
    score_std = pstdev(usable_scores) if len(usable_scores) > 1 else 0.0
    score_range = max_score - min_score
    votes = {
        "ai": sum(1 for label in usable_labels if label == "ai"),
        "real": sum(1 for label in usable_labels if label == "real"),
    }
    resolution_flip_count = sum(
        1
        for previous, current in zip(usable_labels, usable_labels[1:])
        if previous != current
    )
    vote_total = votes["ai"] + votes["real"]
    max_votes = max(votes.values()) if vote_total else 0
    majority_label = "ai" if votes["ai"] >= votes["real"] else "real"
    has_obvious_majority = max_votes > (vote_total / 2)
    basically_stable = has_obvious_majority and (
        vote_total <= 3 or max_votes >= vote_total - 1
    )

    consistency_status = "stable"
    if resolution_flip_count:
        consistency_status = "label_flip"
    if score_std > score_std_limit or score_range > score_range_limit:
        consistency_status = "score_unstable"

    if resolution_flip_count and score_range > score_range_limit:
        final_label = "uncertain"
        decision_reason = "resolution_flip"
    elif score_std > score_std_limit:
        final_label = "uncertain"
        decision_reason = "unstable_score_std"
    elif score_range > score_range_limit:
        final_label = "uncertain"
        decision_reason = "unstable_score_range"
    elif not has_obvious_majority:
        final_label = "uncertain"
        decision_reason = "weak_vote_majority"
    elif real_safe_threshold < mean_score < ai_safe_threshold:
        final_label = "uncertain"
        decision_reason = "near_threshold_band"
    elif mean_score >= ai_safe_threshold and majority_label == "ai" and basically_stable:
        final_label = "ai"
        decision_reason = "stable_ai_high_confidence"
    elif mean_score <= real_safe_threshold and majority_label == "real" and basically_stable:
        final_label = "real"
        decision_reason = "stable_real_high_confidence"
    else:
        final_label = "uncertain"
        decision_reason = "weak_vote_majority"

    return {
        "mean_score": round(mean_score, 6),
        "min_score": round(min_score, 6),
        "max_score": round(max_score, 6),
        "score_std": round(score_std, 6),
        "score_range": round(score_range, 6),
        "raw_label_votes": votes,
        "resolution_flip_count": resolution_flip_count,
        "consistency_status": consistency_status,
        "final_label": final_label,
        "decision_reason": decision_reason,
        "baseline_threshold": round(float(baseline_threshold), 6),
        "real_safe_threshold": round(float(real_safe_threshold), 6),
        "ai_safe_threshold": round(float(ai_safe_threshold), 6),
        "score_std_limit": round(float(score_std_limit), 6),
        "score_range_limit": round(float(score_range_limit), 6),
    }


def make_uncertain_decision_v21(
    scores_by_variant: dict[str, float],
    raw_labels_by_variant: dict[str, str],
    baseline_threshold: float = BASELINE_THRESHOLD,
    ai_safe_threshold: float = FINAL_AI_THRESHOLD,
    real_original_safe_threshold: float = UNCERTAIN_V21_DEFAULTS["real_original_safe_threshold"],
    real_min_safe_threshold: float = UNCERTAIN_V21_DEFAULTS["real_min_safe_threshold"],
    ai_original_guard_threshold: float = UNCERTAIN_V21_DEFAULTS["ai_original_guard_threshold"],
    score_std_limit: float = UNCERTAIN_V21_DEFAULTS["score_std_limit"],
    score_range_limit: float = UNCERTAIN_V21_DEFAULTS["score_range_limit"],
    resize_delta_limit: float = UNCERTAIN_V21_DEFAULTS["resize_delta_limit"],
) -> dict[str, Any]:
    """Aggregate multi-resolution evidence with Day16.1 resize-bias calibration."""
    variant_order = ("original", "long_edge_1024", "long_edge_768", "long_edge_512")
    ordered_variants = [
        variant for variant in variant_order
        if variant in scores_by_variant and scores_by_variant.get(variant) is not None
    ]
    ordered_variants.extend(
        sorted(
            variant for variant in scores_by_variant
            if variant not in set(ordered_variants) and scores_by_variant.get(variant) is not None
        )
    )
    scores = [float(scores_by_variant[variant]) for variant in ordered_variants]
    labels = [
        str(raw_labels_by_variant.get(variant) or "")
        for variant in ordered_variants
        if raw_labels_by_variant.get(variant) in {"ai", "real"}
    ]

    if not scores:
        return {
            "original_score": "",
            "resize_mean_score": "",
            "resize_delta": "",
            "mean_score": "",
            "median_score": "",
            "min_score": "",
            "max_score": "",
            "score_std": "",
            "score_range": "",
            "ai_vote_count": 0,
            "real_vote_count": 0,
            "original_label": "",
            "resolution_flip_count": 0,
            "consistency_status": "no_valid_scores",
            "final_label": "uncertain",
            "decision_reason": "no_valid_scores_v21",
        }

    original_score = float(scores_by_variant.get("original", scores[0]))
    resize_scores = [
        float(scores_by_variant[variant])
        for variant in ordered_variants
        if variant != "original"
    ]
    resize_mean_score = (
        sum(resize_scores) / len(resize_scores)
        if resize_scores
        else original_score
    )
    resize_delta = resize_mean_score - original_score
    mean_score = sum(scores) / len(scores)
    median_score = median(scores)
    min_score = min(scores)
    max_score = max(scores)
    score_std = pstdev(scores) if len(scores) > 1 else 0.0
    score_range = max_score - min_score
    ai_vote_count = sum(1 for label in labels if label == "ai")
    real_vote_count = sum(1 for label in labels if label == "real")
    original_label = str(raw_labels_by_variant.get("original") or "")
    resolution_flip_count = sum(
        1
        for previous, current in zip(labels, labels[1:])
        if previous != current
    )

    consistency_status = "stable"
    if resolution_flip_count:
        consistency_status = "label_flip"
    if score_std > score_std_limit or score_range > score_range_limit:
        consistency_status = "score_unstable"

    real_resize_ceiling = ai_safe_threshold + (score_range_limit / 3.0)
    if (
        original_score <= real_original_safe_threshold
        and resize_delta >= resize_delta_limit
        and mean_score <= real_resize_ceiling
    ):
        final_label = "real"
        decision_reason = "stable_real_safe_v21"
    elif (
        mean_score >= ai_safe_threshold
        and ai_vote_count >= 3
        and original_score >= ai_original_guard_threshold
        and score_range <= score_range_limit
        and resize_delta <= resize_delta_limit
    ):
        final_label = "ai"
        decision_reason = "stable_ai_high_confidence_v21"
    elif (
        mean_score >= ai_safe_threshold
        and ai_vote_count >= 3
        and (
            original_score < ai_original_guard_threshold
            or resize_delta > resize_delta_limit
        )
    ):
        final_label = "uncertain"
        decision_reason = "stable_ai_but_resize_biased"
    elif (
        min_score <= real_min_safe_threshold
        and original_score <= baseline_threshold
        and real_vote_count >= 2
        and resize_delta >= resize_delta_limit
        and mean_score <= real_resize_ceiling
    ):
        final_label = "real"
        decision_reason = "stable_real_safe_v21"
    elif resolution_flip_count >= 1 and score_range > score_range_limit:
        final_label = "uncertain"
        decision_reason = "resolution_flip_v21"
    elif score_std > score_std_limit or score_range > score_range_limit:
        final_label = "uncertain"
        decision_reason = "unstable_score_v21"
    elif abs(ai_vote_count - real_vote_count) <= 1:
        final_label = "uncertain"
        decision_reason = "weak_vote_majority_v21"
    elif (
        0.12 <= original_score <= ai_safe_threshold
        and (
            resolution_flip_count >= 1
            or score_range > score_range_limit * 0.75
            or max(ai_vote_count, real_vote_count) < 3
        )
    ):
        final_label = "uncertain"
        decision_reason = "near_threshold_band_v21"
    else:
        final_label = "uncertain"
        decision_reason = "near_threshold_band_v21"

    return {
        "original_score": round(original_score, 6),
        "resize_mean_score": round(resize_mean_score, 6),
        "resize_delta": round(resize_delta, 6),
        "mean_score": round(mean_score, 6),
        "median_score": round(median_score, 6),
        "min_score": round(min_score, 6),
        "max_score": round(max_score, 6),
        "score_std": round(score_std, 6),
        "score_range": round(score_range, 6),
        "ai_vote_count": ai_vote_count,
        "real_vote_count": real_vote_count,
        "original_label": original_label,
        "resolution_flip_count": resolution_flip_count,
        "consistency_status": consistency_status,
        "final_label": final_label,
        "decision_reason": decision_reason,
        "baseline_threshold": round(float(baseline_threshold), 6),
        "ai_safe_threshold": round(float(ai_safe_threshold), 6),
        "real_original_safe_threshold": round(float(real_original_safe_threshold), 6),
        "real_min_safe_threshold": round(float(real_min_safe_threshold), 6),
        "ai_original_guard_threshold": round(float(ai_original_guard_threshold), 6),
        "score_std_limit": round(float(score_std_limit), 6),
        "score_range_limit": round(float(score_range_limit), 6),
        "resize_delta_limit": round(float(resize_delta_limit), 6),
    }


def display_path(path: str | Path, project_root: Path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path)
