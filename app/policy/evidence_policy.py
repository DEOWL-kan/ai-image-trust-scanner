from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "policy_config.yaml"
AI_TRACE_KEYWORDS = (
    "midjourney",
    "stable diffusion",
    "stability ai",
    "dall-e",
    "dalle",
    "openai",
    "gpt-image",
    "firefly",
    "comfyui",
    "automatic1111",
    "invokeai",
    "leonardo",
)
TRUSTED_CAMERA_KEYWORDS = ("canon", "nikon", "sony", "fujifilm", "leica", "iphone", "pixel", "samsung")
# Detectors that must never count as "supporting AI evidence" (P1-b Step2):
# smogy is the primary decision gate (not its own support); dima806 is
# diagnostic-only (Day35 real-as-AI FP 0.904); legacy is the hand-crafted
# baseline kept as auxiliary; capcheck is disabled (duplicate of dima806).
SECONDARY_VOTE_EXCLUDED_DETECTORS = ("smogy", "dima806", "legacy", "capcheck")
# Roles that never vote, even if a future detector is added under them.
NON_VOTING_ROLES = ("diagnostic", "baseline")
NON_VOTING_DETECTORS = ("dima806", "legacy", "capcheck")


def load_policy_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_POLICY_CONFIG_PATH)
    with source.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    config.setdefault("policy_version", "evidence_policy_v1")
    config.setdefault("thresholds", {})
    config.setdefault("rules", {})
    config.setdefault("detectors", {})
    return config


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(0.0, min(1.0, number)), 4)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str).lower()
    return str(value).lower()


def _contains_any(value: Any, keywords: tuple[str, ...]) -> bool:
    text = _text(value)
    return any(keyword in text for keyword in keywords)


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _recommendation(config: dict[str, Any], action: str) -> dict[str, str]:
    item = (config.get("review_recommendations") or {}).get(action) or {}
    return {
        "action": str(item.get("action") or action),
        "message": str(item.get("message") or ""),
    }


def _policy_profile(config: dict[str, Any], requested: Any = None) -> tuple[str, dict[str, Any]]:
    profiles = config.get("policy_profiles") if isinstance(config.get("policy_profiles"), dict) else {}
    name = str(requested or config.get("default_policy_profile") or "balanced").strip().lower()
    if name not in profiles:
        name = "balanced" if "balanced" in profiles else next(iter(profiles), "default")
    profile = profiles.get(name) if isinstance(profiles.get(name), dict) else {}
    thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), dict) else {}
    fallback_ai = _clamp01(thresholds.get("smogy_high_ai_score"), 0.85)
    fallback_gray = _clamp01(thresholds.get("smogy_medium_ai_score"), 0.65)
    return name, {
        "threshold_profile": str(profile.get("threshold_profile") or name),
        "real_threshold": _clamp01(profile.get("real_threshold"), _clamp01(thresholds.get("smogy_low_ai_score"), 0.35)),
        "gray_threshold": _clamp01(profile.get("gray_threshold"), fallback_gray),
        "ai_threshold": _clamp01(profile.get("ai_threshold"), fallback_ai),
        "ai_risk_level": str(profile.get("ai_risk_level") or "medium"),
        "ai_review_required": bool(profile.get("ai_review_required", True)),
        "review_band_risk_level": str(profile.get("review_band_risk_level") or "medium"),
        "primary_conflict_review": bool(profile.get("primary_conflict_review", False)),
    }


def _detector_id(raw: dict[str, Any]) -> str:
    return str(raw.get("detector_id") or raw.get("id") or raw.get("name") or "unknown").strip().lower()


def _normal_detector(raw: Any, config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {"error": {"type": "InvalidDetectorResult", "message": "Detector result is not an object."}}
    detector_id = _detector_id(raw)
    threshold = _clamp01(raw.get("threshold"), 0.5)
    ai_score = _clamp01(raw.get("ai_score", raw.get("score")), 0.0)
    error = raw.get("error") if isinstance(raw.get("error"), dict) else {}
    status = str(raw.get("status") or ("error" if error.get("message") else "ok")).lower()
    label = str(raw.get("predicted_label") or raw.get("label") or raw.get("raw_label") or "").lower()
    if not label:
        if status in {"error", "skipped", "disabled"}:
            label = status
        else:
            label = "ai" if ai_score >= threshold else "real"
    if status in {"disabled", "skipped"}:
        error = {}
    enabled = bool(raw.get("enabled", status != "disabled"))
    duplicate_of = raw.get("duplicate_of") or raw.get("duplicateOf")
    role = str(raw.get("role") or (config.get("detectors") or {}).get(detector_id, {}).get("role") or "diagnostic")
    return {
        "detector_id": detector_id,
        "label": label,
        "raw_label": raw.get("raw_label") or raw.get("predicted_label") or raw.get("label"),
        "ai_score": ai_score,
        "threshold": threshold,
        "role": role,
        "latency_ms": raw.get("latency_ms"),
        "error": error,
        "status": status,
        "enabled": enabled,
        "duplicate_of": duplicate_of,
        "detector_version": raw.get("detector_version") or raw.get("model_version") or raw.get("version"),
        "model_version": raw.get("model_version"),
        "raw": raw,
    }


def normalize_evidence_inputs(
    detector_results: list[dict[str, Any]] | None,
    metadata_result: dict[str, Any] | None = None,
    provenance_result: dict[str, Any] | None = None,
    forensic_result: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_policy_config()
    detectors = [_normal_detector(item, config) for item in (detector_results or [])]
    active = [
        item
        for item in detectors
        if item["enabled"] and not item.get("duplicate_of") and item["status"] == "ok"
    ]
    metadata = metadata_result if isinstance(metadata_result, dict) else {}
    provenance = provenance_result if isinstance(provenance_result, dict) else {}
    forensic = forensic_result if isinstance(forensic_result, dict) else {}
    context = context if isinstance(context, dict) else {}
    return {
        "detectors": detectors,
        "active_detectors": active,
        "metadata": metadata,
        "provenance": provenance,
        "forensic": forensic,
        "context": context,
        "metadata_has_ai_trace": _contains_any(
            {
                "software": metadata.get("software"),
                "creator_tool": metadata.get("creator_tool"),
                "generator": metadata.get("generator"),
                "xmp_creator_tool": metadata.get("xmp_creator_tool"),
                "c2pa_generator": metadata.get("c2pa_generator"),
            },
            AI_TRACE_KEYWORDS,
        ),
        "metadata_missing": _contains_any(metadata, ("missing_exif", "missing_xmp", "missing_metadata", "missing_c2pa")),
        "forensic_anomaly": bool(forensic.get("anomaly") or forensic.get("forensic_anomaly") or forensic.get("obvious_anomaly")),
    }


def _provenance_state(provenance: dict[str, Any]) -> dict[str, Any]:
    verified = provenance.get("verified") if isinstance(provenance.get("verified"), dict) else provenance
    diagnostics = provenance.get("diagnostics") if isinstance(provenance.get("diagnostics"), dict) else {}
    readable = bool(verified.get("c2pa_readable") or verified.get("verified"))
    valid = verified.get("c2pa_valid")
    valid = True if valid is None and readable and verified.get("openai_provenance_detected") else bool(valid)
    ai_declared = bool(
        verified.get("openai_provenance_detected")
        or verified.get("ai_generated")
        or verified.get("generated_by_ai")
        or _contains_any(verified.get("c2pa_generator"), AI_TRACE_KEYWORDS)
    )
    trusted_human = bool(
        readable
        and valid
        and not ai_declared
        and (
            verified.get("trusted_camera")
            or verified.get("human_verified")
            or _contains_any(verified.get("c2pa_issuer"), TRUSTED_CAMERA_KEYWORDS)
            or _contains_any(verified.get("c2pa_generator"), TRUSTED_CAMERA_KEYWORDS)
        )
    )
    missing = diagnostics.get("c2pa_probe_status") == "no_manifest" or not provenance
    return {
        "readable": readable,
        "valid": valid,
        "ai_declared": bool(readable and valid and ai_declared),
        "trusted_human": trusted_human,
        "missing": missing,
    }


def _detector_groups(evidence: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    active = evidence["active_detectors"]
    smogy = next((item for item in active if item["detector_id"] == "smogy"), None)
    ateeqq = next((item for item in active if item["detector_id"] == "ateeqq"), None)
    high = _clamp01(thresholds.get("smogy_high_ai_score"), 0.85)
    medium = _clamp01(thresholds.get("smogy_medium_ai_score"), 0.65)
    low = _clamp01(thresholds.get("smogy_low_ai_score"), 0.35)
    ateeqq_high = _clamp01(thresholds.get("ateeqq_high_ai_score"), 0.85)
    ai_like = [item for item in active if item["status"] == "ok" and (item["label"] == "ai" or item["ai_score"] >= item["threshold"])]
    real_like = [item for item in active if item["status"] == "ok" and (item["label"] == "real" or item["ai_score"] <= low)]
    voting_ai_like = [item for item in ai_like if item["detector_id"] not in NON_VOTING_DETECTORS and item["role"] not in NON_VOTING_ROLES]
    voting_real_like = [item for item in real_like if item["detector_id"] not in NON_VOTING_DETECTORS and item["role"] not in NON_VOTING_ROLES]
    errors = [
        item
        for item in evidence["detectors"]
        if item["enabled"]
        and not item.get("duplicate_of")
        and item["status"] == "error"
        and item.get("error", {}).get("message")
    ]
    primary_errors = [item for item in errors if item["detector_id"] == "smogy" or item["role"] in {"primary", "primary_candidate"}]
    auxiliary_errors = [item for item in errors if item not in primary_errors]
    conflicts = []
    for ai_item in voting_ai_like:
        for real_item in voting_real_like:
            if ai_item["detector_id"] != real_item["detector_id"] and abs(ai_item["ai_score"] - real_item["ai_score"]) >= _clamp01(thresholds.get("conflict_margin"), 0.35):
                conflicts.append((ai_item, real_item))
    return {
        "smogy": smogy,
        "ateeqq": ateeqq,
        "smogy_high": bool(smogy and smogy["ai_score"] >= high),
        "smogy_medium": bool(smogy and smogy["ai_score"] >= medium),
        "all_low": bool(active) and all(item["status"] in {"ok", "skipped"} and item["ai_score"] <= low for item in active if item["status"] == "ok"),
        "ateeqq_high": bool(ateeqq and ateeqq["ai_score"] >= ateeqq_high),
        "ai_like": ai_like,
        "real_like": real_like,
        "voting_ai_like": voting_ai_like,
        "voting_real_like": voting_real_like,
        "active_primary": smogy,
        "has_active_primary": bool(smogy and smogy["status"] == "ok" and smogy.get("ai_score") is not None),
        "errors": errors,
        "primary_errors": primary_errors,
        "auxiliary_errors": auxiliary_errors,
        "conflicts": conflicts,
    }


def build_evidence_cards(evidence: dict[str, Any], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or load_policy_config()
    cards: list[dict[str, Any]] = []
    for item in evidence["detectors"]:
        status = "neutral"
        severity = "info"
        if item["status"] == "error" or item.get("error", {}).get("message"):
            if item["detector_id"] == "smogy" or item["role"] in {"primary", "primary_candidate"}:
                status, severity = "error", "medium"
            else:
                status, severity = "conflict", "low"
        elif item.get("duplicate_of") or item["status"] in {"disabled", "skipped"}:
            status, severity = "neutral", "info"
        elif item["label"] == "ai" or item["ai_score"] >= item["threshold"]:
            status, severity = "supports_ai", "medium"
        elif item["label"] == "real":
            status, severity = "supports_real", "low"
        cards.append(
            {
                "id": f"detector_{item['detector_id']}",
                "type": "detector",
                "title": f"Detector: {item['detector_id']}",
                "status": status,
                "severity": severity,
                "summary": f"{item['detector_id']} returned {item['label']} with ai_score={item['ai_score']}.",
                "details": {
                    "ai_score": item["ai_score"],
                    "threshold": item["threshold"],
                    "role": item["role"],
                    "status": item["status"],
                    "duplicate_of": item.get("duplicate_of"),
                    "detector_version": item.get("detector_version"),
                    "error": item.get("error"),
                },
            }
        )
    provenance_state = _provenance_state(evidence["provenance"])
    if provenance_state["ai_declared"]:
        prov_status, prov_severity = "supports_ai", "high"
        prov_summary = "Verified provenance indicates AI generation."
    elif provenance_state["trusted_human"]:
        prov_status, prov_severity = "supports_real", "medium"
        prov_summary = "Verified provenance indicates a trusted capture or edit chain."
    elif provenance_state["missing"]:
        prov_status, prov_severity = "neutral", "info"
        prov_summary = "No verified provenance was available; absence of C2PA is not AI evidence."
    else:
        prov_status, prov_severity = "neutral", "info"
        prov_summary = "Provenance was present but not decisive for this policy."
    cards.append({"id": "provenance_c2pa", "type": "provenance", "title": "C2PA / provenance", "status": prov_status, "severity": prov_severity, "summary": prov_summary, "details": evidence["provenance"]})
    if evidence["metadata_has_ai_trace"]:
        meta_status, meta_severity, meta_summary = "supports_ai", "medium", "Metadata contains a known generator or AI software trace."
    elif evidence["metadata_missing"]:
        meta_status, meta_severity, meta_summary = "neutral", "info", "Metadata is missing or incomplete; this is not AI evidence."
    else:
        meta_status, meta_severity, meta_summary = "neutral", "info", "Metadata did not add decisive AI evidence."
    cards.append({"id": "metadata_trace", "type": "metadata", "title": "Metadata", "status": meta_status, "severity": meta_severity, "summary": meta_summary, "details": evidence["metadata"]})
    if evidence["forensic"]:
        cards.append(
            {
                "id": "forensic_features",
                "type": "forensic",
                "title": "Forensic features",
                "status": "supports_ai" if evidence["forensic_anomaly"] else "neutral",
                "severity": "medium" if evidence["forensic_anomaly"] else "info",
                "summary": "Forensic anomaly was reported." if evidence["forensic_anomaly"] else "Forensic features were not decisive.",
                "details": evidence["forensic"],
            }
        )
    return cards


def explain_decision(label: str, risk: str, reason: str, evidence_cards: list[dict[str, Any]]) -> dict[str, str]:
    notable = [card["summary"] for card in evidence_cards if card.get("status") in {"supports_ai", "supports_real", "conflict", "error"}]
    return {
        "decision_reason": reason,
        "user_facing_summary": f"Policy result: {label} with {risk} risk.",
        "technical_explanation": " ".join([reason, *notable[:4]]).strip(),
    }


def make_policy_snapshot(config: dict[str, Any], detectors: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_config = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
    return {
        "policy_config_hash": hashlib.sha256(normalized_config.encode("utf-8")).hexdigest(),
        "thresholds": config.get("thresholds") or {},
        "policy_profiles": config.get("policy_profiles") or {},
        "detectors": [
            {
                "detector_id": item.get("detector_id"),
                "role": item.get("role"),
                "threshold": item.get("threshold"),
                "detector_version": item.get("detector_version"),
                "model_version": item.get("model_version"),
                "enabled": item.get("enabled"),
                "duplicate_of": item.get("duplicate_of"),
                "status": item.get("status"),
            }
            for item in detectors
        ],
    }


def apply_evidence_policy(
    detector_results: list[dict[str, Any]] | None,
    metadata_result: dict[str, Any] | None = None,
    provenance_result: dict[str, Any] | None = None,
    forensic_result: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    policy_profile: str | None = None,
) -> dict[str, Any]:
    config = load_policy_config(config_path)
    thresholds = config.get("thresholds") or {}
    requested_profile = policy_profile or ((context or {}).get("policy_profile") if isinstance(context, dict) else None)
    profile_name, profile = _policy_profile(config, requested_profile)
    evidence = normalize_evidence_inputs(detector_results, metadata_result, provenance_result, forensic_result, context, config)
    groups = _detector_groups(evidence, thresholds)
    provenance = _provenance_state(evidence["provenance"])
    cards = build_evidence_cards(evidence, config)
    # P1-b Step2: a secondary detector (Ateeqq, and any future ensemble member)
    # may *support* — but never alone decide — an AI verdict. The primary
    # (smogy) is the decision gate itself, so it is not its own support. The
    # diagnostic (dima806) and the hand-crafted baseline (legacy) never vote;
    # they stay auxiliary. (Previously this list excluded BOTH smogy AND ateeqq,
    # which made the "primary high + secondary support" rule impossible.)
    supporting_ai = [
        item
        for item in groups["voting_ai_like"]
        if item["detector_id"] not in SECONDARY_VOTE_EXCLUDED_DETECTORS
        and item["role"] not in NON_VOTING_ROLES
    ]
    has_support = bool(supporting_ai or evidence["metadata_has_ai_trace"] or provenance["ai_declared"] or evidence["forensic_anomaly"])

    label = "uncertain"
    risk = "medium"
    confidence = 0.45
    action = "manual_review"
    review_status = "pending_review"
    reason = "policy could not find enough decisive evidence"
    smogy = groups["active_primary"]
    smogy_score = smogy["ai_score"] if smogy else None
    primary_conflict_real = bool(
        smogy_score is not None
        and smogy_score >= profile["ai_threshold"]
        and profile["primary_conflict_review"]
        and any(item["detector_id"] != "smogy" for item in groups["voting_real_like"])
        and not any(item["detector_id"] != "smogy" for item in supporting_ai)
    )

    if provenance["ai_declared"]:
        label, risk, confidence, action, review_status = "likely_ai", "high", 0.95, "manual_review", "pending_review"
        reason = "verified provenance indicates AI generation"
    elif not groups["has_active_primary"]:
        legacy_ai = next((item for item in groups["ai_like"] if item["detector_id"] == "legacy"), None)
        label, risk, confidence, action, review_status = "needs_review", "unknown", 0.28, "manual_review", "pending_review"
        if legacy_ai:
            reason = "Primary AI detector unavailable; legacy AI-like signal requires review but cannot classify AI alone."
        else:
            reason = "Primary AI detector unavailable; result cannot be trusted."
    elif primary_conflict_real:
        label, risk, confidence, action, review_status = "needs_review", "medium", min(0.7, max(0.46, round(float(smogy_score or 0.0), 4))), "manual_review", "pending_review"
        real_votes = [item["detector_id"] for item in groups["voting_real_like"] if item["detector_id"] != "smogy"]
        reason = f"Primary detector is above the {profile_name} AI threshold, but voting secondary evidence supports real: {real_votes}. Route to review instead of hard AI."
    elif smogy_score is not None and smogy_score >= profile["ai_threshold"]:
        label = "likely_ai"
        risk = profile["ai_risk_level"] if profile["ai_risk_level"] in {"medium", "high", "critical"} else "medium"
        confidence = max(0.55, min(0.95, round(float(smogy_score), 4)))
        action = "manual_review" if profile["ai_review_required"] else "no_action_needed"
        review_status = "pending_review" if profile["ai_review_required"] else "unreviewed"
        reason = f"Primary detector score {smogy_score:.4f} is at or above {profile_name} AI threshold {profile['ai_threshold']:.2f}."
        if has_support:
            risk = "high" if risk == "medium" else risk
            reason += " Supporting AI evidence is present."
    elif smogy_score is not None and smogy_score >= profile["gray_threshold"]:
        label, risk, confidence, action, review_status = "needs_review", profile["review_band_risk_level"], 0.46, "manual_review", "pending_review"
        reason = f"Primary detector score {smogy_score:.4f} falls in review band for {profile_name} profile."
    elif groups["conflicts"] and not groups["smogy_high"]:
        pairs = [f"{left['detector_id']}={left['label']} vs {right['detector_id']}={right['label']}" for left, right in groups["conflicts"]]
        label, risk, confidence, action = "uncertain", "medium", 0.45, "manual_review"
        reason = "detector conflict exists: " + "; ".join(pairs)
        for card in cards:
            if card["type"] == "detector" and any(card["id"].endswith(item["detector_id"]) for pair in groups["conflicts"] for item in pair):
                card["status"] = "conflict"
                card["severity"] = "medium"
    elif groups["primary_errors"] and not groups["ai_like"] and not groups["real_like"]:
        label, risk, confidence, action = "needs_review", "unknown", 0.25, "manual_review"
        reason = "primary detector error prevents a default AI or real decision"
    elif provenance["trusted_human"]:
        if groups["ai_like"]:
            label, risk, confidence, action = "uncertain", "medium", 0.55, "manual_review"
            reason = "verified provenance suggests real capture, but detector conflict exists"
        else:
            label, risk, confidence, action, review_status = "likely_real", "low", 0.7, "no_action_needed", "unreviewed"
            reason = "verified provenance supports a trusted capture or edit chain"
    elif groups["smogy_high"] and has_support:
        label, risk, confidence, action = "likely_ai", "high", 0.86, "manual_review"
        reason = "SMOGY high AI score plus supporting evidence"
    elif groups["smogy_high"]:
        label, risk, confidence, action = "likely_ai", "medium", 0.78, "manual_review"
        reason = "SMOGY high AI score from active primary detector"
    elif groups["smogy_medium"] and len(groups["voting_ai_like"]) >= int(thresholds.get("agreement_min_detectors") or 2):
        label, risk, confidence, action = "likely_ai", "medium", 0.66, "manual_review"
        reason = "SMOGY medium AI score agrees with another non-duplicate detector"
    elif groups["ateeqq_high"] and len(groups["voting_ai_like"]) == 1:
        label, risk, confidence, action = "needs_review", "unknown", 0.35, "manual_review"
        reason = "Ateeqq high score alone is supporting evidence only and cannot classify AI"
    elif groups["all_low"] and not evidence["metadata_has_ai_trace"] and not provenance["ai_declared"]:
        label, risk, confidence, action, review_status = "likely_real", "low", 0.68, "no_action_needed", "unreviewed"
        reason = "all active detectors are low AI score and no AI metadata or provenance trace was found"
        if evidence["metadata_missing"] or provenance["missing"]:
            confidence = min(confidence, 0.62)
            action = "inspect_metadata" if evidence["metadata_missing"] else action
            reason += "; metadata/provenance gaps limit confidence"
    elif groups["primary_errors"]:
        if groups["ai_like"]:
            label, risk, confidence, action = "likely_ai", "medium", 0.58, "manual_review"
            reason = "available detector evidence supports AI, but primary detector error lowers confidence"
        elif groups["real_like"]:
            label, risk, confidence, action = "likely_real", "low", 0.55, "no_action_needed"
            review_status = "unreviewed"
            reason = "available detector evidence supports real, but primary detector error lowers confidence"
        else:
            label, risk, confidence, action = "uncertain", "medium", 0.4, "manual_review"
            reason = "primary detector adapter error requires review"

    explanation = explain_decision(label, risk, reason, cards)
    return {
        "policy_version": str(config.get("policy_version") or "evidence_policy_v1"),
        "policy_profile": profile_name,
        "threshold_profile": profile["threshold_profile"],
        "primary_detector_thresholds": {
            "real_threshold": profile["real_threshold"],
            "gray_threshold": profile["gray_threshold"],
            "ai_threshold": profile["ai_threshold"],
        },
        "final_label": label,
        "risk_level": risk,
        "confidence": confidence,
        "confidence_label": _confidence_label(confidence),
        "decision_reason": explanation["decision_reason"],
        "user_facing_summary": explanation["user_facing_summary"],
        "technical_explanation": explanation["technical_explanation"],
        "recommendation": _recommendation(config, action),
        "evidence_cards": cards,
        "review_status": review_status,
        "policy_snapshot": make_policy_snapshot(config, evidence["detectors"]),
        "debug_evidence": {
            "normalized_inputs": evidence,
            "detector_groups": {
                "ai_like": [item["detector_id"] for item in groups["ai_like"]],
                "real_like": [item["detector_id"] for item in groups["real_like"]],
                "voting_ai_like": [item["detector_id"] for item in groups["voting_ai_like"]],
                "voting_real_like": [item["detector_id"] for item in groups["voting_real_like"]],
                "errors": [item["detector_id"] for item in groups["errors"]],
                "primary_errors": [item["detector_id"] for item in groups["primary_errors"]],
                "auxiliary_errors": [item["detector_id"] for item in groups["auxiliary_errors"]],
                "active_primary": groups["active_primary"]["detector_id"] if groups["active_primary"] else None,
                "has_active_primary": groups["has_active_primary"],
                "primary_detector_score": smogy_score,
                "policy_profile": profile_name,
                "primary_detector_thresholds": {
                    "real_threshold": profile["real_threshold"],
                    "gray_threshold": profile["gray_threshold"],
                    "ai_threshold": profile["ai_threshold"],
                },
                "conflicts": [[left["detector_id"], right["detector_id"]] for left, right in groups["conflicts"]],
            },
        },
    }
