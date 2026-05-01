from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
REPORTS_DIR = PROJECT_ROOT / "reports" / "day8"
INVENTORY_CSV = REPORTS_DIR / "day8_testset_inventory.csv"
SUMMARY_MD = REPORTS_DIR / "day8_testset_summary.md"
EXPECTED_PER_CLASS = 30
CSV_FIELDS = [
    "class_label",
    "filename",
    "path",
    "extension",
    "sha256",
    "file_size_kb",
    "width",
    "height",
    "is_duplicate",
    "duplicate_count",
]


@dataclass(frozen=True)
class InventoryItem:
    class_label: str
    path: Path
    extension: str
    sha256: str
    file_size_kb: float
    width: int | None
    height: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day8 test-set inventory checker.")
    parser.add_argument(
        "--ai-dir",
        type=Path,
        default=Path("data/test_images/ai"),
        help="AI test-image directory. Default: data/test_images/ai",
    )
    parser.add_argument(
        "--real-dir",
        type=Path,
        default=Path("data/test_images/real"),
        help="Real test-image directory. Default: data/test_images/real",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Day8 report directory. Default: reports/day8",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def is_hidden_or_system(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    attrs = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attrs & getattr(os, "FILE_ATTRIBUTE_HIDDEN", 0)) or bool(
        attrs & getattr(os, "FILE_ATTRIBUTE_SYSTEM", 0)
    )


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def image_files(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and not is_hidden_or_system(path)
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=natural_key,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def collect_items(ai_dir: Path, real_dir: Path) -> list[InventoryItem]:
    items: list[InventoryItem] = []
    for class_label, directory in (("ai", ai_dir), ("real", real_dir)):
        for path in image_files(directory):
            width, height = image_dimensions(path)
            items.append(
                InventoryItem(
                    class_label=class_label,
                    path=path,
                    extension=path.suffix.lower(),
                    sha256=sha256_file(path),
                    file_size_kb=round(path.stat().st_size / 1024, 2),
                    width=width,
                    height=height,
                )
            )
    return items


def duplicate_counts(items: list[InventoryItem]) -> dict[str, int]:
    counts = Counter(item.sha256 for item in items)
    return {sha256: count for sha256, count in counts.items() if count > 1}


def write_inventory(items: list[InventoryItem], output_csv: Path) -> None:
    duplicates = duplicate_counts(items)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "class_label": item.class_label,
                    "filename": item.path.name,
                    "path": display_path(item.path),
                    "extension": item.extension,
                    "sha256": item.sha256,
                    "file_size_kb": f"{item.file_size_kb:.2f}",
                    "width": "" if item.width is None else item.width,
                    "height": "" if item.height is None else item.height,
                    "is_duplicate": "yes" if item.sha256 in duplicates else "no",
                    "duplicate_count": duplicates.get(item.sha256, 1),
                }
            )


def format_distribution(items: list[InventoryItem]) -> list[str]:
    counts = Counter(item.extension for item in items)
    if not counts:
        return ["- No supported images found."]
    return [f"- `{extension}`: {count}" for extension, count in sorted(counts.items())]


def resolution_range(items: list[InventoryItem]) -> str:
    sizes = [(item.width, item.height) for item in items if item.width and item.height]
    if not sizes:
        return "N/A"
    widths = [width for width, _ in sizes if width is not None]
    heights = [height for _, height in sizes if height is not None]
    return f"{min(widths)}x{min(heights)} to {max(widths)}x{max(heights)}"


def duplicate_summary(items: list[InventoryItem]) -> list[str]:
    duplicates = duplicate_counts(items)
    if not duplicates:
        return ["- No duplicate sha256 values detected."]

    by_hash: dict[str, list[str]] = defaultdict(list)
    for item in items:
        if item.sha256 in duplicates:
            by_hash[item.sha256].append(display_path(item.path))

    lines = ["- Duplicate sha256 values detected:"]
    for sha256, paths in sorted(by_hash.items()):
        lines.append(f"- `{sha256}` appears {len(paths)} times: {', '.join(f'`{path}`' for path in paths)}")
    return lines


def write_summary(items: list[InventoryItem], output_md: Path) -> None:
    ai_count = sum(1 for item in items if item.class_label == "ai")
    real_count = sum(1 for item in items if item.class_label == "real")
    duplicates = duplicate_counts(items)
    meets_requirement = ai_count == EXPECTED_PER_CLASS and real_count == EXPECTED_PER_CLASS

    lines = [
        "# Day8 Test Set Summary",
        "",
        f"- AI image count: {ai_count}",
        f"- Real image count: {real_count}",
        f"- Total test set count: {len(items)}",
        "",
        "## Format Distribution",
        "",
        *format_distribution(items),
        "",
        "## Resolution Range",
        "",
        f"- {resolution_range(items)}",
        "",
        "## Duplicate Files",
        "",
        *duplicate_summary(items),
        "",
        "## Day8 Requirement Check",
        "",
        f"- AI images meet 30-image target: {'yes' if ai_count == EXPECTED_PER_CLASS else 'no'}",
        f"- Real images meet 30-image target: {'yes' if real_count == EXPECTED_PER_CLASS else 'no'}",
        f"- Overall Day8 test-set requirement met: {'yes' if meets_requirement else 'no'}",
        f"- Duplicate files present: {'yes' if duplicates else 'no'}",
        "",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines), encoding="utf-8")


def run(ai_dir: Path, real_dir: Path, output_dir: Path) -> list[InventoryItem]:
    ai_dir = resolve_path(ai_dir)
    real_dir = resolve_path(real_dir)
    output_dir = resolve_path(output_dir)
    items = collect_items(ai_dir, real_dir)
    write_inventory(items, output_dir / INVENTORY_CSV.name)
    write_summary(items, output_dir / SUMMARY_MD.name)
    return items


def main() -> int:
    args = parse_args()
    items = run(args.ai_dir, args.real_dir, args.output_dir)
    ai_count = sum(1 for item in items if item.class_label == "ai")
    real_count = sum(1 for item in items if item.class_label == "real")
    duplicates = duplicate_counts(items)

    print(f"AI images: {ai_count}")
    print(f"Real images: {real_count}")
    print(f"Total images: {len(items)}")
    if ai_count != EXPECTED_PER_CLASS:
        print(f"WARNING: AI image count is {ai_count}, expected {EXPECTED_PER_CLASS}.")
    if real_count != EXPECTED_PER_CLASS:
        print(f"WARNING: Real image count is {real_count}, expected {EXPECTED_PER_CLASS}.")
    if duplicates:
        print(f"WARNING: Duplicate sha256 values detected: {len(duplicates)} group(s).")
    print(f"Inventory: {display_path(resolve_path(args.output_dir) / INVENTORY_CSV.name)}")
    print(f"Summary: {display_path(resolve_path(args.output_dir) / SUMMARY_MD.name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
