from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from detectors.c2pa_detector import analyze_c2pa
from detectors.forensic_detector import analyze_forensic
from detectors.metadata_detector import analyze_metadata
from detectors.score_fusion import fuse_scores


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"


def _error_result(module_name: str, risk_score: int, exc: Exception) -> dict[str, Any]:
    return {
        "checked": False,
        "risk_score": risk_score,
        "signals": [f"{module_name} failed unexpectedly."],
        "error": str(exc),
    }


def _safe_call(
    module_name: str,
    fallback_risk_score: int,
    func: Callable[[str], dict[str, Any]],
    image_path: str,
) -> dict[str, Any]:
    try:
        return func(image_path)
    except Exception as exc:
        result = _error_result(module_name, fallback_risk_score, exc)
        result["traceback"] = traceback.format_exc()
        return result


def build_report(image_path: str) -> dict[str, Any]:
    path = Path(image_path).expanduser()
    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "image_path": str(path),
            "error": "Input image does not exist or is not a file.",
        }

    resolved_path = str(path.resolve())
    metadata_result = _safe_call("metadata_detector", 30, analyze_metadata, resolved_path)
    c2pa_result = _safe_call("c2pa_detector", 20, analyze_c2pa, resolved_path)
    forensic_result = _safe_call("forensic_detector", 70, analyze_forensic, resolved_path)

    try:
        fusion_result = fuse_scores(metadata_result, c2pa_result, forensic_result)
    except Exception as exc:
        fusion_result = {
            "risk": {
                "ai_generation_risk": 0,
                "provenance_risk": 0,
                "editing_risk": 0,
                "technical_quality_risk": 100,
                "overall_risk": 100,
                "risk_level": "very_high",
            },
            "conclusion": "Technical inspection failed; result is unreliable.",
            "evidence_summary": ["Score fusion failed; report should be reviewed manually."],
            "error": str(exc),
        }

    return {
        "ok": True,
        "image_path": resolved_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata_result,
        "c2pa": c2pa_result,
        "forensic": forensic_result,
        "fusion": fusion_result,
    }


def write_report(report: dict[str, Any], image_path: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem or "image"
    report_path = OUTPUT_DIR / f"{stem}_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return report_path


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("Usage: python backend/detect_image.py <image_path>")
        return 1

    image_path = argv[0]
    try:
        report = build_report(image_path)
        report_path = write_report(report, image_path)
        print(f"Report written to: {report_path}")
        return 0 if report.get("ok") else 1
    except Exception as exc:
        fallback_report = {
            "ok": False,
            "image_path": image_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        try:
            report_path = write_report(fallback_report, image_path)
            print(f"Report written to: {report_path}")
        except Exception:
            print(json.dumps(fallback_report, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
