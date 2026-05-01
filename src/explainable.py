from __future__ import annotations

from typing import Any


AI_TERMS = (
    "ai",
    "midjourney",
    "stable diffusion",
    "dall",
    "firefly",
    "comfyui",
    "automatic1111",
)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _add(score: float, delta: float) -> float:
    return max(0.0, min(100.0, score + delta))


def classify_features(features: dict[str, Any]) -> dict[str, Any]:
    """Convert explainable image features into a conservative risk judgment."""
    risk_score = 50.0
    reasons: list[str] = []

    has_exif = bool(features.get("has_exif"))
    camera_model = str(features.get("camera_model") or "").strip()
    software = str(features.get("software") or "").strip()
    software_lower = software.lower()

    if not has_exif:
        risk_score = _add(risk_score, 10)
        reasons.append("No EXIF metadata was found, which is common for generated or heavily processed images.")
    if camera_model:
        risk_score = _add(risk_score, -12)
        reasons.append(f"Camera model metadata is present: {camera_model}.")
    if software:
        if any(term in software_lower for term in AI_TERMS):
            risk_score = _add(risk_score, 18)
            reasons.append(f"Software metadata contains an AI-generation clue: {software}.")
        else:
            risk_score = _add(risk_score, 4)
            reasons.append(f"Software metadata shows the image was processed with: {software}.")

    sharpness = _as_float(features.get("sharpness_score"))
    if sharpness < 40:
        risk_score = _add(risk_score, 12)
        reasons.append("Sharpness score is low, suggesting unusually smooth local detail.")
    elif sharpness > 600:
        risk_score = _add(risk_score, -6)
        reasons.append("Sharpness score is high, indicating strong natural or compressed detail.")

    edge_density = _as_float(features.get("edge_density"))
    if edge_density < 0.035:
        risk_score = _add(risk_score, 10)
        reasons.append("Edge density is low, which can indicate over-smoothed generated imagery.")
    elif edge_density > 0.18:
        risk_score = _add(risk_score, -5)
        reasons.append("Edge density is high, showing many local transitions and details.")

    color_entropy = _as_float(features.get("color_entropy"))
    if color_entropy < 4.5:
        risk_score = _add(risk_score, 8)
        reasons.append("Color entropy is low, meaning the color distribution is comparatively simple.")
    elif color_entropy > 7.0:
        risk_score = _add(risk_score, -4)
        reasons.append("Color entropy is high, suggesting a broad natural-looking color distribution.")

    noise_score = _as_float(features.get("noise_score"))
    if noise_score < 3:
        risk_score = _add(risk_score, 10)
        reasons.append("Noise and local variance are very low, a pattern often seen in synthetic or denoised images.")
    elif noise_score > 25:
        risk_score = _add(risk_score, -5)
        reasons.append("Noise and local variance are visible, which supports a real-camera or compressed-photo signal.")

    jpeg_quality = features.get("jpeg_quality_estimate")
    artifact_score = _as_float(features.get("compression_artifact_score"))
    if jpeg_quality is not None and _as_float(jpeg_quality) >= 96:
        risk_score = _add(risk_score, 4)
        reasons.append("JPEG quality estimate is extremely high, so compression history provides little camera-origin evidence.")
    elif jpeg_quality is not None and _as_float(jpeg_quality) < 55:
        risk_score = _add(risk_score, -4)
        reasons.append("JPEG quality estimate is low enough to show clear recompression history.")
    elif jpeg_quality is None and artifact_score < 1:
        risk_score = _add(risk_score, 3)
        reasons.append("Compression fallback found very weak 8x8 block artifacts.")

    risk_score = round(risk_score, 2)
    if risk_score >= 65:
        prediction = "likely_ai"
    elif risk_score <= 35:
        prediction = "likely_real"
    else:
        prediction = "uncertain"

    distance = abs(risk_score - 50)
    if distance >= 30:
        confidence = "high"
    elif distance >= 15:
        confidence = "medium"
    else:
        confidence = "low"

    if not reasons:
        reasons.append("Available features are neutral, so the image remains uncertain.")

    return {
        "risk_score": risk_score,
        "prediction": prediction,
        "confidence": confidence,
        "reasons": reasons,
    }
