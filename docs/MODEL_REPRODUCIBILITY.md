# Model Reproducibility

This repository defaults to a CPU-safe `stub` runtime and does not ship tuned
adapter weights in v1. Optional model mode is documented for users who can
legally obtain and run the underlying models and any local adapters.

## Runtime Modes

### CPU-Safe Default

```bash
python scripts/run_local_dashboard.py
```

Default environment:

```text
DETECTOR_RUNTIME_MODE=stub
DETECTOR_WARMUP_ON_STARTUP=false
DETECTOR_ALLOW_COLD_MODEL_LOAD=false
OPEN_SOURCE_DETECTOR_ENABLED=false
```

In this mode, Hugging Face detectors are reported as skipped and the product
uses the local lightweight baseline, metadata, provenance, forensic heuristics,
policy rules, and review/report workflows.

### Optional Local HF Mode

```bash
pip install -r requirements-open-source.txt
python scripts/run_local_dashboard.py --with-models
```

By default, `--with-models` allows the first run to download the configured
Smogy and Ateeqq base models from Hugging Face into your local HF cache. Use
cached-only mode when you are offline or want to prevent network access:

```bash
python scripts/run_local_dashboard.py --with-models --offline
```

See [Download Sizes, Memory, and Hardware](#download-sizes-memory-and-hardware)
before opting into model mode.

Optional dependencies:

- `torch`
- `torchvision`
- `transformers`
- `safetensors`
- `peft`

Optional adapter configuration:

```bash
export SMOGY_PEFT_ADAPTER=/absolute/path/to/ft_smogy_lora_v2
python scripts/run_local_dashboard.py --with-models
```

## Configured Detector Sources

The public configuration currently names these detector sources in
`configs/detectors.yaml`:

| detector_id | Role | Source / model ID | Public v1 default |
| --- | --- | --- | --- |
| `smogy` | primary | `Smogy/SMOGY-Ai-images-detector` | skipped in `stub` mode |
| `ateeqq` | secondary | `Ateeqq/ai-vs-human-image-detector` | skipped in `stub` mode |
| `legacy` | baseline | `lightweight-baseline.no-pretrained` | active |
| `dima806` | diagnostic | `dima806/ai_vs_real_image_detection` | disabled unless explicitly enabled |
| `capcheck` | disabled duplicate | `capcheck/ai-image-detection` | disabled |

## Download Sizes, Memory, and Hardware

Nothing below is bundled in the repository. The clone is ~5 MB of code; model
weights are downloaded from Hugging Face only if you opt into model mode.

### Per-model download size (inference weights)

| Model | Role | Download | Architecture |
| --- | --- | --- | --- |
| `Smogy/SMOGY-Ai-images-detector` | primary | **~348 MB** | Swin |
| `Ateeqq/ai-vs-human-image-detector` | secondary | **~372 MB** | SigLIP |
| `dima806/ai_vs_real_image_detection` | diagnostic (off by default, not recommended) | **~343 MB** | ViT |
| `ft_smogy_lora_v2` adapter | optional fine-tune (**not shipped in v1**) | ~1.5 MB | LoRA on Smogy |

> The `dima806` Hugging Face repo *appears* to be ~4.8 GB because it stores four
> training checkpoints with optimizer state. Inference only downloads the single
> `model.safetensors` (~343 MB) — you do not need the checkpoints.

### Total footprint by scenario

| Scenario | What you install | Disk total | Runtime RAM |
| --- | --- | --- | --- |
| **CPU-safe default** (no models) | repo + `requirements.txt` (numpy/opencv/fastapi…) | **~200 MB** | ~200–400 MB |
| **Smogy only** | + Smogy weights + Torch stack | **~0.8–1 GB** | ~1–1.5 GB |
| **Recommended** (Smogy + Ateeqq) | + both weights (~720 MB) + Torch stack (~300–500 MB) | **~1.2–1.4 GB** | **~1.5–2.5 GB** |

### Hardware

- **No GPU required.** Everything runs on CPU. Model mode is slower — expect p50
  ≈ 1.1 s and p95 up to 8–10 s per image on large inputs.
- Default CPU-safe mode has no Torch/Hugging Face dependency at all.

*Code/model file sizes are exact (measured from Hugging Face); Python package and
RAM figures are approximate and vary by platform.*

## Revisions

No immutable Hugging Face model revisions are pinned in the public v1
configuration. Reproducible optional model runs require pinning model revisions
locally before comparing metrics or publishing claims.

Recommended local tracking fields:

- Base model ID
- Base model revision or commit SHA
- Adapter path and checksum
- `transformers`, `torch`, and `peft` versions
- Runtime device and preprocessing settings
- Policy profile and thresholds

## Adapter Status

The private research archive used an optional Smogy PEFT/LoRA adapter path:

```text
models/ft_smogy_lora_v2
```

That adapter is not shipped in public v1 because redistribution of model and
training-data-derived weights must pass license review first. Users who have a
lawful adapter copy can point `SMOGY_PEFT_ADAPTER` at it.

## What Was Tuned

The private research archive contains tuning work around:

- policy thresholds and policy profiles in `configs/policy_config.yaml`
- review routing profiles in `configs/review_trigger_config.yaml`
- optional Smogy LoRA adapter experiments
- held-out evaluation reports and replay artifacts

The public v1 repository includes the policy configuration and lightweight
default path, but not the private/generated report history or adapter weights.

## What Was Not Tuned In Public v1

- No public v1 adapter weights are bundled.
- No public v1 claim is made that the repository trains or owns the named base
  detector models.
- The default lightweight baseline is not a trained deep detector.
- Optional model results are not reproducible unless users pin model revisions
  and document local adapter checksums.

## Known Limitations

- Detector outputs are evidence for review, not proof of authenticity.
- Missing C2PA or EXIF metadata does not prove an image is AI-generated.
- Optional Hugging Face models may change unless revisions are pinned.
- Optional adapters may be subject to separate model and dataset licenses.
- Thresholds reflect product-risk routing preferences, not universal truth.
