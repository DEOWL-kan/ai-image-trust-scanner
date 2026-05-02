from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api_adapter import build_error_response, build_frontend_response  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "reports" / "day18"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def sample_day17_result(
    final_label: str,
    risk_level: str,
    confidence: float,
    score: float,
    decision_reason: str,
) -> dict[str, Any]:
    return {
        "final_label": final_label,
        "risk_level": risk_level,
        "confidence": confidence,
        "decision_reason": [decision_reason],
        "recommendation": {
            "action": "warn" if final_label == "likely_ai" else "review" if final_label == "uncertain" else "allow",
            "message": "Use the adapted Day18 response contract for frontend display.",
        },
        "user_facing_summary": f"Sample Day17 product output for {final_label}.",
        "technical_explanation": "Synthetic Day18 contract sample; no real image was scanned.",
        "debug_evidence": {
            "raw_score": score,
            "threshold_used": 0.15,
            "risk_factors": ["ai_like_score_pattern"] if final_label == "likely_ai" else [],
            "stability_factors": ["multi_resolution_label_consistency"] if final_label != "uncertain" else [],
            "uncertainty_flags": [decision_reason] if final_label == "uncertain" else [],
            "multi_resolution": {
                "score_range": 0.02 if final_label != "uncertain" else 0.061,
                "resolution_flip_count": 0 if final_label != "uncertain" else 1,
            },
            "format_info": {"format": "png"},
            "exif_info": {"has_exif": False},
        },
    }


def required_paths_for_success() -> list[tuple[str, ...]]:
    return [
        ("schema_version",),
        ("status",),
        ("request_id",),
        ("data", "image", "filename"),
        ("data", "image", "width"),
        ("data", "image", "height"),
        ("data", "image", "format"),
        ("data", "image", "size_bytes"),
        ("data", "result", "final_label"),
        ("data", "result", "risk_level"),
        ("data", "result", "confidence"),
        ("data", "result", "decision_reason"),
        ("data", "result", "recommendation", "action"),
        ("data", "result", "recommendation", "message"),
        ("data", "result", "user_facing_summary"),
        ("data", "result", "technical_explanation", "score"),
        ("data", "result", "technical_explanation", "threshold_used"),
        ("data", "result", "technical_explanation", "decision_layer"),
        ("data", "result", "technical_explanation", "main_signals"),
        ("data", "result", "debug_evidence", "enabled"),
        ("data", "result", "debug_evidence", "raw_score"),
        ("data", "result", "debug_evidence", "feature_summary"),
        ("data", "result", "debug_evidence", "consistency_checks"),
        ("data", "result", "debug_evidence", "format_evidence"),
        ("data", "result", "debug_evidence", "resolution_evidence"),
        ("meta", "processed_at"),
        ("meta", "adapter_version"),
        ("meta", "model_family"),
        ("meta", "notes"),
    ]


def required_paths_for_error() -> list[tuple[str, ...]]:
    return [
        ("schema_version",),
        ("status",),
        ("request_id",),
        ("error", "code"),
        ("error", "message"),
        ("error", "details"),
        ("data",),
        ("meta", "processed_at"),
        ("meta", "adapter_version"),
    ]


def has_path(payload: dict[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return True


def field_check(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    paths = required_paths_for_error() if payload.get("status") == "error" else required_paths_for_success()
    missing = [".".join(path) for path in paths if not has_path(payload, path)]
    return {
        "name": name,
        "status": payload.get("status"),
        "complete": not missing,
        "missing": missing,
    }


def build_contract_samples() -> dict[str, dict[str, Any]]:
    image_meta = {
        "filename": "contract_sample.png",
        "width": 1024,
        "height": 768,
        "format": "png",
        "size_bytes": 204800,
    }
    return {
        "day18_success_ai_generated": build_frontend_response(
            sample_day17_result("likely_ai", "high", 0.84, 0.191, "stable_ai_high_confidence_v21"),
            image_meta=image_meta,
            request_id="day18-sample-ai",
            include_debug=True,
        ),
        "day18_success_real_photo": build_frontend_response(
            sample_day17_result("likely_real", "low", 0.78, 0.104, "stable_real_safe_v21"),
            image_meta={**image_meta, "filename": "contract_real.jpg", "format": "jpg"},
            request_id="day18-sample-real",
            include_debug=True,
        ),
        "day18_success_uncertain": build_frontend_response(
            sample_day17_result("uncertain", "medium", 0.52, 0.151, "near_threshold_band_v21"),
            image_meta={**image_meta, "filename": "contract_uncertain.webp", "format": "webp"},
            request_id="day18-sample-uncertain",
            include_debug=False,
        ),
        "day18_error_invalid_image": build_error_response(
            "INVALID_IMAGE",
            "The uploaded file could not be opened as a supported image.",
            details={"filename": "broken.txt"},
            request_id="day18-sample-error",
        ),
    }


def build_real_image_response(image_path: Path) -> dict[str, Any] | None:
    try:
        from main import run_pipeline
    except Exception as exc:
        print(f"Optional image scan skipped; could not import pipeline: {exc}")
        return None

    try:
        report = run_pipeline(image_path, output_dir=PROJECT_ROOT / "outputs" / "reports")
        image_meta = {"filename": image_path.name, "format": image_path.suffix.lower().lstrip(".")}
        return build_frontend_response(report, image_meta=image_meta, request_id="day18-real-image")
    except Exception as exc:
        return build_error_response(
            "DETECTION_FAILED",
            "Optional real-image detection failed.",
            details={"image_path": str(image_path), "error": str(exc)},
            request_id="day18-real-image",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day18 frontend JSON contract check.")
    parser.add_argument("--image", type=Path, help="Optional real image path to adapt through the existing detector.")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR, help="Output directory for Day18 JSON files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    samples = build_contract_samples()

    if args.image:
        image_path = args.image if args.image.is_absolute() else PROJECT_ROOT / args.image
        real_response = build_real_image_response(image_path)
        if real_response is not None:
            samples["day18_optional_real_image_response"] = real_response

    checks = []
    for name, payload in samples.items():
        path = output_dir / f"{name}.json"
        write_json(path, payload)
        check = field_check(name, payload)
        check["path"] = str(path)
        checks.append(check)

    summary = {
        "adapter_version": "day18_api_adapter_v1",
        "output_dir": str(output_dir),
        "all_complete": all(check["complete"] for check in checks),
        "checks": checks,
    }
    write_json(output_dir / "day18_contract_check_summary.json", summary)

    print("Day18 contract check")
    print(f"output_dir: {output_dir}")
    for check in checks:
        status = "PASS" if check["complete"] else "FAIL"
        print(f"{status}: {check['name']} -> {check['path']}")
        if check["missing"]:
            print(f"  missing: {', '.join(check['missing'])}")
    return 0 if summary["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
