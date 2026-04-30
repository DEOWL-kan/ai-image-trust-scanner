from __future__ import annotations

import json
import subprocess
from typing import Any


AI_TOOL_KEYWORDS = [
    "OpenAI",
    "ChatGPT",
    "Midjourney",
    "Stable Diffusion",
    "ComfyUI",
    "Automatic1111",
    "DALL-E",
    "DALL·E",
    "Adobe Firefly",
    "NovelAI",
]

EDITOR_KEYWORDS = [
    "Photoshop",
    "Lightroom",
    "Canva",
    "GIMP",
]

METADATA_FIELDS = {
    "Make": "camera_make",
    "Model": "camera_model",
    "LensModel": "lens_model",
    "ExposureTime": "exposure_time",
    "FNumber": "f_number",
    "ISO": "iso",
    "Software": "software",
    "CreateDate": "create_date",
}


def _empty_result(*, checked: bool, risk_score: int, error: str | None) -> dict[str, Any]:
    return {
        "checked": checked,
        "has_exif": False,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "risk_score": risk_score,
        "signals": [],
        "raw_metadata": {},
        "error": error,
    }


def _get_metadata_value(raw_metadata: dict[str, Any], field_name: str) -> Any:
    """Find an ExifTool field by exact, case-insensitive, or group-suffixed key."""
    if field_name in raw_metadata:
        return raw_metadata[field_name]

    lowered = field_name.lower()
    for key, value in raw_metadata.items():
        key_lower = str(key).lower()
        if key_lower == lowered or key_lower.endswith(f":{lowered}"):
            return value

    return None


def _stringify_metadata(raw_metadata: dict[str, Any]) -> str:
    try:
        return json.dumps(raw_metadata, ensure_ascii=False, default=str)
    except TypeError:
        return str(raw_metadata)


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in text_lower]


def analyze_metadata(image_path: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["exiftool", "-json", image_path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        result = _empty_result(
            checked=False,
            risk_score=30,
            error="exiftool is not installed or not available in PATH.",
        )
        result["signals"].append("Metadata check skipped because exiftool is unavailable.")
        return result
    except Exception as exc:
        result = _empty_result(
            checked=False,
            risk_score=30,
            error=f"Failed to run exiftool: {exc}",
        )
        result["signals"].append("Metadata check failed before metadata could be read.")
        return result

    if completed.returncode != 0:
        error_text = (completed.stderr or completed.stdout or "exiftool failed").strip()
        result = _empty_result(checked=False, risk_score=30, error=error_text)
        result["signals"].append("Metadata check failed while running exiftool.")
        return result

    try:
        parsed = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        result = _empty_result(
            checked=False,
            risk_score=30,
            error=f"Could not parse exiftool JSON output: {exc}",
        )
        result["signals"].append("Metadata check failed because exiftool returned invalid JSON.")
        return result

    raw_metadata = parsed[0] if isinstance(parsed, list) and parsed else {}
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}

    extracted = {
        output_key: _get_metadata_value(raw_metadata, source_key)
        for source_key, output_key in METADATA_FIELDS.items()
    }

    camera_fields = [
        extracted["camera_make"],
        extracted["camera_model"],
        extracted["lens_model"],
        extracted["exposure_time"],
        extracted["f_number"],
        extracted["iso"],
        extracted["create_date"],
    ]
    has_exif = any(value not in (None, "") for value in camera_fields)
    has_complete_camera_exif = bool(
        extracted["camera_make"]
        and extracted["camera_model"]
        and (
            extracted["create_date"]
            or extracted["exposure_time"]
            or extracted["f_number"]
            or extracted["iso"]
        )
    )

    metadata_text = _stringify_metadata(raw_metadata)
    ai_hits = _find_keywords(metadata_text, AI_TOOL_KEYWORDS)
    editor_hits = _find_keywords(metadata_text, EDITOR_KEYWORDS)

    signals: list[str] = []
    if ai_hits:
        signals.append(f"AI tool keyword found in metadata: {', '.join(ai_hits)}.")
        risk_score = 80
    elif editor_hits:
        signals.append(f"Editing software keyword found in metadata: {', '.join(editor_hits)}.")
        risk_score = 45
    elif has_complete_camera_exif:
        signals.append("Camera EXIF found with complete camera provenance fields.")
        risk_score = 20
    elif has_exif:
        signals.append("Camera EXIF found, but complete camera provenance fields are missing.")
        risk_score = 45
    else:
        signals.append("No camera EXIF found; provenance is not verifiable from metadata alone.")
        risk_score = 45

    if extracted["software"]:
        signals.append(f"Software metadata field: {extracted['software']}.")

    return {
        "checked": True,
        "has_exif": has_exif,
        "camera_make": extracted["camera_make"],
        "camera_model": extracted["camera_model"],
        "software": extracted["software"],
        "risk_score": risk_score,
        "signals": signals,
        "raw_metadata": raw_metadata,
        "error": None,
    }
