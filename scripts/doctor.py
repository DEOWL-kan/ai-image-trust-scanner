from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_MODULES = {
    "Pillow": "PIL",
    "numpy": "numpy",
    "opencv-python": "cv2",
    "fastapi": "fastapi",
    "httpx": "httpx",
    "uvicorn": "uvicorn",
    "python-multipart": "multipart",
    "pandas": "pandas",
    "PyYAML": "yaml",
    "requests": "requests",
}
OPTIONAL_MODEL_MODULES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "transformers": "transformers",
    "safetensors": "safetensors",
    "peft": "peft",
}
REQUIRED_CONFIGS = [
    "configs/detectors.yaml",
    "configs/policy_config.yaml",
    "configs/review_trigger_config.yaml",
    "configs/detector_weights.json",
]


def _status_line(status: str, name: str, detail: str) -> str:
    return f"[{status}] {name}: {detail}"


def _find_module(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _runtime_mode() -> str:
    mode = str(os.getenv("DETECTOR_RUNTIME_MODE", "stub")).strip().lower()
    return mode if mode in {"stub", "local_hf", "disabled"} else "stub"


def _load_detector_config() -> dict[str, Any]:
    if not _find_module("yaml"):
        return {}
    import yaml

    path = PROJECT_ROOT / "configs" / "detectors.yaml"
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _configured_adapter_path() -> str:
    env_adapter = str(os.getenv("SMOGY_PEFT_ADAPTER", "")).strip()
    if env_adapter:
        return env_adapter
    config = _load_detector_config()
    detectors = config.get("detectors") if isinstance(config.get("detectors"), list) else []
    for item in detectors:
        if isinstance(item, dict) and item.get("detector_id") == "smogy":
            return str(item.get("peft_adapter_path") or "").strip()
    return ""


def _tmp_writable() -> tuple[bool, str]:
    tmp_dir = PROJECT_ROOT / ".tmp"
    probe = tmp_dir / "doctor_write_test.tmp"
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, str(tmp_dir)
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    failures = 0
    warnings = 0
    lines: list[str] = []

    version = sys.version_info
    version_text = platform.python_version()
    if version >= (3, 10):
        lines.append(_status_line("PASS", "python", f"{version_text}"))
    else:
        failures += 1
        lines.append(_status_line("FAIL", "python", f"{version_text}; Python 3.10+ is required"))

    for package, module in CORE_MODULES.items():
        if _find_module(module):
            lines.append(_status_line("PASS", f"core dependency {package}", "installed"))
        else:
            failures += 1
            lines.append(_status_line("FAIL", f"core dependency {package}", "missing"))

    mode = _runtime_mode()
    lines.append(_status_line("PASS", "runtime mode", mode))
    warmup = str(os.getenv("DETECTOR_WARMUP_ON_STARTUP", "false")).strip().lower()
    lines.append(_status_line("PASS", "startup warmup", warmup))

    for package, module in OPTIONAL_MODEL_MODULES.items():
        if _find_module(module):
            lines.append(_status_line("PASS", f"optional model dependency {package}", "installed"))
        else:
            warnings += 1
            lines.append(_status_line("WARN", f"optional model dependency {package}", "missing"))

    adapter_value = _configured_adapter_path()
    if adapter_value:
        adapter_path = Path(adapter_value)
        if not adapter_path.is_absolute():
            adapter_path = PROJECT_ROOT / adapter_path
        if adapter_path.exists():
            lines.append(_status_line("PASS", "optional Smogy adapter", str(adapter_path)))
        else:
            warnings += 1
            lines.append(_status_line("WARN", "optional Smogy adapter", f"configured but not found: {adapter_path}"))
    else:
        warnings += 1
        lines.append(_status_line("WARN", "optional Smogy adapter", "not configured; CPU-safe stub mode is still usable"))

    for relative in REQUIRED_CONFIGS:
        path = PROJECT_ROOT / relative
        if path.is_file():
            lines.append(_status_line("PASS", relative, "found"))
        else:
            failures += 1
            lines.append(_status_line("FAIL", relative, "missing"))

    frontend = PROJECT_ROOT / "frontend" / "dashboard" / "index.html"
    if frontend.is_file():
        lines.append(_status_line("PASS", "dashboard frontend", "frontend/dashboard/index.html found"))
    else:
        failures += 1
        lines.append(_status_line("FAIL", "dashboard frontend", "frontend/dashboard/index.html missing"))

    writable, detail = _tmp_writable()
    if writable:
        lines.append(_status_line("PASS", ".tmp writable", detail))
    else:
        failures += 1
        lines.append(_status_line("FAIL", ".tmp writable", detail))

    print("AI Image Trust Scanner Doctor")
    print(f"Project: {PROJECT_ROOT}")
    for line in lines:
        print(line)
    print(f"Summary: {failures} fail, {warnings} warn")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
