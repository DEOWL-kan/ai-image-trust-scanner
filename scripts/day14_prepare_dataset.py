from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

try:
    from PIL import ExifTags, Image, ImageOps
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("Pillow is required to inspect and generate image variants.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "data" / "test_images"
DAY14_ROOT = TEST_ROOT / "day14_expansion"
RAW_ROOT = DAY14_ROOT / "raw"
PAIRED_ROOT = DAY14_ROOT / "paired_format"
RESOLUTION_ROOT = DAY14_ROOT / "resolution_control"
LEGACY_ROOT = TEST_ROOT / "legacy" / "day8_small_30"
METADATA_DIR = DAY14_ROOT / "metadata"
ORG_REPORT_PATH = PROJECT_ROOT / "docs" / "day14_dataset_organization_report.md"
FORMAT_REPORT_PATH = PROJECT_ROOT / "docs" / "day14_format_resolution_generation_report.md"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
JPG_QUALITY = 95
RESOLUTION_TARGETS = {
    "long1024": 1024,
    "long768": 768,
    "long512": 512,
}
METADATA_FIELDS = [
    "image_id",
    "label",
    "scene_type",
    "source_type",
    "original_filename",
    "original_format",
    "current_filename",
    "current_format",
    "variant",
    "resolution_type",
    "long_edge",
    "width",
    "height",
    "compression_quality",
    "exif_status",
    "source_device",
    "generation_model",
    "prompt_id",
    "variant_group",
    "split",
    "difficulty",
    "difficulty_source",
    "difficulty_reason",
    "notes",
]


def clean_scene_type(name: str) -> str:
    value = name.lower().strip()
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_]+", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown_scene"


def subdirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([p for p in path.iterdir() if p.is_dir()], key=lambda p: p.name.lower())


def direct_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([p for p in path.iterdir() if p.is_file()], key=lambda p: p.name.lower())


def image_files(path: Path) -> list[Path]:
    return [p for p in direct_files(path) if p.suffix.lower() in SUPPORTED_EXTS]


def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    index = 1
    while True:
        candidate = parent / f"{stem}__dup{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def safe_move(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    final_dest = unique_destination(dest)
    shutil.move(str(src), str(final_dest))
    return final_dest


def prepare_directories() -> None:
    for label in ("ai", "real"):
        (LEGACY_ROOT / label).mkdir(parents=True, exist_ok=True)
        (RAW_ROOT / label).mkdir(parents=True, exist_ok=True)
    for folder in ("ai_png", "ai_jpg", "real_png", "real_jpg"):
        (PAIRED_ROOT / folder).mkdir(parents=True, exist_ok=True)
    for folder in ("long_1024", "long_768", "long_512"):
        (RESOLUTION_ROOT / folder).mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    ORG_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FORMAT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def archive_legacy_images(label: str) -> int:
    moved = 0
    for src in direct_files(TEST_ROOT / label):
        if src.suffix.lower() in SUPPORTED_EXTS:
            safe_move(src, LEGACY_ROOT / label / src.name)
            moved += 1
    return moved


def move_day14_scene_dirs(label: str) -> list[str]:
    source_dir = TEST_ROOT / label
    detected = []
    for scene_dir in subdirs(source_dir):
        safe_scene = clean_scene_type(scene_dir.name)
        detected.append(safe_scene)
        target_scene_dir = RAW_ROOT / label / safe_scene
        target_scene_dir.mkdir(parents=True, exist_ok=True)
        for child in sorted(scene_dir.iterdir(), key=lambda p: p.name.lower()):
            safe_move(child, target_scene_dir / child.name)
        try:
            scene_dir.rmdir()
        except OSError:
            pass
    return sorted(set(detected))


def normalize_raw_scene_dirs(label: str) -> tuple[list[str], list[str]]:
    warnings = []
    raw_label_dir = RAW_ROOT / label
    normalized = []
    for scene_dir in subdirs(raw_label_dir):
        safe_name = clean_scene_type(scene_dir.name)
        target = raw_label_dir / safe_name
        normalized.append(safe_name)
        if target == scene_dir:
            continue
        if target.exists():
            warnings.append(
                f"{label}: scene folder '{scene_dir.name}' sanitized into existing '{safe_name}', files were merged."
            )
            for child in sorted(scene_dir.iterdir(), key=lambda p: p.name.lower()):
                safe_move(child, target / child.name)
            try:
                scene_dir.rmdir()
            except OSError:
                pass
        else:
            scene_dir.rename(target)
    return sorted(set(normalized)), warnings


def exif_model(exif: dict[int, object]) -> str:
    model_tag = None
    for tag_id, tag_name in ExifTags.TAGS.items():
        if tag_name == "Model":
            model_tag = tag_id
            break
    if model_tag is None:
        return "unknown"
    model = exif.get(model_tag)
    if model is None:
        return "unknown"
    return str(model).strip() or "unknown"


def inspect_image(path: Path, label: str) -> tuple[int, int, int, str, str]:
    with Image.open(path) as img:
        exif = dict(img.getexif() or {})
        display_img = ImageOps.exif_transpose(img)
        width, height = display_img.size
    if exif:
        exif_status = "exif_keep"
    elif label == "ai":
        exif_status = "exif_none_generated"
    else:
        exif_status = "exif_missing"
    return width, height, max(width, height), exif_status, exif_model(exif)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_existing_native_metadata() -> dict[str, dict[str, str]]:
    metadata_path = METADATA_DIR / "day14_metadata.csv"
    by_hash: dict[str, dict[str, str]] = {}
    if not metadata_path.exists():
        return by_hash
    with metadata_path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("variant") != "native":
                continue
            label = row.get("label", "")
            scene = row.get("scene_type", "")
            filename = row.get("current_filename", "")
            path = RAW_ROOT / label / scene / filename
            if path.exists():
                by_hash[sha256_file(path)] = row
    return by_hash


def normalized_image_plan(label: str, existing_by_hash: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    raw_label_dir = RAW_ROOT / label
    plan = []
    next_id = 1
    for scene_dir in subdirs(raw_label_dir):
        scene_type = clean_scene_type(scene_dir.name)
        for src in image_files(scene_dir):
            file_hash = sha256_file(src)
            previous = existing_by_hash.get(file_hash, {})
            image_id = f"{label}_{next_id:03d}"
            current_filename = f"{image_id}_{scene_type}_native{src.suffix.lower()}"
            plan.append(
                {
                    "src": src,
                    "label": label,
                    "scene_type": scene_type,
                    "id": next_id,
                    "image_id": image_id,
                    "original_filename": previous.get("original_filename") or src.name,
                    "original_format": previous.get("original_format") or src.suffix.lower().lstrip("."),
                    "target": scene_dir / current_filename,
                    "current_filename": current_filename,
                    "current_format": src.suffix.lower().lstrip("."),
                    "sha256": file_hash,
                }
            )
            next_id += 1
    return plan


def apply_rename_plan(plan: list[dict[str, object]]) -> None:
    temp_pairs: list[tuple[Path, Path]] = []
    for index, item in enumerate(plan):
        src = item["src"]
        target = item["target"]
        if not isinstance(src, Path) or not isinstance(target, Path):
            raise TypeError("Rename plan contains non-path entries.")
        if src == target:
            continue
        temp = src.with_name(f".day14_tmp_{index}_{src.name}")
        if temp.exists():
            temp = unique_destination(temp)
        src.rename(temp)
        temp_pairs.append((temp, target))
        item["src"] = target
    for temp, target in temp_pairs:
        if target.exists():
            raise RuntimeError(f"Refusing to overwrite existing file: {target}")
        temp.rename(target)


def collect_invalid_and_unsupported() -> tuple[list[str], list[str]]:
    invalid = []
    unsupported = []
    for label in ("ai", "real"):
        for scene_dir in subdirs(RAW_ROOT / label):
            for item in sorted(scene_dir.iterdir(), key=lambda p: p.name.lower()):
                if item.is_dir():
                    invalid.append(str(item.relative_to(PROJECT_ROOT)))
                    continue
                if item.suffix.lower() not in SUPPORTED_EXTS:
                    unsupported.append(str(item.relative_to(PROJECT_ROOT)))
                    continue
                try:
                    with Image.open(item) as img:
                        img.verify()
                except Exception:
                    invalid.append(str(item.relative_to(PROJECT_ROOT)))
    return invalid, unsupported


def metadata_row(
    base: dict[str, str],
    current_filename: str,
    current_format: str,
    variant: str,
    resolution_type: str,
    split: str,
    path: Path,
    compression_quality: str = "",
    notes: str = "",
) -> dict[str, str]:
    label = base["label"]
    width, height, long_edge, exif_status, source_device = inspect_image(path, label)
    if base.get("source_device") and base["source_device"] != "unknown":
        source_device = base["source_device"]
    return {
        "image_id": base["image_id"],
        "label": label,
        "scene_type": base["scene_type"],
        "source_type": base["source_type"],
        "original_filename": base["original_filename"],
        "original_format": base["original_format"],
        "current_filename": current_filename,
        "current_format": current_format,
        "variant": variant,
        "resolution_type": resolution_type,
        "long_edge": str(long_edge),
        "width": str(width),
        "height": str(height),
        "compression_quality": compression_quality,
        "exif_status": exif_status,
        "source_device": source_device,
        "generation_model": base["generation_model"],
        "prompt_id": base["prompt_id"],
        "variant_group": base["image_id"],
        "split": split,
        "difficulty": "unknown",
        "difficulty_source": "not_labeled",
        "difficulty_reason": "pending baseline evaluation",
        "notes": notes,
    }


def build_native_metadata(plan: list[dict[str, object]], invalid: list[str]) -> list[dict[str, str]]:
    invalid_set = {Path(p).name for p in invalid}
    rows = []
    for item in plan:
        target = item["target"]
        if not isinstance(target, Path):
            raise TypeError("Metadata plan target is not a path.")
        if target.name in invalid_set:
            continue
        label = str(item["label"])
        image_id = str(item["image_id"])
        base = {
            "image_id": image_id,
            "label": label,
            "scene_type": str(item["scene_type"]),
            "source_type": "generated" if label == "ai" else "camera",
            "original_filename": str(item["original_filename"]),
            "original_format": str(item["original_format"]),
            "generation_model": "unknown_generated_model" if label == "ai" else "none",
            "prompt_id": "unknown_prompt" if label == "ai" else "none",
        }
        rows.append(
            metadata_row(
                base=base,
                current_filename=str(item["current_filename"]),
                current_format=str(item["current_format"]),
                variant="native",
                resolution_type="native",
                split="day14_main_eval",
                path=target,
            )
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def scene_index_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in rows:
        grouped[(row["label"], row["scene_type"])].append(int(row["image_id"].split("_")[1]))
    for (label, scene_type), ids in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        output.append(
            {
                "scene_type": scene_type,
                "start_id": f"{min(ids):03d}",
                "end_id": f"{max(ids):03d}",
                "count": str(len(ids)),
                "label": label,
            }
        )
    return output


def scene_counts(rows: list[dict[str, str]], label: str) -> list[dict[str, str]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["label"] == label:
            counts[row["scene_type"]] += 1
    return [{"scene_type": scene, "count": str(count)} for scene, count in sorted(counts.items())]


def duplicate_report(rows: list[dict[str, str]]) -> list[str]:
    by_name: dict[str, list[str]] = defaultdict(list)
    by_hash: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        path = RAW_ROOT / row["label"] / row["scene_type"] / row["current_filename"]
        rel = str(path.relative_to(PROJECT_ROOT))
        by_name[row["current_filename"]].append(rel)
        by_hash[sha256_file(path)].append(rel)
    duplicates = []
    for filename, paths in sorted(by_name.items()):
        if len(paths) > 1:
            duplicates.append(f"name:{filename} -> {paths}")
    for digest, paths in sorted(by_hash.items()):
        if len(paths) > 1:
            duplicates.append(f"hash:{digest} -> {paths}")
    return duplicates


def open_display_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img).copy()


def flatten_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def save_jpg(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flatten_to_rgb(img).save(path, format="JPEG", quality=JPG_QUALITY)


def files_identical(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and sha256_file(left) == sha256_file(right)


def write_generated_file(
    target: Path,
    suffix: str,
    writer,
    error_list: list[str],
) -> str:
    temp = target.with_name(f".day14_tmp_generate_{target.stem}{suffix}")
    if temp.exists():
        temp.unlink()
    try:
        writer(temp)
        if target.exists():
            if files_identical(temp, target):
                temp.unlink()
                return "skipped"
            temp.unlink()
            error_list.append(f"Refusing to overwrite different existing file: {target.relative_to(PROJECT_ROOT)}")
            return "error"
        temp.rename(target)
        return "generated"
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        error_list.append(f"{target.relative_to(PROJECT_ROOT)}: {exc}")
        return "error"


def copy_generated_file(src: Path, target: Path, error_list: list[str]) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256_file(src) == sha256_file(target):
            return "skipped"
        error_list.append(f"Refusing to overwrite different existing file: {target.relative_to(PROJECT_ROOT)}")
        return "error"
    shutil.copy2(src, target)
    return "generated"


def paired_path(row: dict[str, str], fmt: str) -> Path:
    folder = PAIRED_ROOT / f"{row['label']}_{fmt}"
    if fmt == "png":
        filename = f"{row['image_id']}_{row['scene_type']}_png.png"
    else:
        filename = f"{row['image_id']}_{row['scene_type']}_jpg_q95.jpg"
    return folder / filename


def resolution_path(base_row: dict[str, str], fmt_variant: str, resolution_type: str) -> Path:
    target_edge = resolution_type.replace("long", "")
    folder = RESOLUTION_ROOT / f"long_{target_edge}"
    return folder / f"{base_row['image_id']}_{base_row['scene_type']}_{fmt_variant}_{resolution_type}.{'png' if fmt_variant == 'png' else 'jpg'}"


def generate_paired_format(
    native_rows: list[dict[str, str]], error_list: list[str]
) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows = []
    stats = defaultdict(int)
    for row in native_rows:
        src = RAW_ROOT / row["label"] / row["scene_type"] / row["current_filename"]
        try:
            img = open_display_image(src)
        except Exception as exc:
            error_list.append(f"{src.relative_to(PROJECT_ROOT)}: {exc}")
            continue

        png_target = paired_path(row, "png")
        png_status = write_generated_file(png_target, ".png", lambda temp, image=img: save_png(image, temp), error_list)
        if png_status != "error":
            if png_status == "skipped":
                stats["skipped_existing_count"] += 1
            rows.append(
                metadata_row(
                    base=row,
                    current_filename=png_target.name,
                    current_format="png",
                    variant="png",
                    resolution_type="native",
                    split="day14_format_eval",
                    path=png_target,
                )
            )

        jpg_target = paired_path(row, "jpg")
        jpg_status = write_generated_file(jpg_target, ".jpg", lambda temp, image=img: save_jpg(image, temp), error_list)
        if jpg_status != "error":
            if jpg_status == "skipped":
                stats["skipped_existing_count"] += 1
            rows.append(
                metadata_row(
                    base=row,
                    current_filename=jpg_target.name,
                    current_format="jpg",
                    variant="jpg_q95",
                    resolution_type="native",
                    split="day14_format_eval",
                    path=jpg_target,
                    compression_quality=str(JPG_QUALITY),
                )
            )
    return rows, dict(stats)


def resized_image(img: Image.Image, target_long_edge: int) -> tuple[Image.Image, bool]:
    width, height = img.size
    long_edge = max(width, height)
    if long_edge < target_long_edge:
        return img.copy(), True
    scale = target_long_edge / long_edge
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS), False


def source_for_paired_row(row: dict[str, str]) -> Path:
    folder = PAIRED_ROOT / f"{row['label']}_{'png' if row['variant'] == 'png' else 'jpg'}"
    return folder / row["current_filename"]


def generate_resolution_control(
    paired_rows: list[dict[str, str]], error_list: list[str]
) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows = []
    stats = defaultdict(int)
    for row in paired_rows:
        src = source_for_paired_row(row)
        if not src.exists():
            error_list.append(f"Missing paired source for resolution variant: {src.relative_to(PROJECT_ROOT)}")
            continue
        try:
            img = open_display_image(src)
        except Exception as exc:
            error_list.append(f"{src.relative_to(PROJECT_ROOT)}: {exc}")
            continue

        fmt_variant = row["variant"]
        for resolution_type, target_edge in RESOLUTION_TARGETS.items():
            target = resolution_path(row, fmt_variant, resolution_type)
            resized, no_upscale = resized_image(img, target_edge)
            notes = "no_upscale" if no_upscale else ""
            if no_upscale:
                status = copy_generated_file(src, target, error_list)
                stats["no_upscale_count"] += 1
            elif fmt_variant == "png":
                status = write_generated_file(
                    target, ".png", lambda temp, image=resized: save_png(image, temp), error_list
                )
            else:
                status = write_generated_file(
                    target, ".jpg", lambda temp, image=resized: save_jpg(image, temp), error_list
                )
            if status == "error":
                continue
            if status == "skipped":
                stats["skipped_existing_count"] += 1
            variant = f"{fmt_variant}_{resolution_type}"
            rows.append(
                metadata_row(
                    base=row,
                    current_filename=target.name,
                    current_format="png" if fmt_variant == "png" else "jpg",
                    variant=variant,
                    resolution_type=resolution_type,
                    split="day14_resolution_eval",
                    path=target,
                    compression_quality=str(JPG_QUALITY) if fmt_variant == "jpg_q95" else "",
                    notes=notes,
                )
            )
    return rows, dict(stats)


def markdown_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "_None_"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row.get(field, "") for field in fields) + " |")
    return "\n".join(lines)


def count_rows(rows: list[dict[str, str]], **filters: str) -> int:
    return sum(1 for row in rows if all(row.get(key) == value for key, value in filters.items()))


def variant_scene_counts(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(row["label"], row["scene_type"])] += 1
    return [
        {"label": label, "scene_type": scene, "count": str(count)}
        for (label, scene), count in sorted(counts.items())
    ]


def write_organization_report(summary: dict[str, object]) -> None:
    ai_scenes = ", ".join(summary["detected_ai_scene_folders"]) or "None"
    real_scenes = ", ".join(summary["detected_real_scene_folders"]) or "None"
    warnings = summary["warnings"]
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- None"
    invalid_text = "\n".join(f"- {item}" for item in summary["invalid_file_list"]) or "- None"
    unsupported_text = "\n".join(f"- {item}" for item in summary["unsupported_format_list"]) or "- None"
    duplicate_text = "\n".join(f"- {item}" for item in summary["duplicate_name_or_hash_list"]) or "- None"
    report = f"""# Day14 Dataset Organization Report

## 1. Day14 Data Organization Goal

Organize the Day14 expansion dataset into a separated raw scene structure, archive the older small test set as a legacy regression set, normalize native image filenames, and regenerate Day14 native metadata with difficulty initialized to `unknown`.

## 2. Legacy Regression Set

Archived old directly scattered images into:

- `data/test_images/legacy/day8_small_30/ai`
- `data/test_images/legacy/day8_small_30/real`

Moved counts:

- AI: {summary["old_ai_moved_count"]}
- Real: {summary["old_real_moved_count"]}

## 3. Day14 Dataset Path

Day14 raw images are organized under:

- `data/test_images/day14_expansion/raw/ai/<scene_type>/`
- `data/test_images/day14_expansion/raw/real/<scene_type>/`

## 4. Naming Rule

Native Day14 image filenames follow:

`<label>_<id>_<scene_type>_native.<ext>`

Rules applied:

- `label` is `ai` or `real`
- IDs are independent per label and continuous from `001`
- scene folders are sorted first, then original filenames are sorted within each scene
- `scene_type` is lowercased and restricted to `a-z`, `0-9`, and `_`
- difficulty is not included in filenames

## 5. Scene Type List

Detected AI scene folders:

{ai_scenes}

Detected Real scene folders:

{real_scenes}

## 6. AI/Real Counts By Scene

AI:

{markdown_table(summary["ai_scene_count_table"], ["scene_type", "count"])}

Real:

{markdown_table(summary["real_scene_count_table"], ["scene_type", "count"])}

## 7. Metadata Fields

`day14_metadata.csv` fields:

`{", ".join(METADATA_FIELDS)}`

## 8. Current Gaps And Warnings

- `day14_raw_ai_count`: {summary["day14_raw_ai_count"]}
- `day14_raw_real_count`: {summary["day14_raw_real_count"]}
- `missing_ai_count`: {summary["missing_ai_count"]}
- `missing_real_count`: {summary["missing_real_count"]}
- `native_metadata_row_count`: {summary["metadata_row_count"]}

Warnings:

{warning_text}

Invalid files:

{invalid_text}

Unsupported formats:

{unsupported_text}

Duplicate name or hash findings:

{duplicate_text}

## 9. Suggested Next Steps

- Use `docs/day14_format_resolution_generation_report.md` for paired format and resolution-control generation details.
- Run a baseline evaluation later to label difficulty from measured model behavior rather than subjective judgment.
"""
    ORG_REPORT_PATH.write_text(report, encoding="utf-8")


def write_format_report(summary: dict[str, object]) -> None:
    error_text = "\n".join(f"- {item}" for item in summary["error_list"]) or "- None"
    no_upscale_rows = [
        {"variant": row["variant"], "current_filename": row["current_filename"]}
        for row in summary["resolution_rows"]
        if row.get("notes") == "no_upscale"
    ]
    no_upscale_text = markdown_table(no_upscale_rows[:50], ["variant", "current_filename"])
    if len(no_upscale_rows) > 50:
        no_upscale_text += f"\n\n_Only first 50 of {len(no_upscale_rows)} no_upscale rows shown._"
    report = f"""# Day14 Format And Resolution Generation Report

## 1. Input Raw Data Quantity

- `raw_ai_count`: {summary["raw_ai_count"]}
- `raw_real_count`: {summary["raw_real_count"]}

## 2. Paired Format Output Quantity

- `generated_ai_png_count`: {summary["generated_ai_png_count"]}
- `generated_ai_jpg_count`: {summary["generated_ai_jpg_count"]}
- `generated_real_png_count`: {summary["generated_real_png_count"]}
- `generated_real_jpg_count`: {summary["generated_real_jpg_count"]}

## 3. Resolution Control Output Quantity

- `generated_long1024_count`: {summary["generated_long1024_count"]}
- `generated_long768_count`: {summary["generated_long768_count"]}
- `generated_long512_count`: {summary["generated_long512_count"]}

## 4. Counts By Label

{markdown_table(summary["label_count_table"], ["label", "native", "paired_format", "resolution_control", "total"])}

## 5. Counts By Scene Type

{markdown_table(summary["scene_type_count_table"], ["label", "scene_type", "count"])}

## 6. No Upscale

- `no_upscale_count`: {summary["no_upscale_count"]}

{no_upscale_text}

## 7. Error List

{error_text}

## 8. Metadata

- `metadata_total_rows`: {summary["metadata_total_rows"]}
- `skipped_existing_count`: {summary["skipped_existing_count"]}

## 9. How To Run Day14 Baseline Evaluation Later

Use the updated `data/test_images/day14_expansion/metadata/day14_metadata.csv` to select evaluation splits:

- `day14_main_eval` for native raw images
- `day14_format_eval` for PNG/JPG format comparison
- `day14_resolution_eval` for long-edge resolution control

Keep threshold, final label logic, and score weights unchanged during the first Day14 baseline run so that differences reflect dataset, format, and resolution behavior rather than detector changes.
"""
    FORMAT_REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    prepare_directories()

    old_ai_moved_count = archive_legacy_images("ai")
    old_real_moved_count = archive_legacy_images("real")
    existing_by_hash = load_existing_native_metadata()

    moved_ai_scenes = move_day14_scene_dirs("ai")
    moved_real_scenes = move_day14_scene_dirs("real")
    raw_ai_scenes, ai_warnings = normalize_raw_scene_dirs("ai")
    raw_real_scenes, real_warnings = normalize_raw_scene_dirs("real")

    detected_ai_scene_folders = sorted(set(moved_ai_scenes) | set(raw_ai_scenes))
    detected_real_scene_folders = sorted(set(moved_real_scenes) | set(raw_real_scenes))

    warnings = ai_warnings + real_warnings
    if set(detected_ai_scene_folders) != set(detected_real_scene_folders):
        warnings.append("AI and Real scene_type folder names are not identical; no folders were deleted.")
    if len(detected_ai_scene_folders) != 5:
        warnings.append(f"AI scene_type folder count is {len(detected_ai_scene_folders)}, expected 5 from the Day14 note.")
    if len(detected_real_scene_folders) != 5:
        warnings.append(f"Real scene_type folder count is {len(detected_real_scene_folders)}, expected 5 from the Day14 note.")

    invalid_file_list, unsupported_format_list = collect_invalid_and_unsupported()
    ai_plan = normalized_image_plan("ai", existing_by_hash)
    real_plan = normalized_image_plan("real", existing_by_hash)
    full_plan = ai_plan + real_plan
    apply_rename_plan(full_plan)

    invalid_file_list, unsupported_format_list = collect_invalid_and_unsupported()
    native_rows = build_native_metadata(full_plan, invalid_file_list)
    write_csv(METADATA_DIR / "day14_scene_index_map.csv", scene_index_rows(native_rows), ["scene_type", "start_id", "end_id", "count", "label"])

    raw_ai_count = count_rows(native_rows, label="ai")
    raw_real_count = count_rows(native_rows, label="real")
    organization_summary = {
        "detected_ai_scene_folders": detected_ai_scene_folders,
        "detected_real_scene_folders": detected_real_scene_folders,
        "old_ai_moved_count": old_ai_moved_count,
        "old_real_moved_count": old_real_moved_count,
        "day14_raw_ai_count": raw_ai_count,
        "day14_raw_real_count": raw_real_count,
        "ai_scene_count_table": scene_counts(native_rows, "ai"),
        "real_scene_count_table": scene_counts(native_rows, "real"),
        "invalid_file_list": invalid_file_list,
        "unsupported_format_list": unsupported_format_list,
        "duplicate_name_or_hash_list": duplicate_report(native_rows),
        "metadata_row_count": len(native_rows),
        "missing_ai_count": 100 - raw_ai_count,
        "missing_real_count": 100 - raw_real_count,
        "warnings": warnings,
    }
    write_organization_report(organization_summary)

    error_list: list[str] = []
    paired_rows, paired_stats = generate_paired_format(native_rows, error_list)
    resolution_rows, resolution_stats = generate_resolution_control(paired_rows, error_list)
    all_rows = native_rows + paired_rows + resolution_rows
    write_csv(METADATA_DIR / "day14_metadata.csv", all_rows, METADATA_FIELDS)

    label_count_table = []
    for label in ("ai", "real"):
        native_count = count_rows(native_rows, label=label)
        paired_count = count_rows(paired_rows, label=label)
        resolution_count = count_rows(resolution_rows, label=label)
        label_count_table.append(
            {
                "label": label,
                "native": str(native_count),
                "paired_format": str(paired_count),
                "resolution_control": str(resolution_count),
                "total": str(native_count + paired_count + resolution_count),
            }
        )

    format_summary = {
        "raw_ai_count": raw_ai_count,
        "raw_real_count": raw_real_count,
        "generated_ai_png_count": count_rows(paired_rows, label="ai", variant="png"),
        "generated_ai_jpg_count": count_rows(paired_rows, label="ai", variant="jpg_q95"),
        "generated_real_png_count": count_rows(paired_rows, label="real", variant="png"),
        "generated_real_jpg_count": count_rows(paired_rows, label="real", variant="jpg_q95"),
        "generated_long1024_count": count_rows(resolution_rows, resolution_type="long1024"),
        "generated_long768_count": count_rows(resolution_rows, resolution_type="long768"),
        "generated_long512_count": count_rows(resolution_rows, resolution_type="long512"),
        "metadata_total_rows": len(all_rows),
        "skipped_existing_count": paired_stats.get("skipped_existing_count", 0)
        + resolution_stats.get("skipped_existing_count", 0),
        "no_upscale_count": resolution_stats.get("no_upscale_count", 0),
        "error_list": error_list,
        "label_count_table": label_count_table,
        "scene_type_count_table": variant_scene_counts(all_rows),
        "resolution_rows": resolution_rows,
    }
    write_format_report(format_summary)

    print(json.dumps(organization_summary | format_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
