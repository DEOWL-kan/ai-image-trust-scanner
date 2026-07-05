from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _error_result(image_path: str | Path, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "image_path": str(image_path),
        "filename": Path(image_path).name,
        "format": None,
        "width": None,
        "height": None,
        "color_mode": None,
        "file_size_bytes": None,
        "file_size_kb": None,
        "error": message,
    }


def load_image(image_path: str | Path) -> dict[str, Any]:
    """Load basic image information without making any authenticity claim."""
    path = Path(image_path).expanduser()

    if not path.exists():
        return _error_result(path, "Image file does not exist.")
    if path.is_dir():
        supported_images = [
            item for item in path.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if supported_images:
            return _error_result(
                path,
                "Image path is a directory. Please pass a specific image file with --image.",
            )
        return _error_result(
            path,
            "Image path is an empty directory or contains no supported images. "
            "Put a jpg, jpeg, png, or webp file in data/test_images/ and pass that file path with --image.",
        )
    if not path.is_file():
        return _error_result(path, "Image path is not a regular file.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return _error_result(
            path,
            "Unsupported file type. Supported formats: jpg, jpeg, png, webp.",
        )

    try:
        file_size_bytes = path.stat().st_size
    except OSError as exc:
        return _error_result(path, f"Could not read file size: {exc}")

    if file_size_bytes <= 0:
        return _error_result(path, "Image file is empty.")

    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            image_format = image.format
            color_mode = image.mode
    except UnidentifiedImageError:
        return _error_result(path, "File exists but is not a readable image.")
    except Exception as exc:
        return _error_result(path, f"Image could not be opened: {exc}")

    return {
        "ok": True,
        "image_path": str(path.resolve()),
        "filename": path.name,
        "format": image_format,
        "width": int(width),
        "height": int(height),
        "color_mode": color_mode,
        "file_size_bytes": int(file_size_bytes),
        "file_size_kb": round(file_size_bytes / 1024, 2),
        "error": None,
    }
