from __future__ import annotations

from pathlib import Path
from typing import Any


def analyze_forensic(image_path: str) -> dict[str, Any]:
    try:
        from PIL import Image
    except Exception as exc:
        return {
            "checked": False,
            "format": None,
            "width": None,
            "height": None,
            "mode": None,
            "file_size_kb": None,
            "is_jpeg": False,
            "risk_score": 70,
            "signals": ["Image forensic check failed because Pillow is not available."],
            "error": f"Pillow import failed: {exc}",
        }

    try:
        path = Path(image_path)
        file_size_kb = round(path.stat().st_size / 1024, 2)

        with Image.open(path) as image:
            image_format = image.format
            width, height = image.size
            mode = image.mode

        is_jpeg = (image_format or "").upper() in {"JPEG", "JPG"}
        risk_score = 30 if is_jpeg else 25
        signals = ["Image opened successfully with Pillow."]
        if is_jpeg:
            signals.append("Image is JPEG.")
        else:
            signals.append(f"Image format is {image_format or 'unknown'}, not JPEG.")

        pixel_count = width * height
        if file_size_kb < 100 and pixel_count >= 2_000_000:
            risk_score += 20
            signals.append("File size is very small relative to a large resolution.")

        return {
            "checked": True,
            "format": image_format,
            "width": width,
            "height": height,
            "mode": mode,
            "file_size_kb": file_size_kb,
            "is_jpeg": is_jpeg,
            "risk_score": min(risk_score, 100),
            "signals": signals,
            "error": None,
        }
    except Exception as exc:
        return {
            "checked": False,
            "format": None,
            "width": None,
            "height": None,
            "mode": None,
            "file_size_kb": None,
            "is_jpeg": False,
            "risk_score": 70,
            "signals": ["Image could not be opened or inspected."],
            "error": str(exc),
        }
