# Contributing

Thanks for helping improve AI Image Trust Scanner.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
pytest tests -q -m "not hf and not torch and not local_data and not legacy"
```

## Default Runtime Contract

The default path must remain lightweight and CPU-safe:

- no required Torch install
- no required Hugging Face downloads
- no bundled private datasets or generated report history
- optional model failures must degrade gracefully

## Pull Request Expectations

- Keep changes scoped.
- Add or update tests for behavior changes.
- Do not add private images, generated reports, local absolute paths, or model
  weights.
- Do not claim legal or forensic certainty.
- Disclose detector/model sources honestly in docs.

## Optional Model Work

Mark tests requiring optional model dependencies with `@pytest.mark.hf` or
`@pytest.mark.torch`. CI excludes these by default.
