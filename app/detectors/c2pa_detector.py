from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


MANIFEST_KEYWORDS = ["manifest", "claim", "assertions", "assertion", "signature", "ingredients"]
NO_MANIFEST_KEYWORDS = ["no claim found", "no manifest", "manifest not found"]
INVALID_KEYWORDS = ["invalid", "failed", "signature error", "validation error"]
OPENAI_KEYWORDS = ["openai", "chatgpt", "dall-e", "dalle", "gpt image", "gpt-image", "gpt_image"]
DEFAULT_TIMEOUT_SECONDS = 10
C2PATOOL_INFO_CACHE: dict[tuple[str | None, int], dict[str, Any]] = {}
CLAIM_CBOR_DECODE_ERROR = "claim could not be converted from cbor"
OLD_C2PATOOL_VERSION = (0, 9, 12)
BINARY_C2PA_MARKERS = [b"c2pa", b"C2PA", b"jumbf", b"claim", b"manifest"]
BINARY_OPENAI_MARKERS = [b"OpenAI", b"ChatGPT", b"DALL-E"]
BINARY_GPT_IMAGE_MARKERS = [b"gpt-image", b"GPT Image", b"gpt_image"]
BINARY_MARKER_KEYWORDS = [*BINARY_C2PA_MARKERS, *BINARY_OPENAI_MARKERS, *BINARY_GPT_IMAGE_MARKERS]


def _preview(value: str | None, limit: int = 500) -> str:
    return (value or "")[:limit]


def _parse_version_tuple(text: str | None) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _upgrade_recommended(version: str | None, source: str) -> bool:
    if source == "missing":
        return True
    parsed = _parse_version_tuple(version)
    if parsed is None:
        return False
    return parsed <= OLD_C2PATOOL_VERSION


def get_c2patool_info(timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    env_path = os.environ.get("C2PATOOL_PATH")
    cache_key = (env_path, int(timeout))
    cached = C2PATOOL_INFO_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    if env_path:
        tool_path = env_path
        source = "env"
    else:
        resolved = shutil.which("c2patool")
        tool_path = resolved
        source = "path" if resolved else "missing"

    version = None
    if tool_path:
        try:
            completed = subprocess.run(
                [tool_path, "--version"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            version = (completed.stdout or completed.stderr or "").strip() or None
        except FileNotFoundError:
            source = "missing" if source != "env" else "env"
        except Exception as exc:
            version = f"version_check_failed: {exc}"

    executable = tool_path or "c2patool"
    info = {
        "c2patool_version": version,
        "c2patool_path": tool_path,
        "c2patool_source": source,
        "c2patool_upgrade_recommended": _upgrade_recommended(version, source),
        "c2patool_command_examples": [
            f'"{executable}" <image_path>',
            f'"{executable}" --info <image_path>',
            f'"{executable}" -d <image_path>',
        ],
    }
    C2PATOOL_INFO_CACHE[cache_key] = dict(info)
    return info


def _base_provenance(
    *,
    c2pa_present: bool,
    c2pa_readable: bool,
    c2pa_valid: bool | None,
    c2pa_issuer: str | None,
    c2pa_generator: str | None,
    openai_provenance_detected: bool,
    confidence: str,
    probe_status: str,
    user_note: str,
    c2patool_info: dict[str, Any],
    returncode: int | None = None,
    stdout_preview: str | None = None,
    stderr_preview: str | None = None,
    error: str | None = None,
    error_detail: str | None = None,
    raw_manifest_path: str | None = None,
    marker_scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    markers = marker_scan or {}
    return {
        "verified": {
            "c2pa_present": c2pa_present,
            "c2pa_readable": c2pa_readable,
            "c2pa_valid": c2pa_valid,
            "c2pa_issuer": c2pa_issuer,
            "c2pa_generator": c2pa_generator,
            "openai_provenance_detected": openai_provenance_detected,
            "confidence": confidence,
        },
        "unverified_markers": {
            "binary_c2pa_marker_found": bool(markers.get("binary_c2pa_marker_found")),
            "binary_openai_marker_found": bool(markers.get("binary_openai_marker_found")),
            "binary_gpt_image_marker_found": bool(markers.get("binary_gpt_image_marker_found")),
            "marker_confidence": "weak"
            if any(
                bool(markers.get(key))
                for key in (
                    "binary_c2pa_marker_found",
                    "binary_openai_marker_found",
                    "binary_gpt_image_marker_found",
                )
            )
            else "none",
            "used_for_final_decision": False,
            "marker_offsets_preview": markers.get("marker_offsets_preview") or [],
        },
        "diagnostics": {
            "c2pa_probe_status": probe_status,
            "c2patool_version": c2patool_info.get("c2patool_version"),
            "c2patool_path": c2patool_info.get("c2patool_path"),
            "c2patool_source": c2patool_info.get("c2patool_source"),
            "c2patool_upgrade_recommended": c2patool_info.get("c2patool_upgrade_recommended"),
            "c2patool_returncode": returncode,
            "raw_manifest_path": raw_manifest_path,
            "error": error,
            "error_detail": error_detail,
            "stdout_preview": stdout_preview,
            "stderr_preview": stderr_preview,
        },
        "user_note": user_note,
    }


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


def _run_command(command: list[str], timeout: int = DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return None


def _run_c2pa_tool(
    tool_name: str,
    image_path: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str] | None:
    return _run_command([tool_name, image_path], timeout=timeout)


def analyze_c2pa(image_path: str) -> dict[str, Any]:
    try:
        completed = _run_c2pa_tool("c2patool", image_path)
        tool_used = "c2patool"
        if completed is None:
            completed = _run_c2pa_tool("c2pa", image_path)
            tool_used = "c2pa"
        if completed is None:
            return _tool_missing_result()
        raw_output = _combined_output(completed)
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
        valid_signature = None if not has_manifest else not has_invalid_signal
        signals = [f"C2PA tool used: {tool_used}."]
        risk_score = 10 if has_manifest and valid_signature else 65 if has_manifest else 40
        signals.append(
            "C2PA manifest found and no validation failure was reported."
            if has_manifest and valid_signature
            else "C2PA manifest-like data found, but validation appears to have failed."
            if has_manifest
            else "No C2PA manifest found; provenance is not verifiable from C2PA alone."
        )
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


def _combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part and part.strip())


def _parse_json_output(text: str) -> Any:
    if not text:
        raise json.JSONDecodeError("empty C2PA output", text, 0)
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def c2pa_stdout_parses_as_json(text: str) -> bool:
    try:
        _parse_json_output(text)
        return True
    except Exception:
        return False


def _stringify(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _walk_values(value: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(value, dict):
        for item in value.values():
            values.append(item)
            values.extend(_walk_values(item))
    elif isinstance(value, list):
        for item in value:
            values.append(item)
            values.extend(_walk_values(item))
    return values


def _first_string_for_keys(value: Any, key_patterns: tuple[str, ...]) -> str | None:
    if not isinstance(value, dict):
        return None
    lowered_patterns = tuple(pattern.lower() for pattern in key_patterns)
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, item in current.items():
                key_text = str(key).lower()
                if any(pattern in key_text for pattern in lowered_patterns) and isinstance(item, (str, int, float)):
                    text = str(item).strip()
                    if text:
                        return text
                if isinstance(item, (dict, list)):
                    stack.append(item)
        elif isinstance(current, list):
            stack.extend(item for item in current if isinstance(item, (dict, list)))
    return None


def _extract_validity(parsed: Any, output_lower: str) -> bool | None:
    if any(keyword in output_lower for keyword in INVALID_KEYWORDS):
        return False
    if not isinstance(parsed, dict):
        return None
    text = _stringify(parsed).lower()
    if any(keyword in text for keyword in INVALID_KEYWORDS):
        return False
    for value in _walk_values(parsed):
        if isinstance(value, bool):
            continue
        text_value = str(value).strip().lower()
        if text_value in {"valid", "trusted", "verified"}:
            return True
        if text_value in {"invalid", "untrusted", "failed"}:
            return False
    return True


def _safe_manifest_name(image_path: str) -> str:
    path = Path(image_path)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "image"
    suffix = re.sub(r"[^A-Za-z0-9]+", "", path.suffix.lower().lstrip(".")) or "img"
    return f"{stem}_{suffix}_c2pa_manifest.json"


def _safe_debug_stem(image_path: str) -> str:
    path = Path(image_path)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "image"
    suffix = re.sub(r"[^A-Za-z0-9]+", "", path.suffix.lower().lstrip(".")) or "img"
    return f"{stem}_{suffix}"


def _save_manifest(raw_text: str, image_path: str, manifest_dir: str | Path | None) -> str | None:
    if not raw_text or manifest_dir is None:
        return None
    try:
        output_dir = Path(manifest_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / _safe_manifest_name(image_path)
        target.write_text(raw_text, encoding="utf-8")
        return str(target.resolve())
    except OSError:
        return None


def _save_probe_debug(
    *,
    image_path: str,
    debug_dir: str | Path | None,
    command: list[str],
    returncode: int | None,
    stdout: str,
    stderr: str,
) -> None:
    if debug_dir is None:
        return
    try:
        output_dir = Path(debug_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = _safe_debug_stem(image_path)
        (output_dir / f"stdout_{stem}.txt").write_text(stdout or "", encoding="utf-8")
        (output_dir / f"stderr_{stem}.txt").write_text(stderr or "", encoding="utf-8")
        metadata = {"command": command, "returncode": returncode, "image_path": image_path}
        (output_dir / f"probe_{stem}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError:
        return


def scan_binary_markers(image_path: str | Path, *, max_offsets: int = 20) -> dict[str, Any]:
    try:
        data = Path(image_path).read_bytes()
    except OSError as exc:
        return {
            "binary_c2pa_marker_found": False,
            "binary_openai_marker_found": False,
            "binary_gpt_image_marker_found": False,
            "marker_offsets_preview": [],
            "binary_marker_error": str(exc),
        }

    offsets: list[str] = []
    for marker in BINARY_MARKER_KEYWORDS:
        start = 0
        while len(offsets) < max_offsets:
            index = data.find(marker, start)
            if index < 0:
                break
            offsets.append(f"{marker.decode('utf-8', errors='replace')}@{index}")
            start = index + 1
    return {
        "binary_c2pa_marker_found": any(data.find(marker) >= 0 for marker in BINARY_C2PA_MARKERS),
        "binary_openai_marker_found": any(data.find(marker) >= 0 for marker in BINARY_OPENAI_MARKERS),
        "binary_gpt_image_marker_found": any(data.find(marker) >= 0 for marker in BINARY_GPT_IMAGE_MARKERS),
        "marker_offsets_preview": offsets,
        "binary_marker_error": None,
    }


def analyze_c2pa_provenance(
    image_path: str | Path,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    manifest_dir: str | Path | None = None,
    debug_dir: str | Path | None = None,
) -> dict[str, Any]:
    image_text = str(image_path)
    marker_scan = scan_binary_markers(image_path)
    tool_info = get_c2patool_info(timeout=timeout)
    tool_path = tool_info.get("c2patool_path")
    command = [tool_path or "c2patool", image_text]
    if not tool_path:
        _save_probe_debug(
            image_path=image_text,
            debug_dir=debug_dir,
            command=command,
            returncode=None,
            stdout="",
            stderr="c2patool is not installed or not available.",
        )
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="tool_error",
            user_note="C2PA metadata could not be checked because c2patool is not installed or not available.",
            c2patool_info=tool_info,
            stderr_preview="c2patool is not installed or not available.",
            error="c2patool_missing",
            error_detail="Set C2PATOOL_PATH or add c2patool to PATH.",
            marker_scan=marker_scan,
        )

    try:
        completed = _run_command(command, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        _save_probe_debug(
            image_path=image_text,
            debug_dir=debug_dir,
            command=command,
            returncode=None,
            stdout=stdout,
            stderr=stderr,
        )
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="timeout",
            user_note="C2PA metadata could not be checked because c2patool timed out.",
            c2patool_info=tool_info,
            stdout_preview=_preview(stdout),
            stderr_preview=_preview(stderr),
            error=f"c2patool timed out after {timeout} seconds.",
            error_detail=str(exc),
            marker_scan=marker_scan,
        )

    if completed is None:
        _save_probe_debug(
            image_path=image_text,
            debug_dir=debug_dir,
            command=command,
            returncode=None,
            stdout="",
            stderr="c2patool is not installed or not executable.",
        )
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="tool_error",
            user_note="C2PA metadata could not be checked because c2patool is not installed or not executable.",
            c2patool_info=tool_info,
            stderr_preview="c2patool is not installed or not executable.",
            error="c2patool_missing",
            error_detail="FileNotFoundError while executing c2patool.",
            marker_scan=marker_scan,
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    _save_probe_debug(
        image_path=image_text,
        debug_dir=debug_dir,
        command=command,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    raw_output = _combined_output(completed)
    output_lower = raw_output.lower()
    raw_manifest_path = _save_manifest(raw_output, image_text, manifest_dir)
    stdout_preview = _preview(stdout)
    stderr_preview = _preview(stderr)

    if any(keyword in output_lower for keyword in NO_MANIFEST_KEYWORDS):
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=True,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unknown",
            probe_status="no_manifest",
            user_note="No readable C2PA metadata was found. Absence of C2PA is not evidence of authenticity.",
            c2patool_info=tool_info,
            returncode=completed.returncode,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            raw_manifest_path=raw_manifest_path,
            marker_scan=marker_scan,
        )

    if CLAIM_CBOR_DECODE_ERROR in output_lower:
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="claim_cbor_decode_error",
            user_note="C2PA-related data may be present, but the claim could not be decoded by the local c2patool version. This is not verified provenance.",
            c2patool_info=tool_info,
            returncode=completed.returncode,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            error="claim_cbor_decode_error",
            error_detail=stderr.strip() or raw_output.strip(),
            raw_manifest_path=raw_manifest_path,
            marker_scan=marker_scan,
        )

    if not stdout.strip():
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="stdout_empty",
            user_note="c2patool produced no JSON stdout, so no readable C2PA manifest was parsed.",
            c2patool_info=tool_info,
            returncode=completed.returncode,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            error="stdout_empty",
            error_detail=stderr.strip() or "c2patool stdout was empty.",
            raw_manifest_path=raw_manifest_path,
            marker_scan=marker_scan,
        )

    try:
        parsed = _parse_json_output(stdout)
    except json.JSONDecodeError as exc:
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=False,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unavailable",
            probe_status="stdout_not_json",
            user_note="c2patool stdout was not valid JSON, so no readable C2PA manifest was parsed.",
            c2patool_info=tool_info,
            returncode=completed.returncode,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            error="stdout_not_json",
            error_detail=f"Could not parse c2patool JSON stdout: {exc}. stderr: {stderr.strip()}",
            raw_manifest_path=raw_manifest_path,
            marker_scan=marker_scan,
        )

    parsed_text = _stringify(parsed)
    parsed_lower = parsed_text.lower()
    has_manifest = any(keyword in parsed_lower for keyword in MANIFEST_KEYWORDS) or bool(parsed)
    if not has_manifest:
        return _base_provenance(
            c2pa_present=False,
            c2pa_readable=True,
            c2pa_valid=None,
            c2pa_issuer=None,
            c2pa_generator=None,
            openai_provenance_detected=False,
            confidence="unknown",
            probe_status="no_manifest",
            user_note="No readable C2PA metadata was found. Absence of C2PA is not evidence of authenticity.",
            c2patool_info=tool_info,
            returncode=completed.returncode,
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            raw_manifest_path=raw_manifest_path,
            marker_scan=marker_scan,
        )

    generator = _first_string_for_keys(parsed, ("generator", "claim_generator", "software", "app", "tool", "name"))
    issuer = _first_string_for_keys(parsed, ("issuer", "signature_issuer", "cert", "organization", "org"))
    openai_hit = any(keyword in parsed_lower for keyword in OPENAI_KEYWORDS)
    valid = _extract_validity(parsed, output_lower)
    return _base_provenance(
        c2pa_present=True,
        c2pa_readable=True,
        c2pa_valid=valid,
        c2pa_issuer=issuer,
        c2pa_generator=generator,
        openai_provenance_detected=openai_hit,
        confidence="high" if openai_hit else "unknown",
        probe_status="parsed",
        user_note=(
            "Verified OpenAI-related C2PA provenance metadata was detected."
            if openai_hit
            else "Readable C2PA provenance metadata was detected."
        ),
        c2patool_info=tool_info,
        returncode=completed.returncode,
        stdout_preview=stdout_preview,
        stderr_preview=stderr_preview,
        error_detail=stderr.strip() or None,
        raw_manifest_path=raw_manifest_path,
        marker_scan=marker_scan,
    )
