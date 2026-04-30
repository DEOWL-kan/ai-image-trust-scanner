from __future__ import annotations

from typing import Any


WEIGHTS = {
    "metadata": 0.45,
    "c2pa": 0.25,
    "forensic": 0.30,
}


def _score(result: dict[str, Any] | None) -> int:
    if not isinstance(result, dict):
        return 0
    try:
        return int(result.get("risk_score", 0))
    except (TypeError, ValueError):
        return 0


def _risk_level(score: int) -> str:
    if score <= 34:
        return "low"
    if score <= 64:
        return "medium"
    if score <= 84:
        return "high"
    return "very_high"


def _conclusion(level: str) -> str:
    conclusions = {
        "low": "Low AI-generation risk based on available signals.",
        "medium": "Limited provenance or mixed signals. AI generation cannot be confirmed.",
        "high": "High AI-generation risk based on multiple suspicious signals.",
        "very_high": "Very high AI-generation risk. Strong AI-related evidence detected.",
    }
    return conclusions[level]


def _collect_signals(*results: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        for signal in result.get("signals", []):
            if isinstance(signal, str) and signal:
                evidence.append(signal)
    return evidence


def fuse_scores(
    metadata_result: dict[str, Any],
    c2pa_result: dict[str, Any],
    forensic_result: dict[str, Any],
) -> dict[str, Any]:
    risk_score = round(
        _score(metadata_result) * WEIGHTS["metadata"]
        + _score(c2pa_result) * WEIGHTS["c2pa"]
        + _score(forensic_result) * WEIGHTS["forensic"]
    )
    risk_score = max(0, min(100, int(risk_score)))
    level = _risk_level(risk_score)

    return {
        "risk_score": risk_score,
        "risk_level": level,
        "conclusion": _conclusion(level),
        "evidence_summary": _collect_signals(metadata_result, c2pa_result, forensic_result),
    }
