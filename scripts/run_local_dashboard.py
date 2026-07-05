from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_MODEL_MODULES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "transformers": "transformers",
    "safetensors": "safetensors",
    "peft": "peft",
}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _module_missing(module: str) -> bool:
    return importlib.util.find_spec(module) is None


def _missing_optional_model_modules() -> list[str]:
    return [
        package_name
        for package_name, module_name in OPTIONAL_MODEL_MODULES.items()
        if _module_missing(module_name)
    ]


def _cpu_safe_defaults() -> None:
    os.environ.setdefault("DETECTOR_RUNTIME_MODE", "stub")
    os.environ.setdefault("DETECTOR_WARMUP_ON_STARTUP", "false")
    os.environ.setdefault("DETECTOR_ALLOW_COLD_MODEL_LOAD", "false")
    os.environ.setdefault("OPEN_SOURCE_DETECTOR_ENABLED", "false")
    os.environ.setdefault("HF_LOCAL_FILES_ONLY", "true")


def _model_mode_defaults() -> None:
    os.environ["DETECTOR_RUNTIME_MODE"] = "local_hf"
    os.environ.setdefault("DETECTOR_WARMUP_ON_STARTUP", "true")
    os.environ.setdefault("DETECTOR_ALLOW_COLD_MODEL_LOAD", "false")
    os.environ.setdefault("HF_LOCAL_FILES_ONLY", "true")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the local AI Image Trust Scanner dashboard."
    )
    parser.add_argument("--host", default=os.getenv("MINERVA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MINERVA_PORT", "8000")))
    parser.add_argument(
        "--with-models",
        action="store_true",
        help="Enable optional local Hugging Face model mode. Requires requirements-open-source.txt.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _load_dotenv(PROJECT_ROOT / ".env")
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    if args.with_models:
        missing = _missing_optional_model_modules()
        if missing:
            print("Optional model mode is not ready.", file=sys.stderr)
            print(f"Missing packages: {', '.join(missing)}", file=sys.stderr)
            print("Install them with: pip install -r requirements-open-source.txt", file=sys.stderr)
            return 2
        _model_mode_defaults()
        mode_label = "optional local model mode"
    else:
        _cpu_safe_defaults()
        mode_label = "lightweight / CPU-safe"

    host = str(args.host)
    port = int(args.port)
    base_url = f"http://{host}:{port}"
    print(f"Dashboard: {base_url}/dashboard-ui/index.html", flush=True)
    print(f"API docs:  {base_url}/docs", flush=True)
    print(f"Mode:      {mode_label}", flush=True)

    try:
        import uvicorn
    except Exception as exc:
        print(f"Cannot start dashboard because uvicorn is unavailable: {exc}", file=sys.stderr)
        print("Install core dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 1

    uvicorn.run("app.main:app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
