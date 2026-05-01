from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
REPORTS_DIR = PROJECT_ROOT / "reports" / "day8"
RENAME_MAP_CSV = REPORTS_DIR / "day8_rename_map.csv"
CSV_FIELDS = [
    "class_label",
    "old_filename",
    "new_filename",
    "old_path",
    "new_path",
    "extension",
    "sha256",
    "status",
]


@dataclass(frozen=True)
class RenamePlan:
    class_label: str
    old_path: Path
    temp_path: Path
    new_path: Path
    sha256: str
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day8 test-image naming organizer for AI Image Trust Scanner.",
    )
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
        "--output",
        type=Path,
        default=RENAME_MAP_CSV,
        help="Rename mapping CSV path. Default: reports/day8/day8_rename_map.csv",
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


def is_supported_image(path: Path) -> bool:
    if not path.is_file():
        return False
    if is_hidden_or_system(path):
        return False
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.name.casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def image_files(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")
    return sorted((path for path in directory.iterdir() if is_supported_image(path)), key=natural_key)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_plan(directory: Path, class_label: str, prefix: str, run_id: str) -> list[RenamePlan]:
    plans: list[RenamePlan] = []
    for index, old_path in enumerate(image_files(directory), start=1):
        new_name = f"{prefix}_{index:03d}{old_path.suffix}"
        new_path = directory / new_name
        temp_path = directory / f".__day8_tmp_{run_id}_{index:03d}{old_path.suffix}"
        status = "unchanged" if old_path.name == new_name else "renamed"
        plans.append(
            RenamePlan(
                class_label=class_label,
                old_path=old_path,
                temp_path=temp_path,
                new_path=new_path,
                sha256=sha256_file(old_path),
                status=status,
            )
        )
    return plans


def assert_safe_targets(plans: list[RenamePlan]) -> None:
    temp_names = [plan.temp_path.name.casefold() for plan in plans]
    if len(temp_names) != len(set(temp_names)):
        raise RuntimeError("Temporary rename collision detected.")

    final_names = [plan.new_path.name.casefold() for plan in plans]
    if len(final_names) != len(set(final_names)):
        raise RuntimeError("Final rename collision detected.")

    old_paths = {plan.old_path.resolve() for plan in plans}
    for plan in plans:
        if plan.temp_path.exists():
            raise FileExistsError(f"Temporary file already exists: {plan.temp_path}")
        if plan.new_path.exists() and plan.new_path.resolve() not in old_paths:
            raise FileExistsError(f"Target file already exists outside this image set: {plan.new_path}")


def execute_two_stage_rename(plans: list[RenamePlan]) -> None:
    if not plans:
        return
    assert_safe_targets(plans)

    completed_temp: list[RenamePlan] = []
    try:
        for plan in plans:
            plan.old_path.rename(plan.temp_path)
            completed_temp.append(plan)
        for plan in plans:
            plan.temp_path.rename(plan.new_path)
    except Exception:
        for plan in reversed(completed_temp):
            if plan.temp_path.exists() and not plan.old_path.exists():
                plan.temp_path.rename(plan.old_path)
        raise


def write_mapping(plans: list[RenamePlan], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for plan in plans:
            writer.writerow(
                {
                    "class_label": plan.class_label,
                    "old_filename": plan.old_path.name,
                    "new_filename": plan.new_path.name,
                    "old_path": display_path(plan.old_path),
                    "new_path": display_path(plan.new_path),
                    "extension": plan.old_path.suffix,
                    "sha256": plan.sha256,
                    "status": plan.status,
                }
            )


def run(ai_dir: Path, real_dir: Path, output_csv: Path) -> list[RenamePlan]:
    ai_dir = resolve_path(ai_dir)
    real_dir = resolve_path(real_dir)
    output_csv = resolve_path(output_csv)
    run_id = uuid.uuid4().hex

    plans = [
        *build_plan(ai_dir, "ai", "ai", run_id),
        *build_plan(real_dir, "real", "real", run_id),
    ]
    by_directory: dict[Path, list[RenamePlan]] = {}
    for plan in plans:
        by_directory.setdefault(plan.old_path.parent, []).append(plan)

    for directory_plans in by_directory.values():
        execute_two_stage_rename(directory_plans)

    write_mapping(plans, output_csv)
    return plans


def main() -> int:
    args = parse_args()
    plans = run(args.ai_dir, args.real_dir, args.output)
    renamed_count = sum(1 for plan in plans if plan.status == "renamed")
    unchanged_count = sum(1 for plan in plans if plan.status == "unchanged")

    print(f"Total images recorded: {len(plans)}")
    print(f"Renamed: {renamed_count}")
    print(f"Unchanged: {unchanged_count}")
    print(f"Rename map: {display_path(resolve_path(args.output))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
