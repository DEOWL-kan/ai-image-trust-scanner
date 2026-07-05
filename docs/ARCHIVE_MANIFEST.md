# Archive Manifest

This public repository is a curated product release, not a dump of the private
research workspace.

## Removed From Public v1

- `reports/`: generated benchmark reports, screenshots, policy replay outputs,
  debug manifests, and local review artifacts.
- `data/`: private/local datasets, generated indexes, fine-tuning manifests,
  review manifests, benchmark outputs, and local app databases.
- `outputs/`: local API history and generated HTML reports.
- `archive/`: frozen historical code.
- `tools/`: research/debug utilities not required for the default product path.
- Most `scripts/`: DayXX research scripts and dataset/evaluation runners.
- `models/ft_smogy_lora_v2/` weights: not redistributed until license review
  clears the base model, training data, and adapter derivatives.

## Why These Were Removed

- Keep clone size small.
- Avoid leaking private paths, generated reports, or review artifacts.
- Avoid redistributing datasets or model derivatives without license review.
- Present a clear local dashboard product surface for new users.

## What Remains

- FastAPI product app under `app/`.
- Local dashboard under `frontend/dashboard/`.
- Runtime and policy configs under `configs/`.
- Tiny public fixtures under `examples/`.
- Default lightweight test suite under `tests/`.
- Supported local scripts under `scripts/`.

## How To Recover Historical Artifacts

Historical research artifacts remain in the private research archive. They may
be published later as release assets, a Hugging Face Dataset, or separate
documentation only after privacy, size, and license review.

Do not infer benchmark claims from missing private artifacts. Public claims must
be backed by reproducible public evidence.
