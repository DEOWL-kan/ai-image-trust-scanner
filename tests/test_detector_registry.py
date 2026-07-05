from __future__ import annotations

from app.detectors import registry as detector_registry
from app.detectors.registry import DetectorRegistry


def test_detector_registry_lists_enabled_and_disabled_detectors() -> None:
    registry = DetectorRegistry()

    enabled_ids = {item["detector_id"] for item in registry.enabled_detectors()}
    disabled_ids = {item["detector_id"] for item in registry.disabled_detectors()}

    assert {"smogy", "ateeqq", "legacy", "dima806"}.issubset(enabled_ids)
    assert "capcheck" in disabled_ids
    assert "capcheck" not in enabled_ids
    capcheck = registry.get("capcheck")
    assert capcheck["duplicate_of"] == "dima806-ai-vs-real-image-detection"
    assert "duplicate_disabled" in capcheck["reason_disabled"]


def test_detector_registry_snapshot_contains_policy_ready_fields() -> None:
    snapshot = DetectorRegistry().snapshot()
    smogy = next(item for item in snapshot["enabled_detectors"] if item["detector_id"] == "smogy")

    assert snapshot["registry_version"] == "day38_detector_registry_v1"
    assert snapshot["model_adapter_version"] == "model_adapter_v2"
    assert smogy["role"] == "primary"
    assert smogy["threshold"] == 0.5
    assert smogy["threshold_profile"] == "default"


def test_local_hf_runtime_is_bounded_and_does_not_cold_load(monkeypatch) -> None:
    # Pin the limit to 1 to deterministically exercise the bounding behaviour
    # (independent of the production default, which P1-b raised to 2).
    monkeypatch.setenv("DETECTOR_RUNTIME_MODE", "local_hf")
    monkeypatch.delenv("DETECTOR_ALLOW_COLD_MODEL_LOAD", raising=False)
    monkeypatch.setenv("DETECTOR_LOCAL_HF_MAX_MODELS", "1")
    detector_registry._HF_RUNTIMES.clear()

    results, summary = detector_registry.build_api_detector_results(
        api_data={"image_path": "missing.jpg"},
        image_hash="hash",
        image_meta={},
    )

    by_id = {item["detector_id"]: item for item in results}
    assert by_id["smogy"]["status"] == "error"
    assert by_id["smogy"]["error"]["type"] == "PrimaryDetectorUnavailable"
    assert "hf_runtime_cold_load_disabled" in by_id["smogy"]["debug"]["notes"]
    assert by_id["ateeqq"]["status"] == "skipped"
    assert "DETECTOR_LOCAL_HF_MAX_MODELS limit reached" in by_id["ateeqq"]["debug"]["notes"]
    assert summary["detector_runtime_mode"] == "local_hf"
    assert len(detector_registry._HF_RUNTIMES) == 1


def test_default_limit_enables_both_smogy_and_ateeqq(monkeypatch) -> None:
    # P1-b: default DETECTOR_LOCAL_HF_MAX_MODELS is now 2, so BOTH HF detectors
    # enter the run path. With cold load still disabled they both report
    # "not loaded" rather than ateeqq being skipped for limit.
    monkeypatch.setenv("DETECTOR_RUNTIME_MODE", "local_hf")
    monkeypatch.delenv("DETECTOR_ALLOW_COLD_MODEL_LOAD", raising=False)
    monkeypatch.delenv("DETECTOR_LOCAL_HF_MAX_MODELS", raising=False)
    detector_registry._HF_RUNTIMES.clear()

    assert detector_registry.local_hf_detector_limit() == 2

    results, _ = detector_registry.build_api_detector_results(
        api_data={"image_path": "missing.jpg"},
        image_hash="hash",
        image_meta={},
    )
    by_id = {item["detector_id"]: item for item in results}
    assert by_id["smogy"]["status"] == "error"
    assert by_id["ateeqq"]["status"] == "error"
    assert "hf_runtime_cold_load_disabled" in by_id["ateeqq"]["debug"]["notes"]
    assert "limit reached" not in " ".join(by_id["ateeqq"]["debug"]["notes"])
    assert len(detector_registry._HF_RUNTIMES) == 2
