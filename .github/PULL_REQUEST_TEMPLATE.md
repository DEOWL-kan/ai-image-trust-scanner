## Summary

## Testing

- [ ] `pytest tests -q -m "not hf and not torch and not local_data and not legacy"`
- [ ] `python scripts/doctor.py`

## Checklist

- [ ] Default path remains CPU-safe and does not require Torch/Hugging Face packages.
- [ ] No private images, datasets, secrets, generated reports, or local paths were added.
- [ ] Detector/source claims are honest and do not imply legal or forensic certainty.
- [ ] Documentation was updated when user-facing behavior changed.
