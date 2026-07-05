from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "detector_result_v2"
MODEL_ADAPTER_VERSION = "model_adapter_v2"
VALID_LABELS = {"ai", "real", "uncertain", "error", "skipped"}
VALID_STATUS = {"ok", "skipped", "error", "disabled"}


@dataclass(frozen=True)
class DetectorInput:
    image_hash: str | None = None
    width: int = 0
    height: int = 0
    format: str = "unknown"
    mode: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DetectorError:
    type: str | None = None
    message: str | None = None
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DetectorResultV2:
    schema_version: str
    detector_id: str
    detector_name: str
    detector_version: str
    model_version: str
    role: str
    status: str
    ai_score: float
    real_score: float
    raw_score: float
    threshold: float
    threshold_profile: str
    predicted_label: str
    confidence: float
    latency_ms: float
    device: str
    input: DetectorInput
    error: DetectorError = field(default_factory=DetectorError)
    debug: dict[str, Any] = field(default_factory=lambda: {"raw_output": {}, "notes": []})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["debug"] = {
            "raw_output": self.debug.get("raw_output") if isinstance(self.debug.get("raw_output"), dict) else {},
            "notes": [str(item) for item in self.debug.get("notes", [])],
        }
        return payload


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(0.0, min(1.0, number)), 6)


def confidence_from_threshold(ai_score: float, threshold: float) -> float:
    distance = abs(clamp01(ai_score) - clamp01(threshold, 0.5))
    scale = max(threshold, 1.0 - threshold, 0.5)
    return round(max(0.0, min(1.0, distance / scale)), 6)


def label_from_score(ai_score: float, threshold: float, status: str) -> str:
    if status == "disabled":
        return "skipped"
    if status == "skipped":
        return "skipped"
    if status == "error":
        return "error"
    return "ai" if ai_score >= threshold else "real"


def image_input_from_payload(
    *,
    image_hash: str | None = None,
    width: Any = 0,
    height: Any = 0,
    format: Any = "unknown",
    mode: Any = "unknown",
) -> DetectorInput:
    try:
        width_value = max(0, int(width or 0))
    except (TypeError, ValueError):
        width_value = 0
    try:
        height_value = max(0, int(height or 0))
    except (TypeError, ValueError):
        height_value = 0
    return DetectorInput(
        image_hash=image_hash,
        width=width_value,
        height=height_value,
        format=str(format or "unknown").lower(),
        mode=str(mode or "unknown"),
    )


class DetectorAdapter:
    detector_id: str
    detector_name: str
    role: str
    threshold: float
    threshold_profile: str

    def __init__(
        self,
        *,
        detector_id: str,
        detector_name: str,
        role: str,
        threshold: float = 0.5,
        threshold_profile: str = "default",
        detector_version: str = "unknown",
        model_version: str = "unknown",
        device: str = "unknown",
        enabled: bool = True,
        duplicate_of: str | None = None,
        reason_disabled: str | None = None,
        reason_skipped: str | None = None,
        predictor: Callable[[Any], Any] | None = None,
    ) -> None:
        self.detector_id = detector_id
        self.detector_name = detector_name
        self.role = "disabled" if not enabled else role
        self.threshold = clamp01(threshold, 0.5)
        self.threshold_profile = threshold_profile or "default"
        self.detector_version = detector_version or "unknown"
        self.model_version = model_version or "unknown"
        self.device = device if device in {"cpu", "cuda", "mps", "unknown"} else "unknown"
        self.enabled = bool(enabled)
        self.duplicate_of = duplicate_of
        self.reason_disabled = reason_disabled
        self.reason_skipped = reason_skipped
        self.predictor = predictor

    def predict(self, image_input: Any, context: dict[str, Any] | None = None) -> DetectorResultV2:
        context = context or {}
        started = time.perf_counter()
        input_meta = context.get("input")
        if not isinstance(input_meta, DetectorInput):
            input_meta = image_input_from_payload(**(input_meta if isinstance(input_meta, dict) else {}))

        if not self.enabled:
            return self.normalize_result(
                status="disabled",
                ai_score=0.0,
                real_score=0.0,
                raw_score=0.0,
                input_meta=input_meta,
                latency_ms=0.0,
                error=DetectorError(type="DetectorDisabled", message=self.reason_disabled, recoverable=True),
                raw_output={},
                notes=["disabled_detector", *(["duplicate_disabled"] if self.duplicate_of else [])],
            )

        if self.predictor is None:
            return self.normalize_result(
                status="skipped",
                ai_score=0.0,
                real_score=0.0,
                raw_score=0.0,
                input_meta=input_meta,
                latency_ms=self._elapsed_ms(started),
                error=DetectorError(type=None, message=None, recoverable=True),
                raw_output={},
                notes=[self.reason_skipped or "no_runtime_predictor_configured"],
            )

        try:
            raw = self.predictor(image_input)
            return self.normalize_raw_output(raw, input_meta=input_meta, latency_ms=self._elapsed_ms(started))
        except Exception as exc:
            return self.normalize_result(
                status="error",
                ai_score=0.0,
                real_score=0.0,
                raw_score=0.0,
                input_meta=input_meta,
                latency_ms=self._elapsed_ms(started),
                error=DetectorError(type=type(exc).__name__, message=str(exc), recoverable=True),
                raw_output={},
                notes=["predict_exception_captured"],
            )

    def predict_many(self, image_inputs: list[Any], contexts: list[dict[str, Any] | None] | None = None) -> list[DetectorResultV2]:
        contexts = [None] * len(image_inputs) if contexts is None else contexts
        if len(contexts) != len(image_inputs):
            raise ValueError("contexts length must match image_inputs length")
        input_metas: list[DetectorInput] = []
        for context in contexts:
            context = context or {}
            input_meta = context.get("input")
            if not isinstance(input_meta, DetectorInput):
                input_meta = image_input_from_payload(**(input_meta if isinstance(input_meta, dict) else {}))
            input_metas.append(input_meta)

        if not self.enabled:
            return [
                self.normalize_result(
                    status="disabled",
                    ai_score=0.0,
                    real_score=0.0,
                    raw_score=0.0,
                    input_meta=input_meta,
                    latency_ms=0.0,
                    error=DetectorError(type="DetectorDisabled", message=self.reason_disabled, recoverable=True),
                    raw_output={},
                    notes=["disabled_detector", *(["duplicate_disabled"] if self.duplicate_of else [])],
                )
                for input_meta in input_metas
            ]

        if self.predictor is None:
            return [
                self.normalize_result(
                    status="skipped",
                    ai_score=0.0,
                    real_score=0.0,
                    raw_score=0.0,
                    input_meta=input_meta,
                    latency_ms=0.0,
                    error=DetectorError(type=None, message=None, recoverable=True),
                    raw_output={},
                    notes=[self.reason_skipped or "no_runtime_predictor_configured"],
                )
                for input_meta in input_metas
            ]

        runtime = getattr(self.predictor, "__self__", None)
        batch_predict = getattr(runtime, "predict_many", None)
        if not callable(batch_predict):
            return [self.predict(image_input, context=context) for image_input, context in zip(image_inputs, contexts)]

        started = time.perf_counter()
        try:
            raw_outputs = batch_predict(image_inputs)
            if len(raw_outputs) != len(image_inputs):
                raise ValueError("batch predictor returned a different number of outputs")
        except Exception as exc:
            return [
                self.normalize_result(
                    status="error",
                    ai_score=0.0,
                    real_score=0.0,
                    raw_score=0.0,
                    input_meta=input_meta,
                    latency_ms=self._elapsed_ms(started),
                    error=DetectorError(type=type(exc).__name__, message=str(exc), recoverable=True),
                    raw_output={},
                    notes=["batch_predict_exception_captured"],
                )
                for input_meta in input_metas
            ]
        latency_ms = self._elapsed_ms(started)
        results: list[DetectorResultV2] = []
        for raw, input_meta in zip(raw_outputs, input_metas):
            results.append(self.normalize_raw_output(raw, input_meta=input_meta, latency_ms=latency_ms))
        return results

    def normalize_raw_output(
        self,
        raw: Any,
        *,
        input_meta: DetectorInput,
        latency_ms: float,
    ) -> DetectorResultV2:
        raw_dict = raw if isinstance(raw, dict) else {"value": raw}
        status = str(raw_dict.get("status") or "ok").lower()
        if status not in VALID_STATUS:
            status = "ok"
        error_value = raw_dict.get("error")
        if error_value and status == "ok":
            status = "error"

        notes = [str(item) for item in raw_dict.get("notes", [])] if isinstance(raw_dict.get("notes"), list) else []
        ai_score = raw_dict.get("ai_score")
        if ai_score is None:
            ai_score = raw_dict.get("open_source_score", raw_dict.get("score"))
        if ai_score is None:
            ai_score = raw_dict.get("raw_score")
        ai = clamp01(ai_score, 0.0)
        real_input = raw_dict.get("real_score")
        if real_input is None:
            real = round(1.0 - ai, 6)
            notes.append("real_score_derived_from_ai_score")
        else:
            real = clamp01(real_input, 1.0 - ai)
        raw_score = clamp01(raw_dict.get("raw_score", ai), ai)
        predicted = str(raw_dict.get("predicted_label") or label_from_score(ai, self.threshold, status)).lower()
        if predicted not in VALID_LABELS:
            predicted = label_from_score(ai, self.threshold, status)
        confidence = raw_dict.get("confidence")
        if confidence is None:
            confidence_value = confidence_from_threshold(ai, self.threshold)
            notes.append("confidence_derived_from_threshold_distance")
        else:
            confidence_value = clamp01(confidence)

        error = DetectorError()
        if status == "error":
            error = DetectorError(
                type=str(raw_dict.get("error_type") or "DetectorError"),
                message=str(error_value or raw_dict.get("error_message") or "Detector returned an error."),
                recoverable=bool(raw_dict.get("recoverable", True)),
            )

        return self.normalize_result(
            status=status,
            ai_score=ai,
            real_score=real,
            raw_score=raw_score,
            predicted_label=predicted,
            confidence=confidence_value,
            input_meta=input_meta,
            latency_ms=latency_ms,
            error=error,
            raw_output=raw_dict,
            notes=notes,
        )

    def normalize_result(
        self,
        *,
        status: str,
        ai_score: Any,
        real_score: Any,
        raw_score: Any,
        input_meta: DetectorInput,
        latency_ms: Any,
        error: DetectorError | None = None,
        raw_output: dict[str, Any] | None = None,
        notes: list[str] | None = None,
        predicted_label: str | None = None,
        confidence: Any | None = None,
    ) -> DetectorResultV2:
        status_value = status if status in VALID_STATUS else "error"
        ai = clamp01(ai_score)
        real = clamp01(real_score)
        raw = clamp01(raw_score, ai)
        label = predicted_label or label_from_score(ai, self.threshold, status_value)
        if label not in VALID_LABELS:
            label = label_from_score(ai, self.threshold, status_value)
        default_confidence = 0.0 if status_value in {"disabled", "skipped", "error"} else confidence_from_threshold(ai, self.threshold)
        conf = clamp01(confidence, default_confidence)
        try:
            latency = round(max(0.0, float(latency_ms or 0.0)), 3)
        except (TypeError, ValueError):
            latency = 0.0
        return DetectorResultV2(
            schema_version=SCHEMA_VERSION,
            detector_id=self.detector_id,
            detector_name=self.detector_name,
            detector_version=str(self.detector_version or "unknown"),
            model_version=str(self.model_version or "unknown"),
            role=self.role,
            status=status_value,
            ai_score=ai,
            real_score=real,
            raw_score=raw,
            threshold=self.threshold,
            threshold_profile=self.threshold_profile,
            predicted_label=label,
            confidence=conf,
            latency_ms=latency,
            device=self.device,
            input=input_meta,
            error=error or DetectorError(),
            debug={"raw_output": raw_output or {}, "notes": notes or []},
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000.0, 3)


def normalize_legacy_api_result(
    *,
    adapter: DetectorAdapter,
    api_data: dict[str, Any],
    input_meta: DetectorInput,
) -> DetectorResultV2:
    debug = api_data.get("debug_evidence") if isinstance(api_data.get("debug_evidence"), dict) else {}
    tech = api_data.get("technical_explanation") if isinstance(api_data.get("technical_explanation"), dict) else {}
    ai_score = tech.get("score", debug.get("raw_score"))
    final_label = str(api_data.get("final_label") or "").lower()
    if ai_score is None:
        ai_score = 1.0 if final_label in {"ai", "ai_generated"} else 0.0 if final_label == "real" else 0.5
    raw_latency = debug.get("latency_ms") or debug.get("runtime_ms") or 0.0
    return adapter.normalize_raw_output(
        {
            "status": "ok",
            "ai_score": ai_score,
            "raw_score": ai_score,
            "threshold": tech.get("threshold_used") or adapter.threshold,
            "predicted_label": "ai" if final_label in {"ai", "ai_generated"} else "real" if final_label == "real" else "uncertain",
            "raw_output": {"technical_explanation": tech, "debug_evidence": debug},
            "notes": ["legacy_api_payload_normalized"],
        },
        input_meta=input_meta,
        latency_ms=raw_latency,
    )


def normalize_open_source_result(
    *,
    adapter: DetectorAdapter,
    evidence: dict[str, Any],
    input_meta: DetectorInput,
) -> DetectorResultV2:
    enabled = bool(evidence.get("enabled"))
    available = bool(evidence.get("available"))
    if not enabled:
        return adapter.normalize_result(
            status="disabled",
            ai_score=0.0,
            real_score=0.0,
            raw_score=0.0,
            input_meta=input_meta,
            latency_ms=evidence.get("latency_ms") or 0.0,
            error=DetectorError(type=None, message=None, recoverable=True),
            raw_output=evidence,
            notes=["open_source_adapter_disabled", "OPEN_SOURCE_DETECTOR_ENABLED is false"],
        )
    if not available or evidence.get("error"):
        return adapter.normalize_result(
            status="error",
            ai_score=0.0,
            real_score=0.0,
            raw_score=0.0,
            input_meta=input_meta,
            latency_ms=evidence.get("latency_ms") or 0.0,
            error=DetectorError(type="OpenSourceAdapterError", message=evidence.get("error") or "Detector unavailable.", recoverable=True),
            raw_output=evidence,
            notes=["open_source_adapter_error"],
        )
    return adapter.normalize_raw_output(
        {
            "status": "ok",
            "ai_score": evidence.get("score", evidence.get("open_source_score")),
            "raw_score": evidence.get("score", evidence.get("open_source_score")),
            "confidence": evidence.get("confidence"),
            "predicted_label": evidence.get("label"),
            "notes": ["open_source_adapter_normalized"],
            **evidence,
        },
        input_meta=input_meta,
        latency_ms=float(evidence.get("latency_ms") or 0.0),
    )
