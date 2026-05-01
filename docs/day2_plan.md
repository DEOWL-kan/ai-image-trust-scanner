# Day 2 Plan

## What Changed

Day 2 turns the project into a clearer V0.1 Python CLI baseline while keeping the Day 1 `backend/` implementation as history.

The new primary entry point is:

```bash
python main.py --image data/test_images/example.jpg
```

The new V0.1 core modules are:

- `core/image_loader.py`: validates and reads image file properties.
- `core/metadata_analyzer.py`: reads basic EXIF with Pillow and reserves optional ExifTool/C2PA interfaces.
- `core/forensic_analyzer.py`: computes simple OpenCV/numpy forensic features.
- `core/frequency_analyzer.py`: computes a basic FFT high-frequency energy ratio.
- `core/model_detector.py`: provides a placeholder model interface without training or downloading models.
- `core/score_fusion.py`: combines metadata, forensic, and frequency heuristics into a baseline risk level. Placeholder model output is excluded from scoring.
- `core/report_generator.py`: writes JSON and Markdown reports.

## Why Multi-Evidence Fusion

AI image detection should not rely on one fragile signal.

Missing EXIF, missing C2PA, unusual frequency patterns, smooth texture, or high edge density can all happen for non-AI reasons such as editing, screenshots, compression, resizing, social-media processing, or camera app behavior.

For that reason, V0.1 uses a multi-evidence baseline:

- Metadata is treated as provenance context, not proof.
- Forensic features are treated as weak technical signals.
- Frequency features are treated as weak heuristic signals.
- The deep model detector is placeholder and is not used as trained evidence.
- A future model may influence score fusion only when `model_status` is `active`.

This keeps the project honest and extensible.

## Current Output Language

The V0.1 report should use cautious wording:

- `baseline risk level`
- `heuristic evidence summary`
- `not a final authenticity judgment`

The report must avoid overconfident authenticity claims, final real/fake labels, or wording that implies V0.1 has a trained deep detector.

## Day 3 Next Steps

- Add real fixture images for valid JPEG, valid PNG, empty file, unsupported file, and corrupted image.
- Add tests for report generation and score thresholds.
- Calibrate the score fusion rules using known sample sets.
- Improve metadata extraction with optional ExifTool support.
- Add optional C2PA / Content Credentials parsing.
- Improve Markdown report readability.
- Keep the project local CLI-only until the baseline is stable.

## V0.1 Limitation Note

V0.1 is not a final AI detector. It does not train a model, download model weights, or produce legal/forensic proof. It produces a baseline heuristic risk report for local engineering iteration.
