from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
CONTROL_ROOT = PROJECT_ROOT / "data" / "day10_format_control"
MAPPING_CSV = PROJECT_ROOT / "reports" / "day10_format_control_mapping.csv"
CSV_FIELDS = [
    "source_path",
    "true_label",
    "output_png_path",
    "output_jpeg_q95_path",
    "output_jpeg_q85_path",
    "original_format",
    "source_width",
    "source_height",
]


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def image_files(label_dir: Path) -> list[Path]:
    if not label_dir.exists():
        raise FileNotFoundError(f"Missing directory: {label_dir}")
    return sorted(
        path
        for path in label_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def to_safe_rgb(opened: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    transposed = ImageOps.exif_transpose(opened)
    if transposed.mode in {"RGBA", "LA"} or (
        transposed.mode == "P" and "transparency" in transposed.info
    ):
        rgba = transposed.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (*background, 255))
        canvas.alpha_composite(rgba)
        return canvas.convert("RGB")
    return transposed.convert("RGB")


def convert_one(source: Path, true_label: str) -> dict[str, Any]:
    with Image.open(source) as opened:
        original_format = opened.format or source.suffix.lstrip(".").upper()
        width, height = opened.size
        rgb = to_safe_rgb(opened)

    png_path = CONTROL_ROOT / true_label / "png" / f"{source.stem}__png.png"
    jpeg_q95_path = CONTROL_ROOT / true_label / "jpeg_q95" / f"{source.stem}__jpeg_q95.jpg"
    jpeg_q85_path = CONTROL_ROOT / true_label / "jpeg_q85" / f"{source.stem}__jpeg_q85.jpg"
    for path in (png_path, jpeg_q95_path, jpeg_q85_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    rgb.save(png_path, format="PNG")
    rgb.save(jpeg_q95_path, format="JPEG", quality=95, optimize=True)
    rgb.save(jpeg_q85_path, format="JPEG", quality=85, optimize=True)

    return {
        "source_path": display_path(source),
        "true_label": true_label,
        "output_png_path": display_path(png_path),
        "output_jpeg_q95_path": display_path(jpeg_q95_path),
        "output_jpeg_q85_path": display_path(jpeg_q85_path),
        "original_format": original_format,
        "source_width": width,
        "source_height": height,
    }


def write_mapping(rows: list[dict[str, Any]]) -> None:
    MAPPING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for true_label in ("ai", "real"):
        for source in image_files(TEST_ROOT / true_label):
            rows.append(convert_one(source, true_label))
    write_mapping(rows)
    return rows


def main() -> int:
    rows = run()
    print(f"Converted source images: {len(rows)}")
    print(f"Control root: {display_path(CONTROL_ROOT)}")
    print(f"Mapping CSV: {display_path(MAPPING_CSV)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
