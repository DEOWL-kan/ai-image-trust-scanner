from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


AI_LABEL_MARKERS = ("fake", "ai", "generated", "synthetic", "artificial")
REAL_LABEL_MARKERS = ("real", "human", "authentic", "natural")


def detector_runtime_mode() -> str:
    mode = str(os.getenv("DETECTOR_RUNTIME_MODE", "stub")).strip().lower()
    if mode in {"stub", "local_hf", "disabled"}:
        return mode
    return "stub"


def bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def allow_cold_model_load() -> bool:
    return bool_env("DETECTOR_ALLOW_COLD_MODEL_LOAD", False)


def _is_ai_label(label: Any) -> bool:
    text = str(label or "").strip().lower()
    return any(marker in text for marker in AI_LABEL_MARKERS)


def _is_real_label(label: Any) -> bool:
    text = str(label or "").strip().lower()
    return any(marker in text for marker in REAL_LABEL_MARKERS)


class HFImageClassificationRuntime:
    def __init__(
        self,
        *,
        detector_id: str,
        model_id: str,
        threshold: float,
        device: str | None = None,
        local_files_only: bool | None = None,
        peft_adapter_path: str | None = None,
    ) -> None:
        self.detector_id = detector_id
        self.model_id = os.getenv(f"{detector_id.upper()}_MODEL_ID") or model_id
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.device = (device or os.getenv(f"{detector_id.upper()}_DEVICE") or os.getenv("DETECTOR_DEVICE") or "auto").strip().lower()
        self.local_files_only = bool_env(f"{detector_id.upper()}_LOCAL_FILES_ONLY", bool_env("HF_LOCAL_FILES_ONLY", True)) if local_files_only is None else bool(local_files_only)
        # Opt-in LoRA/PEFT adapter (P1-c fine-tune adoption). Default OFF: when
        # unset the base HF weights load unchanged. An env override
        # `{ID}_PEFT_ADAPTER` lets evaluation toggle the adapter without editing
        # config. A relative path is resolved against the project root.
        self.peft_adapter_path = (os.getenv(f"{detector_id.upper()}_PEFT_ADAPTER") or peft_adapter_path or "").strip()
        self._peft_loaded = False
        self._processor: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._resolved_device = "cpu"
        self._load_error: str | None = None
        self._load_attempted = False

    def config_summary(self) -> dict[str, Any]:
        cache_home = os.getenv("HF_HOME") or os.getenv("TRANSFORMERS_CACHE")
        return {
            "detector_id": self.detector_id,
            "model_id": self.model_id,
            "device": self.device,
            "resolved_device": self._resolved_device,
            "local_files_only": self.local_files_only,
            "hf_home": os.getenv("HF_HOME"),
            "transformers_cache": os.getenv("TRANSFORMERS_CACHE"),
            "cache_dir": cache_home,
            "cache_dir_exists": bool(cache_home and Path(cache_home).exists()),
            "load_attempted": self._load_attempted,
            "model_loaded": self._model is not None and self._processor is not None,
            "load_error": self._load_error,
            "peft_adapter_path": self.peft_adapter_path or None,
            "peft_loaded": self._peft_loaded,
        }

    def predict(self, image_path_or_pil: str | Path | Any) -> dict[str, Any]:
        started = time.perf_counter()
        if self._model is None or self._processor is None:
            if not allow_cold_model_load():
                return {
                    "status": "error",
                    "error_type": "PrimaryDetectorUnavailable",
                    "error": "HF model is not loaded; cold request-time model loading is disabled.",
                    "error_message": "HF model is not loaded; cold request-time model loading is disabled.",
                    "recoverable": True,
                    "notes": ["hf_runtime_cold_load_disabled"],
                    "model_loaded": False,
                    "raw_output_summary": self.config_summary(),
                }
        self._load_model()
        if self._load_error:
            return {
                "status": "error",
                "error_type": "PrimaryDetectorUnavailable",
                "error": self._load_error,
                "error_message": self._load_error,
                "recoverable": True,
                "notes": ["hf_runtime_load_failed"],
                "model_loaded": False,
                "raw_output_summary": self.config_summary(),
            }
        try:
            image = self._load_image(image_path_or_pil)
            preprocess = self._preprocess_summary(image)
            inputs = self._processor(images=image, return_tensors="pt")
            pixel_values = inputs.get("pixel_values")
            if pixel_values is not None:
                preprocess["tensor_shape"] = list(pixel_values.shape)
                if len(pixel_values.shape) >= 4:
                    preprocess["resized_width"] = int(pixel_values.shape[-1])
                    preprocess["resized_height"] = int(pixel_values.shape[-2])
            inputs = {key: value.to(self._resolved_device) for key, value in inputs.items()}
            with self._torch.no_grad():
                output = self._model(**inputs)
                logits = output.logits[0].detach().cpu().tolist()
                probs = self._torch.nn.functional.softmax(output.logits, dim=-1)[0].detach().cpu().tolist()
            labels = self._labels_from_probs(probs)
            return self._map_labels(labels, started, logits=logits, probs=probs, preprocess=preprocess)
        except Exception as exc:
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "error_message": str(exc),
                "recoverable": True,
                "notes": ["hf_runtime_predict_failed"],
                "model_loaded": bool(self._model is not None and self._processor is not None),
                "raw_output_summary": self.config_summary(),
            }

    def predict_many(self, image_path_or_pils: list[str | Path | Any]) -> list[dict[str, Any]]:
        items = list(image_path_or_pils)
        if not items:
            return []
        started = time.perf_counter()
        if self._model is None or self._processor is None:
            if not allow_cold_model_load():
                return [
                    {
                        "status": "error",
                        "error_type": "PrimaryDetectorUnavailable",
                        "error": "HF model is not loaded; cold request-time model loading is disabled.",
                        "error_message": "HF model is not loaded; cold request-time model loading is disabled.",
                        "recoverable": True,
                        "notes": ["hf_runtime_cold_load_disabled"],
                        "model_loaded": False,
                        "raw_output_summary": self.config_summary(),
                    }
                    for _ in items
                ]
        self._load_model()
        if self._load_error:
            return [
                {
                    "status": "error",
                    "error_type": "PrimaryDetectorUnavailable",
                    "error": self._load_error,
                    "error_message": self._load_error,
                    "recoverable": True,
                    "notes": ["hf_runtime_load_failed"],
                    "model_loaded": False,
                    "raw_output_summary": self.config_summary(),
                }
                for _ in items
            ]
        try:
            images = [self._load_image(item) for item in items]
            inputs = self._processor(images=images, return_tensors="pt")
            pixel_values = inputs.get("pixel_values")
            batch_tensor_shape = list(pixel_values.shape) if pixel_values is not None else None
            inputs = {key: value.to(self._resolved_device) for key, value in inputs.items()}
            with self._torch.no_grad():
                output = self._model(**inputs)
                logits_batch = output.logits.detach().cpu().tolist()
                probs_batch = self._torch.nn.functional.softmax(output.logits, dim=-1).detach().cpu().tolist()
            outputs: list[dict[str, Any]] = []
            batch_size = len(images)
            for index, (image, logits, probs) in enumerate(zip(images, logits_batch, probs_batch)):
                labels = self._labels_from_probs([float(value) for value in probs])
                preprocess = self._preprocess_summary(image)
                if batch_tensor_shape is not None:
                    preprocess["tensor_shape"] = batch_tensor_shape
                    preprocess["batch_size"] = batch_size
                    preprocess["batch_index"] = index
                    if len(batch_tensor_shape) >= 4:
                        preprocess["resized_width"] = int(batch_tensor_shape[-1])
                        preprocess["resized_height"] = int(batch_tensor_shape[-2])
                mapped = self._map_labels(
                    labels,
                    started,
                    logits=[float(value) for value in logits],
                    probs=[float(value) for value in probs],
                    preprocess=preprocess,
                )
                summary = mapped.get("raw_output_summary") if isinstance(mapped.get("raw_output_summary"), dict) else {}
                summary["batch_size"] = batch_size
                summary["batch_index"] = index
                mapped["raw_output_summary"] = summary
                notes = mapped.get("notes") if isinstance(mapped.get("notes"), list) else []
                mapped["notes"] = [*notes, "hf_runtime_batch_predict"]
                outputs.append(mapped)
            return outputs
        except Exception as exc:
            return [
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "error_message": str(exc),
                    "recoverable": True,
                    "notes": ["hf_runtime_batch_predict_failed"],
                    "model_loaded": bool(self._model is not None and self._processor is not None),
                    "raw_output_summary": self.config_summary(),
                }
                for _ in items
            ]

    def _load_model(self) -> None:
        self._load_attempted = True
        if self._model is not None and self._processor is not None:
            return
        if self._load_error:
            return
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            self._torch = torch
            self._resolved_device = self._select_device(torch)
            self._processor = AutoImageProcessor.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model = AutoModelForImageClassification.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            if self.peft_adapter_path:
                from peft import PeftModel

                adapter_path = Path(self.peft_adapter_path)
                if not adapter_path.is_absolute():
                    adapter_path = Path(__file__).resolve().parents[2] / adapter_path
                if not adapter_path.exists():
                    raise FileNotFoundError(f"PEFT adapter path does not exist: {adapter_path}")
                self._model = PeftModel.from_pretrained(self._model, str(adapter_path))
                self._peft_loaded = True
            self._model.to(self._resolved_device)
            self._model.eval()
        except Exception as exc:
            cache_hint = "Set HF_HOME or TRANSFORMERS_CACHE to a cache outside the repo and pre-download the model."
            self._load_error = f"{type(exc).__name__}: {exc}. {cache_hint}"

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

    def _preprocess_summary(self, image: Any) -> dict[str, Any]:
        image_mean = getattr(self._processor, "image_mean", None)
        image_std = getattr(self._processor, "image_std", None)
        size = getattr(self._processor, "size", None)
        return {
            "image_mode": getattr(image, "mode", "unknown"),
            "original_width": int(getattr(image, "width", 0) or 0),
            "original_height": int(getattr(image, "height", 0) or 0),
            "processor_size": size,
            "normalization_mean": image_mean,
            "normalization_std": image_std,
        }

    def _labels_from_probs(self, probs: list[float]) -> list[dict[str, Any]]:
        id2label = getattr(getattr(self._model, "config", None), "id2label", None) or {}
        labels = [
            {
                "index": index,
                "label": str(id2label.get(index, f"LABEL_{index}")),
                "score": round(float(score), 6),
                "score_full_precision": float(score),
            }
            for index, score in enumerate(probs)
        ]
        labels.sort(key=lambda item: float(item["score_full_precision"]), reverse=True)
        return labels

    def _map_labels(
        self,
        labels: list[dict[str, Any]],
        started: float,
        *,
        logits: list[float],
        probs: list[float],
        preprocess: dict[str, Any],
    ) -> dict[str, Any]:
        id2label = getattr(getattr(self._model, "config", None), "id2label", None) or {}
        ai_indexes = [index for index, label in id2label.items() if _is_ai_label(label)]
        real_indexes = [index for index, label in id2label.items() if _is_real_label(label)]
        ai_score_full = sum(float(probs[index]) for index in ai_indexes if index < len(probs))
        real_score_full = sum(float(probs[index]) for index in real_indexes if index < len(probs))
        ai_score = sum(float(item["score_full_precision"]) for item in labels if _is_ai_label(item.get("label")))
        real_score = sum(float(item["score_full_precision"]) for item in labels if _is_real_label(item.get("label")))
        if ai_score <= 0.0 and real_score <= 0.0:
            return {
                "status": "error",
                "error_type": "LabelMappingError",
                "error": "Unable to map model labels to ai/real classes.",
                "error_message": "Unable to map model labels to ai/real classes.",
                "recoverable": True,
                "notes": ["hf_runtime_label_mapping_failed"],
                "raw_labels": labels[:5],
                "model_loaded": True,
                "raw_output_summary": self.config_summary(),
            }
        score = max(0.0, min(1.0, ai_score))
        label = "ai" if score >= self.threshold else "real"
        confidence = score if label == "ai" else max(0.0, min(1.0, real_score or (1.0 - score)))
        predicted_index = int(max(range(len(probs)), key=lambda index: probs[index])) if probs else -1
        ai_logit = max((float(logits[index]) for index in ai_indexes if index < len(logits)), default=None)
        real_logit = max((float(logits[index]) for index in real_indexes if index < len(logits)), default=None)
        logit_margin = None
        if ai_logit is not None and real_logit is not None:
            logit_margin = ai_logit - real_logit
        raw_output_summary = self.config_summary()
        raw_output_summary.update(
            {
                "raw_logits": [float(value) for value in logits],
                "probabilities_raw": [float(value) for value in probs],
                "probability_raw": ai_score_full,
                "ai_score_full_precision": ai_score_full,
                "ai_score_rounded": round(score, 6),
                "real_score_full_precision": real_score_full,
                "logit_margin": logit_margin,
                "ai_logit": ai_logit,
                "real_logit": real_logit,
                "predicted_class_index": predicted_index,
                "class_mapping": {str(key): str(value) for key, value in id2label.items()},
                "ai_class_indexes": ai_indexes,
                "real_class_indexes": real_indexes,
                "preprocessing": preprocess,
            }
        )
        return {
            "status": "ok",
            "ai_score": round(score, 6),
            "real_score": round(max(0.0, min(1.0, real_score or (1.0 - score))), 6),
            "raw_score": round(score, 6),
            "predicted_label": label,
            "confidence": round(float(confidence), 6),
            "raw_labels": labels[:5],
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "model_loaded": True,
            "raw_output_summary": raw_output_summary,
            "notes": ["hf_runtime_local_hf"],
        }
