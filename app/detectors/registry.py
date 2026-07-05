from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from app.detectors.model_adapter_v2 import (
    MODEL_ADAPTER_VERSION,
    DetectorAdapter,
    DetectorInput,
    image_input_from_payload,
    normalize_legacy_api_result,
    normalize_open_source_result,
)
from app.detectors.hf_image_runtime import HFImageClassificationRuntime, detector_runtime_mode


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "configs" / "detectors.yaml"
DETECTOR_RESULT_SCHEMA_VERSION = "detector_result_v2"
_HF_RUNTIMES: dict[tuple[str, str, float], HFImageClassificationRuntime] = {}
_LOCAL_HF_DETECTORS = {"smogy", "ateeqq"}


def local_hf_detector_limit() -> int:
    # P1-b: default raised 1 -> 2 so the Smogy(primary)+Ateeqq(secondary) vote
    # can run. NOTE: a limit alone does not load weights — the models still need
    # a load mechanism (startup warmup or DETECTOR_ALLOW_COLD_MODEL_LOAD=true),
    # otherwise both HF detectors return "not loaded" at request time.
    raw = os.getenv("DETECTOR_LOCAL_HF_MAX_MODELS", "2")
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return 2


def load_detector_registry_config(path: Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_REGISTRY_PATH)
    with source.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    data.setdefault("registry_version", "day38_detector_registry_v1")
    data.setdefault("model_adapter_version", MODEL_ADAPTER_VERSION)
    data.setdefault("detectors", [])
    return data


class DetectorRegistry:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_detector_registry_config()
        self.registry_version = str(self.config.get("registry_version") or "day38_detector_registry_v1")
        self.model_adapter_version = str(self.config.get("model_adapter_version") or MODEL_ADAPTER_VERSION)
        self.entries: list[dict[str, Any]] = [
            dict(item) for item in self.config.get("detectors", []) if isinstance(item, dict)
        ]

    def enabled_detectors(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries if bool(entry.get("enabled", True))]

    def disabled_detectors(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries if not bool(entry.get("enabled", True))]

    def get(self, detector_id: str) -> dict[str, Any]:
        for entry in self.entries:
            if entry.get("detector_id") == detector_id:
                return entry
        raise KeyError(detector_id)

    def adapter_for(self, detector_id: str, **overrides: Any) -> DetectorAdapter:
        entry = {**self.get(detector_id), **overrides}
        runtime_mode = detector_runtime_mode()
        force_stub = bool(entry.pop("_force_stub", False))
        enabled = bool(entry.get("enabled", True))
        predictor = entry.get("predictor")
        reason_skipped = entry.get("reason_skipped")
        reason_disabled = entry.get("reason_disabled")
        if detector_id in _LOCAL_HF_DETECTORS:
            if runtime_mode == "disabled":
                enabled = False
                reason_disabled = "DETECTOR_RUNTIME_MODE=disabled"
            elif runtime_mode == "local_hf" and not force_stub:
                peft_adapter_path = str(entry.get("peft_adapter_path") or "")
                runtime_key = (detector_id, str(entry.get("model_id") or "") + ("@" + peft_adapter_path if peft_adapter_path else ""), float(entry.get("threshold", 0.5)))
                runtime = _HF_RUNTIMES.setdefault(
                    runtime_key,
                    HFImageClassificationRuntime(
                        detector_id=detector_id,
                        model_id=str(entry.get("model_id") or ""),
                        threshold=float(entry.get("threshold", 0.5)),
                        peft_adapter_path=peft_adapter_path or None,
                    ),
                )
                predictor = runtime.predict
                reason_skipped = None
            else:
                predictor = None
                reason_skipped = "DETECTOR_LOCAL_HF_MAX_MODELS limit reached" if force_stub else (reason_skipped or "DETECTOR_RUNTIME_MODE=stub")
        return DetectorAdapter(
            detector_id=str(entry.get("detector_id")),
            detector_name=str(entry.get("detector_name") or entry.get("source_detector_id") or entry.get("detector_id")),
            role=str(entry.get("role") or "diagnostic"),
            threshold=float(entry.get("threshold", 0.5)),
            threshold_profile=str(entry.get("threshold_profile") or self.config.get("threshold_profile") or "default"),
            detector_version=str(entry.get("source_detector_id") or "unknown"),
            model_version=str(entry.get("model_id") or "unknown"),
            enabled=enabled,
            duplicate_of=entry.get("duplicate_of"),
            reason_disabled=reason_disabled,
            reason_skipped=reason_skipped,
            predictor=predictor,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "model_adapter_version": self.model_adapter_version,
            "detector_result_schema_version": DETECTOR_RESULT_SCHEMA_VERSION,
            "enabled_detectors": [
                self._entry_snapshot(entry) for entry in self.enabled_detectors()
            ],
            "disabled_detectors": [
                self._entry_snapshot(entry) for entry in self.disabled_detectors()
            ],
        }

    @staticmethod
    def _entry_snapshot(entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "detector_id": entry.get("detector_id"),
            "source_detector_id": entry.get("source_detector_id"),
            "role": entry.get("role"),
            "threshold": entry.get("threshold"),
            "threshold_profile": entry.get("threshold_profile"),
            "duplicate_of": entry.get("duplicate_of"),
            "reason_disabled": entry.get("reason_disabled"),
            "enabled": bool(entry.get("enabled", True)),
        }


def build_detector_summary(results: list[dict[str, Any]], registry: DetectorRegistry | None = None) -> dict[str, Any]:
    registry = registry or DetectorRegistry()
    return {
        "schema_version": DETECTOR_RESULT_SCHEMA_VERSION,
        "enabled_count": len(registry.enabled_detectors()),
        "ok_count": sum(1 for item in results if item.get("status") == "ok"),
        "error_count": sum(1 for item in results if item.get("status") == "error"),
        "skipped_count": sum(1 for item in results if item.get("status") == "skipped"),
        "disabled_count": len(registry.disabled_detectors()) + sum(1 for item in results if item.get("status") == "disabled"),
        "primary_detector": next(
            (entry.get("detector_id") for entry in registry.enabled_detectors() if entry.get("role") == "primary"),
            None,
        ),
        "registry_version": registry.registry_version,
        "model_adapter_version": registry.model_adapter_version,
            "threshold_profile": str(registry.config.get("threshold_profile") or "default"),
            "detector_runtime_mode": detector_runtime_mode(),
            "active_primary_valid": any(
                item.get("detector_id") == "smogy"
                and item.get("status") == "ok"
                and item.get("ai_score") is not None
                for item in results
            ),
    }


def build_model_status(registry: DetectorRegistry | None = None) -> dict[str, Any]:
    registry = registry or DetectorRegistry()
    runtimes = []
    for (detector_id, model_id, threshold), runtime in _HF_RUNTIMES.items():
        runtimes.append(
            {
                "detector_id": detector_id,
                "model_id": model_id,
                "threshold": threshold,
                **runtime.config_summary(),
            }
        )
    return {
        "detector_runtime_mode": detector_runtime_mode(),
        "local_hf_max_models": local_hf_detector_limit(),
        "registered_detectors": registry.snapshot()["enabled_detectors"],
        "hf_runtime_count": len(runtimes),
        "hf_runtimes": runtimes,
    }


def warmup_local_hf_detectors(registry: DetectorRegistry | None = None) -> dict[str, Any]:
    """Preload up to the configured limit of local HF detectors into the runtime
    cache so request-time predictions skip the cold-load guard (predict() only
    blocks when the model is None). Safe to call from a background thread at
    startup: it never raises, and per-model load failures degrade to an error
    entry instead of crashing. Only runs in local_hf mode.
    """
    registry = registry or DetectorRegistry()
    if detector_runtime_mode() != "local_hf":
        return {"mode": detector_runtime_mode(), "loaded": [], "skipped": "not_local_hf"}
    limit = local_hf_detector_limit()
    loaded: list[dict[str, Any]] = []
    started = 0
    for entry in registry.enabled_detectors():
        detector_id = str(entry.get("detector_id"))
        if detector_id not in _LOCAL_HF_DETECTORS:
            continue
        if started >= limit:
            break
        started += 1
        peft_adapter_path = str(entry.get("peft_adapter_path") or "")
        runtime_key = (detector_id, str(entry.get("model_id") or "") + ("@" + peft_adapter_path if peft_adapter_path else ""), float(entry.get("threshold", 0.5)))
        runtime = _HF_RUNTIMES.setdefault(
            runtime_key,
            HFImageClassificationRuntime(
                detector_id=detector_id,
                model_id=str(entry.get("model_id") or ""),
                threshold=float(entry.get("threshold", 0.5)),
                peft_adapter_path=peft_adapter_path or None,
            ),
        )
        runtime._load_model()  # noqa: SLF001 — intentional warmup of the cached runtime
        loaded.append({"detector_id": detector_id, "model_loaded": runtime._model is not None, "load_error": runtime._load_error})
    return {"mode": "local_hf", "limit": limit, "loaded": loaded}


def build_api_detector_results(
    *,
    api_data: dict[str, Any],
    image_hash: str | None,
    image_meta: dict[str, Any],
    registry: DetectorRegistry | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = registry or DetectorRegistry()
    input_meta: DetectorInput = image_input_from_payload(
        image_hash=image_hash,
        width=image_meta.get("width"),
        height=image_meta.get("height"),
        format=image_meta.get("format"),
        mode=image_meta.get("mode"),
    )
    results = []
    runtime_mode = detector_runtime_mode()
    local_hf_limit = local_hf_detector_limit()
    local_hf_started = 0
    for entry in registry.enabled_detectors():
        detector_id = str(entry.get("detector_id"))
        force_stub = False
        if runtime_mode == "local_hf" and detector_id in _LOCAL_HF_DETECTORS:
            force_stub = local_hf_started >= local_hf_limit
            if not force_stub:
                local_hf_started += 1
        adapter = registry.adapter_for(detector_id, _force_stub=force_stub)
        if detector_id == "legacy":
            result = normalize_legacy_api_result(adapter=adapter, api_data=api_data, input_meta=input_meta)
        elif detector_id == "dima806":
            evidence = api_data.get("open_source_evidence") if isinstance(api_data.get("open_source_evidence"), dict) else {}
            result = normalize_open_source_result(adapter=adapter, evidence=evidence, input_meta=input_meta)
        else:
            image_path = api_data.get("image_path")
            result = adapter.predict(image_path, context={"input": input_meta})
        results.append(result.to_dict())
    return results, build_detector_summary(results, registry)
