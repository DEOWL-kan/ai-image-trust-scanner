from __future__ import annotations

import json
from typing import Any


AI_TOOL_KEYWORDS = [
    "OpenAI",
    "ChatGPT",
    "DALL-E",
    "DALL·E",
    "Midjourney",
    "Stable Diffusion",
    "ComfyUI",
    "Automatic1111",
    "Adobe Firefly",
    "NovelAI",
]

EDITOR_KEYWORDS = [
    "Photoshop",
    "Lightroom",
    "Canva",
    "GIMP",
]


def _clamp(score: float | int) -> int:
    return max(0, min(100, int(round(score))))


def _risk_level(score: int) -> str:
    if score <= 34:
        return "low"
    if score <= 64:
        return "medium"
    if score <= 84:
        return "high"
    return "very_high"


def _stringify(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _combined_text(result: dict[str, Any] | None) -> str:
    if not isinstance(result, dict):
        return ""
    return " ".join(
        [
            _stringify(result.get("signals", [])),
            _stringify(result.get("raw_metadata", {})),
            str(result.get("software") or ""),
            str(result.get("raw_output") or ""),
        ]
    )


def _has_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _collect_signals(*results: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        for signal in result.get("signals", []):
            if isinstance(signal, str) and signal:
                evidence.append(signal)
    return evidence


def _ai_generation_risk(metadata_result: dict[str, Any]) -> int:
    metadata_text = _combined_text(metadata_result)
    has_ai_keyword = _has_keyword(metadata_text, AI_TOOL_KEYWORDS)
    has_exif = bool(metadata_result.get("has_exif"))

    if has_ai_keyword:
        return 90
    if has_exif:
        return 15
    if metadata_result.get("checked") is False:
        return 25
    return 30


def _provenance_risk(metadata_result: dict[str, Any], c2pa_result: dict[str, Any]) -> int:
    score = 0

    if metadata_result.get("has_exif"):
        score += 10
    else:
        score += 35

    has_manifest = c2pa_result.get("has_manifest")
    valid_signature = c2pa_result.get("valid_signature")
    if has_manifest and valid_signature:
        score += 5
    elif has_manifest and valid_signature is False:
        score += 45
    elif has_manifest is False:
        score += 40
    else:
        score += 25

    return _clamp(score)


def _editing_risk(metadata_result: dict[str, Any]) -> int:
    metadata_text = _combined_text(metadata_result)
    if _has_keyword(metadata_text, EDITOR_KEYWORDS):
        return 50
    return 15


def _technical_quality_risk(forensic_result: dict[str, Any]) -> int:
    if not forensic_result.get("checked"):
        return 70

    signals_text = _combined_text(forensic_result).lower()
    if "very small relative to a large resolution" in signals_text:
        return 45

    return 20 if forensic_result.get("is_jpeg") else 15


def _conclusion(
    ai_generation_risk: int,
    provenance_risk: int,
    technical_quality_risk: int,
) -> str:
    if technical_quality_risk >= 70:
        return "Technical inspection failed; result is unreliable."
    if ai_generation_risk >= 85:
        return "Strong AI-generation metadata signal detected."
    if provenance_risk >= 65:
        return "No strong AI-generation evidence detected, but provenance is limited."
    if provenance_risk >= 45:
        return "The image has limited verifiable provenance. This does not prove AI generation."
    return "No strong AI-generation evidence detected based on available signals."


def fuse_scores(
    metadata_result: dict[str, Any],
    c2pa_result: dict[str, Any],
    forensic_result: dict[str, Any],
) -> dict[str, Any]:
    ai_generation_risk = _ai_generation_risk(metadata_result)
    provenance_risk = _provenance_risk(metadata_result, c2pa_result)
    editing_risk = _editing_risk(metadata_result)
    technical_quality_risk = _technical_quality_risk(forensic_result)

    overall_risk = _clamp(
        0.45 * ai_generation_risk
        + 0.25 * provenance_risk
        + 0.15 * editing_risk
        + 0.15 * technical_quality_risk
    )

    return {
        "risk": {
            "ai_generation_risk": ai_generation_risk,
            "provenance_risk": provenance_risk,
            "editing_risk": editing_risk,
            "technical_quality_risk": technical_quality_risk,
            "overall_risk": overall_risk,
            "risk_level": _risk_level(overall_risk),
        },
        "conclusion": _conclusion(
            ai_generation_risk,
            provenance_risk,
            technical_quality_risk,
        ),
        "evidence_summary": _collect_signals(metadata_result, c2pa_result, forensic_result),
    }
