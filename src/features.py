from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageChops, ImageFilter, ImageOps, ImageStat


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
EXCLUDED_SCAN_DIRS = {"reports"}
MAX_ANALYSIS_SIZE = 256


@dataclass(frozen=True)
class ImageScanResult:
    input_path: Path
    image_paths: list[Path]
    skipped_files: list[Path]


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def scan_supported_images(input_root: Path) -> ImageScanResult:
    """Scan a file or directory and count unsupported files separately."""
    if not input_root.exists():
        raise FileNotFoundError("Input path does not exist")

    if input_root.is_file():
        return ImageScanResult(
            input_path=input_root,
            image_paths=[input_root] if is_supported_image(input_root) else [],
            skipped_files=[] if is_supported_image(input_root) else [input_root],
        )

    image_paths: list[Path] = []
    skipped_files: list[Path] = []
    for path in sorted(input_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.lower() in EXCLUDED_SCAN_DIRS for part in path.relative_to(input_root).parts[:-1]):
            skipped_files.append(path)
            continue
        if is_supported_image(path):
            image_paths.append(path)
        else:
            skipped_files.append(path)

    return ImageScanResult(input_path=input_root, image_paths=image_paths, skipped_files=skipped_files)


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None or math.isnan(value) or math.isinf(value):
        return None
    return round(float(value), digits)


def _analysis_gray(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    gray.thumbnail((MAX_ANALYSIS_SIZE, MAX_ANALYSIS_SIZE))
    return gray.copy()


def _pixel_values(image: Image.Image) -> list[int]:
    get_flattened_data = getattr(image, "get_flattened_data", None)
    if callable(get_flattened_data):
        return list(get_flattened_data())
    return list(image.getdata())


def _exif_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip("\x00 ")
    return str(value).strip()


def extract_metadata(opened: Image.Image) -> dict[str, Any]:
    exif = opened.getexif()
    tag_values: dict[str, Any] = {}
    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        tag_values[tag_name] = value

    time_fields = [
        _exif_text(tag_values.get("DateTime")),
        _exif_text(tag_values.get("DateTimeOriginal")),
        _exif_text(tag_values.get("DateTimeDigitized")),
    ]
    time_fields = [value for value in time_fields if value]

    return {
        "has_exif": bool(exif),
        "camera_make": _exif_text(tag_values.get("Make")),
        "camera_model": _exif_text(tag_values.get("Model")),
        "software": _exif_text(tag_values.get("Software")),
        "datetime": time_fields[0] if time_fields else "",
        "metadata_time_fields": time_fields,
    }


def calculate_laplacian_variance(gray: Image.Image) -> float:
    width, height = gray.size
    if width < 3 or height < 3:
        return 0.0

    pixels = _pixel_values(gray)
    values: list[float] = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = pixels[row + x]
            laplacian = (
                pixels[row + x - 1]
                + pixels[row + x + 1]
                + pixels[row - width + x]
                + pixels[row + width + x]
                - (4 * center)
            )
            values.append(float(laplacian))

    mean_value = sum(values) / len(values)
    return sum((value - mean_value) ** 2 for value in values) / len(values)


def calculate_edge_density(gray: Image.Image, threshold: float = 24.0) -> float:
    width, height = gray.size
    if width < 2 or height < 2:
        return 0.0

    pixels = _pixel_values(gray)
    edge_count = 0
    total = 0
    for y in range(height - 1):
        row = y * width
        next_row = row + width
        for x in range(width - 1):
            horizontal = abs(pixels[row + x] - pixels[row + x + 1])
            vertical = abs(pixels[row + x] - pixels[next_row + x])
            if max(horizontal, vertical) >= threshold:
                edge_count += 1
            total += 1
    return edge_count / total if total else 0.0


def calculate_color_entropy(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    histogram = rgb.histogram()
    total_pixels = rgb.size[0] * rgb.size[1]
    if total_pixels == 0:
        return 0.0

    channel_entropies: list[float] = []
    for channel_index in range(3):
        channel_hist = histogram[channel_index * 256 : (channel_index + 1) * 256]
        entropy = 0.0
        for count in channel_hist:
            if count == 0:
                continue
            probability = count / total_pixels
            entropy -= probability * math.log2(probability)
        channel_entropies.append(entropy)
    return sum(channel_entropies) / len(channel_entropies)


def calculate_local_variance_score(gray: Image.Image) -> float:
    blurred = gray.filter(ImageFilter.BoxBlur(1))
    residual = ImageChops.difference(gray, blurred)
    return float(ImageStat.Stat(residual).var[0])


def calculate_blockiness_score(gray: Image.Image) -> float:
    width, height = gray.size
    if width < 16 or height < 16:
        return 0.0

    pixels = _pixel_values(gray)
    boundary_diffs: list[int] = []
    interior_diffs: list[int] = []

    for y in range(height):
        row = y * width
        for x in range(1, width):
            diff = abs(pixels[row + x] - pixels[row + x - 1])
            if x % 8 == 0:
                boundary_diffs.append(diff)
            else:
                interior_diffs.append(diff)

    for y in range(1, height):
        row = y * width
        previous_row = row - width
        for x in range(width):
            diff = abs(pixels[row + x] - pixels[previous_row + x])
            if y % 8 == 0:
                boundary_diffs.append(diff)
            else:
                interior_diffs.append(diff)

    if not boundary_diffs or not interior_diffs:
        return 0.0
    boundary_mean = sum(boundary_diffs) / len(boundary_diffs)
    interior_mean = sum(interior_diffs) / len(interior_diffs)
    return max(0.0, boundary_mean - interior_mean)


def estimate_jpeg_quality(opened: Image.Image) -> float | None:
    quantization = getattr(opened, "quantization", None)
    if not quantization:
        return None

    values: list[int] = []
    for table in quantization.values():
        values.extend(int(value) for value in table if int(value) > 0)
    if not values:
        return None

    avg_quantization = sum(values) / len(values)
    estimate = 100.0 - ((avg_quantization - 1.0) * 1.35)
    return max(1.0, min(100.0, estimate))


def extract_image_features(image_path: str | Path) -> dict[str, Any]:
    path = Path(image_path)
    with Image.open(path) as opened:
        metadata = extract_metadata(opened)
        image_format = opened.format or path.suffix.lstrip(".").upper()
        width, height = opened.size
        file_size = path.stat().st_size if path.exists() else 0
        jpeg_quality = estimate_jpeg_quality(opened)
        image = ImageOps.exif_transpose(opened).convert("RGB")

    gray = _analysis_gray(image)
    rgb_stat = ImageStat.Stat(image)
    rgb_mean = rgb_stat.mean
    rgb_stddev = rgb_stat.stddev
    local_variance_score = calculate_local_variance_score(gray)

    return {
        "image_path": str(path),
        "file_name": path.name,
        "format": image_format,
        "width": width,
        "height": height,
        "aspect_ratio": _round(width / height if height else None),
        "file_size_bytes": file_size,
        **metadata,
        "sharpness_score": _round(calculate_laplacian_variance(gray)),
        "edge_density": _round(calculate_edge_density(gray)),
        "rgb_mean_r": _round(rgb_mean[0]),
        "rgb_mean_g": _round(rgb_mean[1]),
        "rgb_mean_b": _round(rgb_mean[2]),
        "rgb_std_r": _round(rgb_stddev[0]),
        "rgb_std_g": _round(rgb_stddev[1]),
        "rgb_std_b": _round(rgb_stddev[2]),
        "color_entropy": _round(calculate_color_entropy(image)),
        "noise_score": _round(local_variance_score),
        "local_variance_score": _round(local_variance_score),
        "jpeg_quality_estimate": _round(jpeg_quality, 2),
        "compression_artifact_score": _round(calculate_blockiness_score(gray)),
        "compression_artifact_method": "jpeg_quantization" if jpeg_quality is not None else "blockiness_fallback",
    }
