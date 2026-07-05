from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_local_hf_factory_defaults_need_no_user_retuning() -> None:
    detectors = yaml.safe_load((PROJECT_ROOT / "configs" / "detectors.yaml").read_text(encoding="utf-8"))
    policy = yaml.safe_load((PROJECT_ROOT / "configs" / "policy_config.yaml").read_text(encoding="utf-8"))
    review_triggers = yaml.safe_load((PROJECT_ROOT / "configs" / "review_trigger_config.yaml").read_text(encoding="utf-8"))

    enabled = {item["detector_id"]: item for item in detectors["detectors"] if item.get("enabled")}
    assert enabled["smogy"]["model_id"] == "Smogy/SMOGY-Ai-images-detector"
    assert enabled["smogy"]["role"] == "primary"
    assert enabled["smogy"]["threshold"] == 0.5
    assert "peft_adapter_path" not in enabled["smogy"]
    assert enabled["ateeqq"]["model_id"] == "Ateeqq/ai-vs-human-image-detector"
    assert enabled["ateeqq"]["role"] == "secondary"
    assert enabled["ateeqq"]["threshold"] == 0.5

    assert policy["default_policy_profile"] == "strict_safe_plus"
    strict_safe = policy["policy_profiles"]["strict_safe_plus"]
    assert strict_safe["ai_threshold"] == 0.85
    assert strict_safe["gray_threshold"] == 0.35
    assert strict_safe["ai_review_required"] is True

    assert review_triggers["default_profile"] == "strict_safe_plus"
