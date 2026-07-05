from __future__ import annotations

from pathlib import Path
from typing import Any


def _round_float(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def _error_result(image_path: str | Path, message: str) -> dict[str, Any]:
    return {
        "checked": False,
        "brightness_mean": None,
        "brightness_std": None,
        "color_channel_mean": None,
        "color_channel_std": None,
        "edge_density": None,
        "laplacian_variance": None,
        "noise_estimate": None,
        "error": message,
    }


def analyze_forensics(image_path: str | Path) -> dict[str, Any]:
    """Compute simple OpenCV/numpy forensic features for V0.1 baseline scoring."""
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        return _error_result(image_path, f"OpenCV/numpy import failed: {exc}")

    path = Path(image_path).expanduser()
    if not path.exists() or not path.is_file():
        return _error_result(path, "Image file does not exist or is not a file.")

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return _error_result(path, "OpenCV could not decode the image.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    median = cv2.medianBlur(gray, 3)
    noise = gray.astype("float32") - median.astype("float32")

    channel_mean_bgr = image.mean(axis=(0, 1))
    channel_std_bgr = image.std(axis=(0, 1))

    return {
        "checked": True,
        "brightness_mean": _round_float(gray.mean()),
        "brightness_std": _round_float(gray.std()),
        "color_channel_mean": {
            "red": _round_float(channel_mean_bgr[2]),
            "green": _round_float(channel_mean_bgr[1]),
            "blue": _round_float(channel_mean_bgr[0]),
        },
        "color_channel_std": {
            "red": _round_float(channel_std_bgr[2]),
            "green": _round_float(channel_std_bgr[1]),
            "blue": _round_float(channel_std_bgr[0]),
        },
        "edge_density": _round_float((edges > 0).mean()),
        "laplacian_variance": _round_float(laplacian.var()),
        "noise_estimate": _round_float(np.std(noise)),
        "error": None,
    }

