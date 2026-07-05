from __future__ import annotations

import argparse
import importlib.util
import os
import signal
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_MODEL_MODULES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "transformers": "transformers",
    "safetensors": "safetensors",
    "peft": "peft",
}
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
OPTIONAL_MODEL_DOWNLOAD_HINT = "Smogy ~348MB, Ateeqq ~372MB"


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


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in TRUTHY_ENV_VALUES


def _hf_offline_requested(cli_offline: bool) -> bool:
    return cli_offline or _env_truthy("HF_LOCAL_FILES_ONLY") or _env_truthy("HF_HUB_OFFLINE") or _env_truthy("TRANSFORMERS_OFFLINE")


def _hf_cache_mode_label() -> str:
    if _hf_offline_requested(False):
        return "offline cache only"
    return "online downloads allowed"


def _cpu_safe_defaults() -> None:
    os.environ.setdefault("DETECTOR_RUNTIME_MODE", "stub")
    os.environ.setdefault("DETECTOR_WARMUP_ON_STARTUP", "false")
    os.environ.setdefault("DETECTOR_ALLOW_COLD_MODEL_LOAD", "false")
    os.environ.setdefault("OPEN_SOURCE_DETECTOR_ENABLED", "false")
    os.environ.setdefault("HF_LOCAL_FILES_ONLY", "true")


def _model_mode_defaults(*, offline: bool) -> None:
    os.environ["DETECTOR_RUNTIME_MODE"] = "local_hf"
    os.environ["DETECTOR_WARMUP_ON_STARTUP"] = "true"
    os.environ.setdefault("DETECTOR_ALLOW_COLD_MODEL_LOAD", "false")
    if offline:
        os.environ["HF_LOCAL_FILES_ONLY"] = "true"
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    else:
        os.environ.setdefault("HF_LOCAL_FILES_ONLY", "false")


def _model_warmup_timeout_seconds() -> int:
    raw = os.getenv("MINERVA_MODEL_WARMUP_TIMEOUT_SECONDS", "900")
    try:
        return max(30, int(str(raw).strip()))
    except (TypeError, ValueError):
        return 900


def _format_warmup_failures(result: dict[str, Any]) -> str:
    loaded = result.get("loaded") if isinstance(result, dict) else []
    if not isinstance(loaded, list):
        return "warmup did not return per-detector status"
    failures = [item for item in loaded if isinstance(item, dict) and not bool(item.get("model_loaded"))]
    if not failures:
        return ""
    details = []
    for item in failures:
        detector_id = str(item.get("detector_id") or "unknown")
        error = str(item.get("load_error") or "model was not loaded")
        details.append(f"{detector_id}: {error}")
    return "; ".join(details)


def _warmup_loaded_detector_ids(result: dict[str, Any]) -> list[str]:
    loaded = result.get("loaded") if isinstance(result, dict) else []
    if not isinstance(loaded, list):
        return []
    return [
        str(item.get("detector_id"))
        for item in loaded
        if isinstance(item, dict) and item.get("detector_id") and bool(item.get("model_loaded"))
    ]


def _run_with_signal_timeout(timeout_seconds: int, callback) -> Any:
    if not hasattr(signal, "SIGALRM"):
        return callback()
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(signum, frame) -> None:  # noqa: ARG001
        raise TimeoutError(f"model warmup exceeded {timeout_seconds}s")

    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(timeout_seconds)
    try:
        return callback()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _prewarm_optional_models() -> dict[str, Any]:
    from app.detectors.registry import warmup_local_hf_detectors

    timeout_seconds = _model_warmup_timeout_seconds()
    result = _run_with_signal_timeout(timeout_seconds, warmup_local_hf_detectors)
    failure_details = _format_warmup_failures(result)
    if failure_details:
        raise RuntimeError(failure_details)
    return result


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
    parser.add_argument(
        "--offline",
        action="store_true",
        help="With --with-models, require cached Hugging Face files and do not download missing base models.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _load_dotenv(PROJECT_ROOT / ".env")
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    if args.with_models:
        offline = _hf_offline_requested(args.offline)
        missing = _missing_optional_model_modules()
        if missing:
            print("Optional model mode is not ready.", file=sys.stderr)
            print(f"Missing packages: {', '.join(missing)}", file=sys.stderr)
            print("Install them with: pip install -r requirements-open-source.txt", file=sys.stderr)
            return 2
        _model_mode_defaults(offline=offline)
        if offline:
            print("Optional models: offline cache only; missing Hugging Face weights will be skipped gracefully.", flush=True)
        else:
            print(
                f"Downloading/loading models ({OPTIONAL_MODEL_DOWNLOAD_HINT}); first run may take several minutes...",
                flush=True,
            )
            print("Use --offline to require already-cached model files.", flush=True)
            try:
                warmup_result = _prewarm_optional_models()
            except Exception as exc:  # noqa: BLE001
                print("Optional model warmup failed before the dashboard started.", file=sys.stderr)
                print("The dashboard was not started, so first scans will not silently fall back to unloaded models.", file=sys.stderr)
                print(f"Details: {exc}", file=sys.stderr)
                print("Check your network/Hugging Face access, then retry; or use --offline after the models are cached.", file=sys.stderr)
                return 3
            loaded_ids = ", ".join(_warmup_loaded_detector_ids(warmup_result)) or "no detectors reported"
            print(f"Model warmup complete: {loaded_ids}.", flush=True)
        mode_label = f"optional local model mode ({_hf_cache_mode_label()})"
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
