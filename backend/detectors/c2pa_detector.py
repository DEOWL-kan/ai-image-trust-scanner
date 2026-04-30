from __future__ import annotations

import subprocess
from typing import Any


MANIFEST_KEYWORDS = ["manifest", "claim", "assertions", "assertion", "signature", "ingredients"]
NO_MANIFEST_KEYWORDS = [
    "no claim found",
    "no manifest",
    "manifest not found",
]
INVALID_KEYWORDS = [
    "invalid",
    "failed",
    "signature error",
    "validation error",
]


def _tool_missing_result() -> dict[str, Any]:
    return {
        "checked": False,
        "has_manifest": None,
        "valid_signature": None,
        "risk_score": 20,
        "signals": ["C2PA check skipped because neither c2patool nor c2pa is available."],
        "raw_output": "",
        "error": "c2patool and c2pa are not installed or not available in PATH.",
    }


def _run_c2pa_tool(tool_name: str, image_path: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            [tool_name, image_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return None


def analyze_c2pa(image_path: str) -> dict[str, Any]:
    try:
        completed = _run_c2pa_tool("c2patool", image_path)
        tool_used = "c2patool"
        if completed is None:
            completed = _run_c2pa_tool("c2pa", image_path)
            tool_used = "c2pa"

        if completed is None:
            return _tool_missing_result()

        raw_output = "\n".join(
            part.strip()
            for part in [completed.stdout, completed.stderr]
            if part and part.strip()
        )
        output_lower = raw_output.lower()

        if any(keyword in output_lower for keyword in NO_MANIFEST_KEYWORDS):
            return {
                "checked": True,
                "has_manifest": False,
                "valid_signature": None,
                "risk_score": 40,
                "signals": ["No C2PA manifest or claim found. Provenance cannot be verified."],
                "raw_output": raw_output,
                "error": None,
            }

        has_manifest = any(keyword in output_lower for keyword in MANIFEST_KEYWORDS)
        has_invalid_signal = any(keyword in output_lower for keyword in INVALID_KEYWORDS)

        valid_signature = None
        if has_manifest:
            valid_signature = not has_invalid_signal

        signals: list[str] = [f"C2PA tool used: {tool_used}."]
        if has_manifest and valid_signature:
            risk_score = 10
            signals.append("C2PA manifest found and no validation failure was reported.")
        elif has_manifest:
            risk_score = 65
            signals.append("C2PA manifest-like data found, but validation appears to have failed.")
        else:
            risk_score = 40
            signals.append("No C2PA manifest found; provenance is not verifiable from C2PA alone.")

        return {
            "checked": True,
            "has_manifest": has_manifest,
            "valid_signature": valid_signature,
            "risk_score": risk_score,
            "signals": signals,
            "raw_output": raw_output,
            "error": None if completed.returncode == 0 or raw_output else "C2PA tool returned no output.",
        }
    except Exception as exc:
        return {
            "checked": False,
            "has_manifest": None,
            "valid_signature": None,
            "risk_score": 20,
            "signals": ["C2PA check failed unexpectedly."],
            "raw_output": "",
            "error": str(exc),
        }
