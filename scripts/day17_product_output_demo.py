from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline  # noqa: E402
from scripts.day16_uncertain_v2 import (  # noqa: E402
    BASELINE_THRESHOLD,
    DEFAULT_DAY15_ALL_CSV,
    DEFAULT_DAY15_VARIANTS_CSV,
    DEFAULT_REPORTS_DIR,
    DEFAULT_TMP_ROOT,
    run_day16,
)
from src.product_output_schema import build_product_output  # noqa: E402


DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "test_images"
DEFAULT_V21_CSV = PROJECT_ROOT / "reports" / "day16_1_uncertain_decision_v21_results.csv"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "reports" / "day17_product_outputs.json"
DEFAULT_OUTPUT_JSONL = PROJECT_ROOT / "reports" / "day17_product_outputs.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Day17 product-level output schema demo for single image or batch CSV."
    )
    parser.add_argument("--image", type=Path, help="Optional single image path.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Batch data root used only when Day16.1 CSV needs to be regenerated.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_V21_CSV,
        help="Day16.1 v2.1 result CSV for batch product output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path. Defaults to reports/day17_product_outputs.json or .jsonl.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
        help="Batch output format.",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Omit raw_result from debug_evidence while keeping the stable debug schema.",
    )
    parser.add_argument(
        "--ensure-v21",
        action="store_true",
        help="Run the existing Day16.1 v21 report first if the input CSV is missing.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def ensure_v21_csv(path: Path, data_dir: Path) -> None:
    if path.exists():
        return
    run_day16(
        data_dir=resolve_path(data_dir),
        reports_dir=DEFAULT_REPORTS_DIR,
        tmp_root=DEFAULT_TMP_ROOT,
        threshold=BASELINE_THRESHOLD,
        day15_cache=DEFAULT_DAY15_VARIANTS_CSV,
        day15_all=DEFAULT_DAY15_ALL_CSV,
        force_rescan=False,
        policy_name="v21",
    )


def product_for_single_image(image_path: Path, debug: bool) -> dict[str, Any]:
    report = run_pipeline(resolve_path(image_path), output_dir=PROJECT_ROOT / "outputs" / "reports")
    product = build_product_output(report, image_path=str(resolve_path(image_path)), debug=debug)
    return {
        "image_path": str(resolve_path(image_path)),
        **product,
    }


def product_for_batch(input_csv: Path, debug: bool) -> list[dict[str, Any]]:
    rows = read_csv_rows(input_csv)
    outputs: list[dict[str, Any]] = []
    for row in rows:
        image_path = str(row.get("image_path") or "")
        outputs.append(
            {
                "image_path": image_path,
                **build_product_output(row, image_path=image_path, debug=debug),
            }
        )
    return outputs


def main() -> int:
    args = parse_args()
    debug = not args.no_debug
    output_path = resolve_path(
        args.output
        or (DEFAULT_OUTPUT_JSONL if args.format == "jsonl" else DEFAULT_OUTPUT_JSON)
    )

    if args.image:
        product = product_for_single_image(args.image, debug=debug)
        write_json(output_path, product)
        print(json.dumps(product, ensure_ascii=False, indent=2, default=str))
        print(f"product_output: {output_path}")
        return 0

    input_csv = resolve_path(args.input_csv)
    if args.ensure_v21:
        ensure_v21_csv(input_csv, args.data_dir)
    if not input_csv.exists():
        print(
            f"Missing input CSV: {input_csv}. Run scripts/day16_uncertain_v2.py --policy v21 "
            "or rerun with --ensure-v21.",
            file=sys.stderr,
        )
        return 1

    outputs = product_for_batch(input_csv, debug=debug)
    if args.format == "jsonl":
        write_jsonl(output_path, outputs)
    else:
        write_json(output_path, outputs)
    print(f"batch_count: {len(outputs)}")
    print(f"product_output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
