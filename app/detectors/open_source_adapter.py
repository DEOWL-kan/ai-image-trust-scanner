from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL_ID = "dima806/ai_vs_real_image_detection"
AI_LABEL_MARKERS = ("fake", "ai", "generated", "synthetic", "artificial")
REAL_LABEL_MARKERS = ("real", "human", "authentic", "natural")


@dataclass
class OpenSourceDetectionResult:
    enabled: bool
    available: bool
    model_id: str | None
    open_source_score: float | None
    open_source_label: str
    open_source_confidence: float | None
    open_source_threshold: float
    open_source_latency_ms: float | None
    open_source_error: str | None
    raw_labels: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_enabled() -> bool:
    return str(os.getenv("OPEN_SOURCE_DETECTOR_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_threshold() -> float:
    raw = os.getenv("OPEN_SOURCE_DETECTOR_THRESHOLD", "0.5")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.5
    return max(0.0, min(1.0, value))


def _is_ai_label(label: Any) -> bool:
    text = str(label or "").strip().lower()
    return any(marker in text for marker in AI_LABEL_MARKERS)


def _is_real_label(label: Any) -> bool:
    text = str(label or "").strip().lower()
    return any(marker in text for marker in REAL_LABEL_MARKERS)


class OpenSourceDetectorAdapter:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        model_id: str | None = None,
        device: str | None = None,
        threshold: float | None = None,
    ) -> None:
        self.enabled = _env_enabled() if enabled is None else bool(enabled)
        self.model_id = model_id or os.getenv("OPEN_SOURCE_DETECTOR_MODEL_ID") or DEFAULT_MODEL_ID
        self.device = (device or os.getenv("OPEN_SOURCE_DETECTOR_DEVICE") or "auto").strip().lower()
        self.threshold = _env_threshold() if threshold is None else max(0.0, min(1.0, float(threshold)))
        self._processor: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._resolved_device = "cpu"
        self._load_error: str | None = None

    def is_enabled(self) -> bool:
        return self.enabled

    def predict(self, image_path_or_pil: str | Path | Any) -> OpenSourceDetectionResult:
        started = time.perf_counter()
        if not self.is_enabled():
            return self._result(
                enabled=False,
                available=False,
                label="unknown",
                latency_ms=0.0,
            )

        try:
            self._load_model()
            if self._load_error:
                return self._result(
                    enabled=True,
                    available=False,
                    label="error",
                    error=self._load_error,
                    latency_ms=self._elapsed_ms(started),
                )

            image = self._load_image(image_path_or_pil)
            inputs = self._processor(images=image, return_tensors="pt")
            inputs = {key: value.to(self._resolved_device) for key, value in inputs.items()}
            with self._torch.no_grad():
                output = self._model(**inputs)
                probs = self._torch.nn.functional.softmax(output.logits, dim=-1)[0].detach().cpu().tolist()

            id2label = getattr(getattr(self._model, "config", None), "id2label", None) or {}
            labels = [
                {
                    "label": str(id2label.get(index, f"LABEL_{index}")),
                    "score": round(float(score), 6),
                }
                for index, score in enumerate(probs)
            ]
            labels.sort(key=lambda item: float(item["score"]), reverse=True)
            return self._map_labels(labels, started)
        except Exception as exc:
            return self._result(
                enabled=True,
                available=False,
                label="error",
                error=str(exc),
                latency_ms=self._elapsed_ms(started),
            )

    def _load_model(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        if self._load_error:
            return
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            self._torch = torch
            self._resolved_device = self._select_device(torch)
            self._processor = AutoImageProcessor.from_pretrained(self.model_id)
            self._model = AutoModelForImageClassification.from_pretrained(self.model_id)
            self._model.to(self._resolved_device)
            self._model.eval()
        except Exception as exc:
            self._load_error = str(exc)

    def _select_device(self, torch: Any) -> str:
        if self.device != "auto":
            return self.device
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    def _load_image(self, image_path_or_pil: str | Path | Any) -> Any:
        if hasattr(image_path_or_pil, "convert"):
            return image_path_or_pil.convert("RGB")
        from PIL import Image

        with Image.open(image_path_or_pil) as image:
            return image.convert("RGB")

    def _map_labels(self, labels: list[dict[str, Any]], started: float) -> OpenSourceDetectionResult:
        ai_score = sum(float(item["score"]) for item in labels if _is_ai_label(item.get("label")))
        real_score = sum(float(item["score"]) for item in labels if _is_real_label(item.get("label")))
        raw_labels = labels[:5]
        if ai_score <= 0.0 and real_score <= 0.0:
            return self._result(
                enabled=True,
                available=True,
                label="unknown",
                error="Unable to map model labels to ai/real classes.",
                raw_labels=raw_labels,
                latency_ms=self._elapsed_ms(started),
            )

        open_source_score = max(0.0, min(1.0, ai_score))
        label = "ai" if open_source_score >= self.threshold else "real"
        confidence = open_source_score if label == "ai" else max(0.0, min(1.0, real_score or (1.0 - open_source_score)))
        return self._result(
            enabled=True,
            available=True,
            score=round(open_source_score, 6),
            label=label,
            confidence=round(float(confidence), 6),
            raw_labels=raw_labels,
            latency_ms=self._elapsed_ms(started),
        )

    def _result(
        self,
        *,
        enabled: bool,
        available: bool,
        score: float | None = None,
        label: str,
        confidence: float | None = None,
        error: str | None = None,
        raw_labels: list[dict[str, Any]] | None = None,
        latency_ms: float | None = None,
    ) -> OpenSourceDetectionResult:
        return OpenSourceDetectionResult(
            enabled=enabled,
            available=available,
            model_id=self.model_id if enabled else None,
            open_source_score=score,
            open_source_label=label,
            open_source_confidence=confidence,
            open_source_threshold=self.threshold,
            open_source_latency_ms=latency_ms,
            open_source_error=error,
            raw_labels=raw_labels or [],
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000.0, 3)
