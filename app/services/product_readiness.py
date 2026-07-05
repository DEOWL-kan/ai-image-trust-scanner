from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = "product_readiness_check_v1"


def _ok_check(
    name: str,
    passed: bool,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else ("warn" if severity == "warning" else "fail"),
        "message": message,
        "details": details or {},
    }


def _runtime_by_id(model_status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runtimes = model_status.get("hf_runtimes") if isinstance(model_status.get("hf_runtimes"), list) else []
    return {
        str(item.get("detector_id") or item.get("model_id") or ""): item
        for item in runtimes
        if isinstance(item, dict)
    }


def _summary(checks: list[dict[str, Any]], *, deployment_profile: str, mode: str | None = None) -> dict[str, Any]:
    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "deployment_profile": deployment_profile,
        "status": "fail" if failed else "warn" if warnings else "pass",
        "summary": {
            "passed": sum(1 for item in checks if item["status"] == "pass"),
            "warnings": len(warnings),
            "failed": len(failed),
        },
        "checks": checks,
    }
    if mode:
        payload["mode"] = mode
    return payload


def evaluate_readiness(
    *,
    health: dict[str, Any] | None,
    model_status: dict[str, Any] | None,
    policy_profiles: dict[str, Any] | None,
    retention: dict[str, Any] | None,
    frontend: dict[str, Any] | None,
    deployment_profile: str = "local_gpu_max",
) -> dict[str, Any]:
    health = health if isinstance(health, dict) else {}
    model_status = model_status if isinstance(model_status, dict) else {}
    policy_profiles = policy_profiles if isinstance(policy_profiles, dict) else {}
    retention = retention if isinstance(retention, dict) else {}
    frontend = frontend if isinstance(frontend, dict) else {}
    checks: list[dict[str, Any]] = []

    checks.append(_ok_check("api_health", health.get("api_status") == "ok", "API health endpoint returns ok.", details={"api_status": health.get("api_status")}))
    checks.append(_ok_check("warmup_ready", bool(health.get("warmup_ready")), "Model warmup gate is ready.", details={"warmup_ready": health.get("warmup_ready")}))
    checks.append(
        _ok_check(
            "persistence",
            health.get("database_status") == "ok" and bool(health.get("persistence_enabled")),
            "SQLite report persistence is available.",
            details={"database_status": health.get("database_status"), "persistence_enabled": health.get("persistence_enabled")},
        )
    )

    runtimes = _runtime_by_id(model_status)
    smogy = runtimes.get("smogy") or {}
    ateeqq = runtimes.get("ateeqq") or {}
    expects_gpu = deployment_profile == "local_gpu_max"
    checks.append(
        _ok_check(
            "hf_runtime_mode",
            model_status.get("detector_runtime_mode") == "local_hf" if expects_gpu else bool(model_status.get("detector_runtime_mode")),
            "Detector runtime mode is appropriate for the deployment profile.",
            details={"detector_runtime_mode": model_status.get("detector_runtime_mode"), "deployment_profile": deployment_profile},
        )
    )
    if expects_gpu:
        ateeqq_loaded = bool(ateeqq.get("model_loaded"))
        checks.extend(
            [
                _ok_check("smogy_loaded", bool(smogy.get("model_loaded")), "Smogy primary runtime is loaded.", details=smogy),
                _ok_check("ateeqq_loaded", ateeqq_loaded, "Ateeqq secondary runtime is loaded.", details={"model_loaded": ateeqq.get("model_loaded"), "load_error": ateeqq.get("load_error")}),
                _ok_check("smogy_lora", bool(smogy.get("peft_loaded")), "Smogy local LoRA adapter is loaded.", details={"peft_adapter_path": smogy.get("peft_adapter_path"), "peft_loaded": smogy.get("peft_loaded")}),
                _ok_check(
                    "cuda_runtime",
                    str(smogy.get("resolved_device") or smogy.get("device")).lower() == "cuda"
                    and str(ateeqq.get("resolved_device") or ateeqq.get("device")).lower() == "cuda",
                    "HF runtimes are on CUDA.",
                    details={"smogy_device": smogy.get("resolved_device") or smogy.get("device"), "ateeqq_device": ateeqq.get("resolved_device") or ateeqq.get("device"), "ateeqq_loaded": ateeqq_loaded},
                ),
            ]
        )

    profile_names = {
        str(item.get("name") or "")
        for item in (policy_profiles.get("profiles") if isinstance(policy_profiles.get("profiles"), list) else [])
        if isinstance(item, dict)
    }
    required_profiles = {"strict_safe_plus", "high_recall_review", "strict_safe_plus_lora_v2", "strict_safe_plus_mirage_low_fp"}
    checks.append(
        _ok_check(
            "policy_profiles",
            required_profiles.issubset(profile_names)
            and policy_profiles.get("product_default_policy_profile") == "strict_safe_plus",
            "Required policy profiles are exposed.",
            details={"product_default_policy_profile": policy_profiles.get("product_default_policy_profile"), "profiles": sorted(profile_names), "required_profiles": sorted(required_profiles)},
        )
    )

    retention_totals = retention.get("totals") if isinstance(retention.get("totals"), dict) else {}
    checks.append(
        _ok_check(
            "retention_dry_run",
            retention.get("schema_version") == "retention_policy_v1" and retention.get("apply") is False,
            "Retention endpoint returns dry-run plan.",
            details=retention_totals or {"error": retention.get("_error")},
        )
    )
    if int(retention_totals.get("would_delete_files") or 0) > 0:
        checks.append(
            _ok_check(
                "retention_backlog",
                False,
                "Retention has old local artifacts ready for cleanup.",
                severity="warning",
                details=retention_totals,
            )
        )

    checks.extend(
        [
            _ok_check("frontend_index", bool(frontend.get("index_ok")), "Dashboard index contains required product hooks.", details=frontend.get("index") or {}),
            _ok_check("frontend_theme", bool(frontend.get("theme_ok")), "Dashboard stylesheet is served.", details=frontend.get("theme") or {}),
            _ok_check("frontend_app", bool(frontend.get("app_ok")), "Dashboard app contains policy/auth wiring.", details=frontend.get("app") or {}),
        ]
    )
    return _summary(checks, deployment_profile=deployment_profile)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def evaluate_offline_readiness(*, project_root: str | Path, deployment_profile: str = "local_gpu_max") -> dict[str, Any]:
    root = Path(project_root)
    checks: list[dict[str, Any]] = []
    policy_path = root / "configs" / "policy_config.yaml"
    detector_path = root / "configs" / "detectors.yaml"
    index_path = root / "frontend" / "dashboard" / "index.html"
    theme_path = root / "frontend" / "dashboard" / "styles.css"
    app_path = root / "frontend" / "dashboard" / "app.js"

    try:
        policy_config = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        policy_config = {}
        policy_error = str(exc)
    else:
        policy_error = ""
    profiles = policy_config.get("policy_profiles") if isinstance(policy_config.get("policy_profiles"), dict) else {}
    required_profiles = {"strict_safe_plus", "high_recall_review", "strict_safe_plus_lora_v2", "strict_safe_plus_mirage_low_fp"}
    checks.append(
        _ok_check(
            "offline_policy_config",
            policy_path.exists() and required_profiles.issubset(set(profiles)),
            "Policy config exists and exposes required product profiles.",
            details={"path": str(policy_path), "profiles": sorted(profiles), "error": policy_error},
        )
    )

    try:
        detector_config = yaml.safe_load(detector_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        detector_config = {}
        detector_error = str(exc)
    else:
        detector_error = ""
    detectors = detector_config.get("detectors") if isinstance(detector_config.get("detectors"), list) else []
    smogy = next((item for item in detectors if isinstance(item, dict) and item.get("detector_id") == "smogy"), {})
    adapter_value = str(smogy.get("peft_adapter_path") or "").strip()
    adapter = Path(adapter_value) if adapter_value else None
    adapter_path = adapter if adapter and adapter.is_absolute() else root / adapter if adapter else None
    checks.append(
        _ok_check(
            "offline_smogy_lora_path",
            detector_path.exists() and bool(smogy) and (adapter_path.exists() if adapter_path else True),
            "Smogy LoRA adapter is optional in the public CPU-safe default.",
            details={
                "detector_config": str(detector_path),
                "peft_adapter_path": str(adapter_path) if adapter_path else None,
                "adapter_configured": bool(adapter_path),
                "error": detector_error,
            },
        )
    )

    index = _read_text(index_path)
    theme = _read_text(theme_path)
    app_js = _read_text(app_path)
    checks.extend(
        [
            _ok_check(
                "offline_frontend_index",
                index_path.exists()
                and "styles.css" in index
                and "policy-profile-switch" in index
                and "demo-result-fixture" in index
                and "console-theme.css" not in index
                and "global-particles" not in index,
                "Dashboard index contains minimal local workbench hooks.",
                details={"path": str(index_path)},
            ),
            _ok_check(
                "offline_frontend_theme",
                theme_path.exists()
                and "workbench-shell" in theme
                and "policy-profile-switch" in theme
                and "global-particles" not in theme,
                "Dashboard stylesheet contains minimal workbench hooks.",
                details={"path": str(theme_path)},
            ),
            _ok_check(
                "offline_frontend_app",
                app_path.exists() and "policyProfiles" in app_js and "policy_profile" in app_js and "authHeaders" in app_js,
                "Dashboard app contains policy/profile/auth wiring.",
                details={"path": str(app_path)},
            ),
            _ok_check(
                "offline_note",
                True,
                "Offline mode checks local files only; API health, CUDA, warmup, and static serving require --mode online with a running server.",
                severity="warning",
            ),
        ]
    )
    return _summary(checks, deployment_profile=deployment_profile, mode="offline")
