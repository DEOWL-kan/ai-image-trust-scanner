# Quickstart

AI Image Trust Scanner runs as a local FastAPI app with a browser dashboard.
The default path is lightweight and CPU-safe: it does not require Torch,
Hugging Face downloads, or bundled model weights.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Check Your Environment

```bash
python scripts/doctor.py
```

Optional model dependencies and adapter weights may show as warnings. That is
expected in the default CPU-safe mode.

## Start The Dashboard

```bash
python scripts/run_local_dashboard.py
```

The launcher prints:

```text
Dashboard: http://127.0.0.1:8000/dashboard-ui/index.html
API docs:  http://127.0.0.1:8000/docs
Mode:      lightweight / CPU-safe
```

## Optional Local Model Mode

Optional model mode is opt-in:

```bash
pip install -r requirements-open-source.txt
python scripts/run_local_dashboard.py --with-models
```

This mode may load local Hugging Face models and optional PEFT/LoRA adapters.
If optional packages are missing, the launcher prints a clear error and exits
without crashing.

## What Results Mean

Results are risk signals for review, not legal or forensic conclusions. Absence
of AI evidence does not prove authenticity. Suspicious evidence should trigger
review, not automatic enforcement.
