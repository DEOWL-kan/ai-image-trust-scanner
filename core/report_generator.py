from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LIMITATION_NOTE = (
    "This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, "
    "forensic, frequency, and placeholder model signals. It is not a final detection "
    "conclusion and should not be treated as proof that an image is real or AI-generated."
)


def _safe_stem(image_info: dict[str, Any]) -> str:
    filename = image_info.get("filename") or Path(str(image_info.get("image_path", "image"))).name
    stem = Path(filename).stem
    return stem or "image"


def build_report(
    image_info: dict[str, Any],
    metadata_result: dict[str, Any],
    forensic_result: dict[str, Any],
    frequency_result: dict[str, Any],
    model_result: dict[str, Any],
    final_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "V0.1 baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": bool(image_info.get("ok")),
        "image_info": image_info,
        "metadata_result": metadata_result,
        "forensic_result": forensic_result,
        "frequency_result": frequency_result,
        "model_result": model_result,
        "final_result": final_result,
        "evidence_summary": final_result.get("evidence_summary", []),
        "limitation_note": LIMITATION_NOTE,
    }


def write_reports(report: dict[str, Any], output_dir: str | Path = "outputs/reports") -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(report.get("image_info", {}))
    json_path = output_path / f"{stem}_report.json"
    markdown_path = output_path / f"{stem}_report.md"
    report_paths = {
        "json_report": str(json_path.resolve()),
        "markdown_report": str(markdown_path.resolve()),
    }
    report["report_paths"] = report_paths

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")

    return report_paths


def _render_markdown(report: dict[str, Any]) -> str:
    final_result = report.get("final_result", {})
    evidence = report.get("evidence_summary", [])
    evidence_lines = "\n".join(f"- {item}" for item in evidence) if evidence else "- No evidence summary."

    return f"""# AI Image Trust Scanner Report

Version: {report.get("version", "V0.1 baseline")}

Generated at: {report.get("generated_at")}

## Final Result

- Final score: {final_result.get("final_score")}
- Risk level: {final_result.get("risk_level")}

## Image Info

```json
{json.dumps(report.get("image_info", {}), ensure_ascii=False, indent=2, default=str)}
```

## Metadata Result

```json
{json.dumps(report.get("metadata_result", {}), ensure_ascii=False, indent=2, default=str)}
```

## Forensic Result

```json
{json.dumps(report.get("forensic_result", {}), ensure_ascii=False, indent=2, default=str)}
```

## Frequency Result

```json
{json.dumps(report.get("frequency_result", {}), ensure_ascii=False, indent=2, default=str)}
```

## Model Result

```json
{json.dumps(report.get("model_result", {}), ensure_ascii=False, indent=2, default=str)}
```

## Evidence Summary

{evidence_lines}

## Limitation Note

{report.get("limitation_note")}
"""
