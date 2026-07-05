# Open Source Release Checklist

## Repository Shape

- [ ] No `.git` history from the private research archive.
- [ ] No `reports/`, `data/`, `outputs/`, `.tmp/`, `.venv/`, `archive/`, or
      research script dump.
- [ ] No private images, generated report history, or unlicensed datasets.
- [ ] No bundled adapter weights unless license review passes.

## Runtime

- [ ] `python scripts/doctor.py` exits 0.
- [ ] `python scripts/run_local_dashboard.py` starts in CPU-safe mode.
- [ ] `/health` returns 200.
- [ ] `/dashboard-ui/index.html` returns 200.
- [ ] Optional model dependency failures are warnings or friendly errors, not
      crashes.

## Tests And CI

- [ ] `pytest tests -q -m "not hf and not torch and not local_data and not legacy"` passes.
- [ ] GitHub Actions runs on Python 3.11.
- [ ] CI installs only `requirements.txt`.

## Documentation

- [ ] README uses honest positioning and links to quickstart.
- [ ] Model/source names are disclosed in docs.
- [ ] Limitations state that results are review signals, not proof.
- [ ] `docs/MODEL_REPRODUCIBILITY.md` is current.
- [ ] `docs/ARCHIVE_MANIFEST.md` explains removed artifacts.

## Final Gate

- [ ] Secret scan completed.
- [ ] Large-file scan completed.
- [ ] License review completed for dependencies, assets, and optional models.
- [ ] User explicitly approves public push.
