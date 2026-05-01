from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features import estimate_jpeg_quality  # noqa: E402


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
REPORTS_DIR = PROJECT_ROOT / "reports"
OUTPUT_CSV = REPORTS_DIR / "day10_dataset_format_audit.csv"
OUTPUT_MD = REPORTS_DIR / "day10_dataset_format_audit.md"
CSV_FIELDS = [
    "relative_path",
    "true_label",
    "file_name",
    "extension",
    "detected_format",
    "width",
    "height",
    "aspect_ratio",
    "megapixels",
    "file_size_kb",
    "color_mode",
    "has_alpha",
    "is_jpeg",
    "is_png",
    "exif_exists",
    "estimated_jpeg_quality",
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


def has_alpha_channel(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def audit_image(path: Path, true_label: str) -> dict[str, Any]:
    try:
        with Image.open(path) as opened:
            opened = ImageOps.exif_transpose(opened)
            detected_format = opened.format or path.suffix.lstrip(".").upper()
            width, height = opened.size
            color_mode = opened.mode
            alpha = has_alpha_channel(opened)
            exif_exists = bool(opened.getexif())
            jpeg_quality = estimate_jpeg_quality(opened)
    except UnidentifiedImageError as exc:
        raise ValueError(f"Unreadable image: {path}") from exc

    detected_upper = str(detected_format or "").upper()
    file_size_kb = path.stat().st_size / 1024
    return {
        "relative_path": display_path(path),
        "true_label": true_label,
        "file_name": path.name,
        "extension": path.suffix.lower(),
        "detected_format": detected_format,
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 6) if height else "",
        "megapixels": round((width * height) / 1_000_000, 6),
        "file_size_kb": round(file_size_kb, 3),
        "color_mode": color_mode,
        "has_alpha": alpha,
        "is_jpeg": detected_upper in {"JPEG", "JPG"} or path.suffix.lower() in {".jpg", ".jpeg"},
        "is_png": detected_upper == "PNG" or path.suffix.lower() == ".png",
        "exif_exists": exif_exists,
        "estimated_jpeg_quality": "" if jpeg_quality is None else round(float(jpeg_quality), 2),
    }


def write_csv(rows: list[dict[str, Any]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["true_label"])].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for label, items in groups.items():
        formats = Counter(str(row["detected_format"]).upper() for row in items)
        extensions = Counter(str(row["extension"]).lower() for row in items)
        summary[label] = {
            "count": len(items),
            "formats": formats,
            "extensions": extensions,
            "avg_width": round(mean(float(row["width"]) for row in items), 2),
            "avg_height": round(mean(float(row["height"]) for row in items), 2),
            "avg_megapixels": round(mean(float(row["megapixels"]) for row in items), 4),
            "avg_file_size_kb": round(mean(float(row["file_size_kb"]) for row in items), 2),
            "png_count": sum(1 for row in items if row["is_png"]),
            "jpeg_count": sum(1 for row in items if row["is_jpeg"]),
        }
    return summary


def ratio(count: int, total: int) -> float:
    return count / total if total else 0.0


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in sorted(counter.items()))


def write_markdown(rows: list[dict[str, Any]], output_md: Path) -> None:
    summary = summarize(rows)
    ai = summary.get("ai", {})
    real = summary.get("real", {})
    ai_count = int(ai.get("count", 0))
    real_count = int(real.get("count", 0))
    ai_png_ratio = ratio(int(ai.get("png_count", 0)), ai_count)
    real_jpeg_ratio = ratio(int(real.get("jpeg_count", 0)), real_count)
    format_bias = ai_png_ratio >= 0.70 and real_jpeg_ratio >= 0.70

    ai_mp = float(ai.get("avg_megapixels", 0.0))
    real_mp = float(real.get("avg_megapixels", 0.0))
    ai_size = float(ai.get("avg_file_size_kb", 0.0))
    real_size = float(real.get("avg_file_size_kb", 0.0))
    size_bias = max(ai_size, real_size) / max(min(ai_size, real_size), 1.0) >= 1.5
    dimension_bias = max(ai_mp, real_mp) / max(min(ai_mp, real_mp), 0.001) >= 1.5

    lines = [
        "# Day10 Dataset Format Audit",
        "",
        "## Scope",
        "",
        "- Scanned `data/test_images/ai` and `data/test_images/real`.",
        "- This script only audits metadata and does not modify source images.",
        "",
        "## Format Counts",
        "",
        "| true_label | count | detected formats | extensions | PNG | JPEG |",
        "| --- | ---: | --- | --- | ---: | ---: |",
    ]
    for label in ("ai", "real"):
        item = summary.get(label, {})
        lines.append(
            f"| {label} | {item.get('count', 0)} | {format_counter(item.get('formats', Counter()))} | "
            f"{format_counter(item.get('extensions', Counter()))} | {item.get('png_count', 0)} | {item.get('jpeg_count', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Average Size",
            "",
            "| true_label | avg width | avg height | avg megapixels | avg file size KB |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in ("ai", "real"):
        item = summary.get(label, {})
        lines.append(
            f"| {label} | {item.get('avg_width', 0)} | {item.get('avg_height', 0)} | "
            f"{item.get('avg_megapixels', 0)} | {item.get('avg_file_size_kb', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Bias Checks",
            "",
            f"- AI PNG ratio: {ai_png_ratio:.2%}",
            f"- Real JPEG ratio: {real_jpeg_ratio:.2%}",
            f"- AI-mostly-PNG vs Real-mostly-JPEG bias: {'yes' if format_bias else 'no'}",
            f"- Dimension bias flag: {'yes' if dimension_bias else 'no'}",
            f"- File-size bias flag: {'yes' if size_bias else 'no'}",
            "",
            "## Conclusion",
            "",
        ]
    )
    if format_bias:
        lines.append(
            "- The current test set has an obvious format confound: AI samples are mostly PNG while Real samples are mostly JPEG."
        )
        lines.append(
            "- Because the format distribution is not balanced, this original test set cannot be used alone for a final accuracy claim."
        )
    else:
        lines.append("- No dominant AI-PNG vs Real-JPEG split was detected in this audit.")
    if dimension_bias or size_bias:
        lines.append(
            "- Resolution or file-size differences are large enough to treat current metrics as potentially source-biased."
        )
    else:
        lines.append("- Resolution and file-size averages are not the main bias signal in this audit.")
    lines.extend(
        [
            "- Day10 should re-evaluate with controlled PNG/JPEG versions before drawing detector-performance conclusions.",
            "",
            "## Output Files",
            "",
            f"- `{display_path(OUTPUT_CSV)}`",
            f"- `{display_path(OUTPUT_MD)}`",
            "",
            f"_Generated at {datetime.now().astimezone().isoformat(timespec='seconds')}._",
            "",
        ]
    )
    output_md.write_text("\n".join(lines), encoding="utf-8")


def run() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in ("ai", "real"):
        for path in image_files(TEST_ROOT / label):
            rows.append(audit_image(path, label))
    write_csv(rows, OUTPUT_CSV)
    write_markdown(rows, OUTPUT_MD)
    return rows


def main() -> int:
    rows = run()
    print(f"Audited images: {len(rows)}")
    print(f"CSV: {display_path(OUTPUT_CSV)}")
    print(f"Report: {display_path(OUTPUT_MD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
