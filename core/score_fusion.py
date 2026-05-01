from __future__ import annotations

from typing import Any


AI_TOOL_KEYWORDS = [
    "openai",
    "chatgpt",
    "dall-e",
    "dalle",
    "midjourney",
    "stable diffusion",
    "comfyui",
    "automatic1111",
    "firefly",
    "novelai",
]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def risk_level(score: float) -> str:
    if score < 0.35:
        return "low"
    if score < 0.65:
        return "medium"
    if score < 0.85:
        return "high"
    return "very_high"


def _metadata_score(metadata_result: dict[str, Any]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0

    if not metadata_result.get("checked"):
        evidence.append("Metadata could not be checked; provenance evidence is limited.")
        return 0.04, evidence

    if not metadata_result.get("has_exif"):
        score += 0.05
        evidence.append("No EXIF found; this is only a weak provenance signal.")
    else:
        evidence.append("EXIF metadata exists.")

    software = str(metadata_result.get("software") or "").lower()
    if any(keyword in software for keyword in AI_TOOL_KEYWORDS):
        score += 0.35
        evidence.append("AI-related software keyword found in metadata.")

    return _clamp(score), evidence


def _forensic_score(forensic_result: dict[str, Any]) -> tuple[float, list[str]]:
    evidence: list[str] = []
    if not forensic_result.get("checked"):
        return 0.08, ["Forensic features could not be computed."]

    score = 0.0
    edge_density = forensic_result.get("edge_density")
    laplacian_variance = forensic_result.get("laplacian_variance")
    noise_estimate = forensic_result.get("noise_estimate")
    brightness_std = forensic_result.get("brightness_std")

    if isinstance(edge_density, (int, float)) and (edge_density < 0.005 or edge_density > 0.35):
        score += 0.12
        evidence.append("Edge density is outside the broad expected baseline range.")

    if isinstance(laplacian_variance, (int, float)) and laplacian_variance < 20:
        score += 0.10
        evidence.append("Laplacian variance is low, suggesting a very smooth image.")

    if isinstance(noise_estimate, (int, float)) and noise_estimate < 1.5:
        score += 0.08
        evidence.append("Noise estimate is very low for this baseline heuristic.")

    if isinstance(brightness_std, (int, float)) and brightness_std < 8:
        score += 0.06
        evidence.append("Brightness variation is low.")

    if not evidence:
        evidence.append("Basic forensic features did not trigger strong baseline warnings.")

    return _clamp(score), evidence


def _frequency_score(frequency_result: dict[str, Any]) -> tuple[float, list[str]]:
    if not frequency_result.get("checked"):
        return 0.06, ["Frequency features could not be computed."]

    score = frequency_result.get("frequency_score")
    if not isinstance(score, (int, float)):
        return 0.06, ["Frequency score is unavailable."]

    normalized = _clamp(float(score))
    return normalized, [
        "Frequency score is a weak heuristic based on high-frequency energy, not a final judgment."
    ]


def _model_score(model_result: dict[str, Any]) -> tuple[float, float, list[str]]:
    if model_result.get("model_status") == "placeholder":
        return 0.0, 0.0, [
            "Deep model detector is placeholder and is not used as trained evidence."
        ]

    probability = model_result.get("ai_probability")
    if model_result.get("model_status") == "active" and isinstance(probability, (int, float)):
        return _clamp(float(probability)), 0.30, [
            "Active model probability included in score fusion."
        ]

    return 0.0, 0.0, [
        "Deep model detector is not active and is not used as trained evidence."
    ]


def fuse_scores(
    metadata_result: dict[str, Any],
    forensic_result: dict[str, Any],
    frequency_result: dict[str, Any],
    model_result: dict[str, Any],
) -> dict[str, Any]:
    metadata_score, metadata_evidence = _metadata_score(metadata_result)
    forensic_score, forensic_evidence = _forensic_score(forensic_result)
    frequency_score, frequency_evidence = _frequency_score(frequency_result)
    model_score, model_weight, model_evidence = _model_score(model_result)

    weights = {
        "metadata": 0.15,
        "forensic": 0.35,
        "frequency": 0.30,
        "model": model_weight,
    }
    active_weight = sum(weights.values()) or 1.0

    final_score = (
        metadata_score * weights["metadata"]
        + forensic_score * weights["forensic"]
        + frequency_score * weights["frequency"]
        + model_score * weights["model"]
    ) / active_weight
    final_score = round(_clamp(final_score), 6)

    return {
        "final_score": final_score,
        "risk_level": risk_level(final_score),
        "component_scores": {
            "metadata_score": round(metadata_score, 6),
            "forensic_score": round(forensic_score, 6),
            "frequency_score": round(frequency_score, 6),
            "model_score": round(model_score, 6),
        },
        "component_weights": weights,
        "result_type": "baseline risk level",
        "evidence_summary": metadata_evidence
        + forensic_evidence
        + frequency_evidence
        + model_evidence,
        "limitation_note": (
            "AI Image Trust Scanner V0.1 is a baseline multi-evidence heuristic. "
            "It provides a heuristic evidence summary and is not a final authenticity judgment, "
            "not a legal forensic conclusion, "
            "and not a trained AI-generation detector."
        ),
    }
