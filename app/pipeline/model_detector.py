from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_with_model(image_path: str | Path) -> dict[str, Any]:
    """Placeholder for future CNN / ViT / DIRE / CLIP-based detectors."""
    return {
        "checked": True,
        "image_path": str(Path(image_path).expanduser()),
        "ai_probability": 0.5,
        "model_name": "v0.1-baseline-placeholder",
        "model_status": "placeholder",
        "note": (
            "No deep model is trained or loaded in V0.1. "
            "This neutral value is placeholder metadata and is not used as trained evidence."
        ),
        "error": None,
    }
