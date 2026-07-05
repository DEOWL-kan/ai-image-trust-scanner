from __future__ import annotations

from pathlib import Path

import yaml

from app.services.product_readiness import evaluate_offline_readiness
from app.services.product_readiness import evaluate_readiness


def _good_payloads():
    health = {"api_status": "ok", "warmup_ready": True, "database_status": "ok", "persistence_enabled": True}
    model_status = {
        "detector_runtime_mode": "local_hf",
        "hf_runtimes": [
            {"detector_id": "smogy", "model_loaded": True, "peft_loaded": True, "resolved_device": "cuda"},
            {"detector_id": "ateeqq", "model_loaded": True, "resolved_device": "cuda"},
        ],
    }
    policy_profiles = {
        "product_default_policy_profile": "strict_safe_plus",
        "profiles": [
            {"name": "strict_safe_plus"},
            {"name": "high_recall_review"},
            {"name": "strict_safe_plus_lora_v2"},
            {"name": "strict_safe_plus_mirage_low_fp"},
        ],
    }
    retention = {"schema_version": "retention_policy_v1", "apply": False, "totals": {"would_delete_files": 0}}
    frontend = {
        "index_ok": True,
        "theme_ok": True,
        "app_ok": True,
        "index": {},
        "theme": {},
        "app": {},
    }
    return health, model_status, policy_profiles, retention, frontend


def test_product_readiness_passes_for_local_gpu_max_payload() -> None:
    health, model_status, policy_profiles, retention, frontend = _good_payloads()

    report = evaluate_readiness(
        health=health,
        model_status=model_status,
        policy_profiles=policy_profiles,
        retention=retention,
        frontend=frontend,
        deployment_profile="local_gpu_max",
    )

    assert report["schema_version"] == "product_readiness_check_v1"
    assert report["status"] == "pass"
    assert report["summary"]["failed"] == 0


def test_product_readiness_warns_for_retention_backlog() -> None:
    health, model_status, policy_profiles, retention, frontend = _good_payloads()
    retention["totals"]["would_delete_files"] = 2

    report = evaluate_readiness(
        health=health,
        model_status=model_status,
        policy_profiles=policy_profiles,
        retention=retention,
        frontend=frontend,
        deployment_profile="local_gpu_max",
    )

    assert report["status"] == "warn"
    assert any(item["name"] == "retention_backlog" and item["status"] == "warn" for item in report["checks"])


def test_product_readiness_fails_when_gpu_runtime_is_not_loaded() -> None:
    health, model_status, policy_profiles, retention, frontend = _good_payloads()
    model_status["hf_runtimes"][0]["model_loaded"] = False
    model_status["hf_runtimes"][0]["load_error"] = "missing torch"

    report = evaluate_readiness(
        health=health,
        model_status=model_status,
        policy_profiles=policy_profiles,
        retention=retention,
        frontend=frontend,
        deployment_profile="local_gpu_max",
    )

    assert report["status"] == "fail"
    assert any(item["name"] == "smogy_loaded" and item["status"] == "fail" for item in report["checks"])


def test_offline_readiness_checks_local_config_and_frontend_hooks(tmp_path: Path) -> None:
    root = tmp_path
    (root / "configs").mkdir()
    (root / "frontend" / "dashboard").mkdir(parents=True)
    (root / "configs" / "policy_config.yaml").write_text(
        yaml.safe_dump(
            {
                "policy_profiles": {
                    "strict_safe_plus": {},
                    "high_recall_review": {},
                    "strict_safe_plus_lora_v2": {},
                    "strict_safe_plus_mirage_low_fp": {},
                }
            }
        ),
        encoding="utf-8",
    )
    (root / "configs" / "detectors.yaml").write_text(
        yaml.safe_dump({"detectors": [{"detector_id": "smogy"}]}),
        encoding="utf-8",
    )
    (root / "frontend" / "dashboard" / "index.html").write_text(
        "styles.css policy-profile-switch demo-result-fixture",
        encoding="utf-8",
    )
    (root / "frontend" / "dashboard" / "styles.css").write_text(
        "workbench-shell policy-profile-switch",
        encoding="utf-8",
    )
    (root / "frontend" / "dashboard" / "app.js").write_text(
        "policyProfiles policy_profile authHeaders",
        encoding="utf-8",
    )

    report = evaluate_offline_readiness(project_root=root)

    assert report["mode"] == "offline"
    assert report["summary"]["failed"] == 0
    lora_check = next(item for item in report["checks"] if item["name"] == "offline_smogy_lora_path")
    assert lora_check["status"] == "pass"
    assert lora_check["details"]["adapter_configured"] is False
    assert any(item["name"] == "offline_note" for item in report["checks"])
