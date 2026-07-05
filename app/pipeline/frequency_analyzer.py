from __future__ import annotations

from pathlib import Path
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _error_result(image_path: str | Path, message: str) -> dict[str, Any]:
    return {
        "checked": False,
        "high_frequency_energy_ratio": None,
        "frequency_score": None,
        "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
        "error": message,
    }


def analyze_frequency(image_path: str | Path) -> dict[str, Any]:
    """Compute a basic FFT high-frequency energy ratio as a weak heuristic signal."""
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        return _error_result(image_path, f"OpenCV/numpy import failed: {exc}")

    path = Path(image_path).expanduser()
    if not path.exists() or not path.is_file():
        return _error_result(path, "Image file does not exist or is not a file.")

    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return _error_result(path, "OpenCV could not decode the image.")

    gray_float = gray.astype("float32") / 255.0
    spectrum = np.fft.fftshift(np.fft.fft2(gray_float))
    magnitude = np.abs(spectrum)

    height, width = gray.shape
    y, x = np.ogrid[:height, :width]
    center_y, center_x = height / 2.0, width / 2.0
    radius = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    high_frequency_mask = radius > (min(height, width) * 0.25)

    total_energy = float(magnitude.sum())
    high_frequency_energy = float(magnitude[high_frequency_mask].sum())
    ratio = high_frequency_energy / total_energy if total_energy > 0 else 0.0

    return {
        "checked": True,
        "high_frequency_energy_ratio": round(float(ratio), 6),
        "frequency_score": round(_clamp(float(ratio)), 6),
        "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
        "error": None,
    }
