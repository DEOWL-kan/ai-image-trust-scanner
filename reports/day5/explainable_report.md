# Day5 Explainable Image Feature Report

This report provides feature-based signals that can assist AI image detection. It is not an absolute authenticity judgment.

## Summary

- Generated at: 2026-05-01T19:10:29+08:00
- Input path: `D:\ai image\ai-image-trust-scanner\data\test_images`
- Output path: `D:\ai image\ai-image-trust-scanner\reports\day5`
- Total supported images: 20
- Processed images: 20
- Errors: 0
- Average risk score: 45.95
- Likely real: 0
- Uncertain: 19
- Likely AI: 1

## Scan Details

- Input directory scanned: `D:\ai image\ai-image-trust-scanner\data\test_images`
- Supported extensions: .bmp, .jpeg, .jpg, .png, .tif, .tiff, .webp
- Found image count: 20
- Skipped file count: 2
- Error count: 0

## Output Files

- `feature_report.jsonl`: one detailed JSON object per processed image.
- `feature_summary.csv`: flat table of features, score, prediction, and confidence.
- `explainable_report.md`: this human-readable report.
- `day5_metrics.json`: aggregate run metrics.
- `calibration_analysis.md`: label-group calibration notes derived from `feature_summary.csv`.

## Feature Guide

- Metadata features check EXIF, camera model, software, and timestamp fields.
- Sharpness score estimates local detail with a Laplacian-style variance calculation.
- Edge density measures how many neighboring pixels have strong transitions.
- RGB mean and standard deviation summarize brightness and color spread per channel.
- Color entropy measures how diverse the color distribution is.
- Noise score and local variance estimate fine texture after light smoothing.
- Compression artifacts use JPEG quantization when available, otherwise an 8x8 blockiness fallback.

## Image Results

| Image | Label | Risk | Prediction | Confidence | Key Reasons |
| --- | --- | ---: | --- | --- | --- |
| `data\test_images\ai\ai_001.png` | ai | 43.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\ai\ai_002.png` | ai | 43.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\ai\ai_003.png` | ai | 43.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\ai\ai_004.png` | ai | 48.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Color entropy is high, suggesting a broad natural-looking color distribution. |
| `data\test_images\ai\ai_005.png` | ai | 48.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Color entropy is high, suggesting a broad natural-looking color distribution. |
| `data\test_images\ai\ai_006.png` | ai | 59.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Color entropy is high, suggesting a broad natural-looking color distribution.; Compression fallback found very weak 8x8 block artifacts. |
| `data\test_images\ai\ai_007.png` | ai | 47.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\ai\ai_008.png` | ai | 48.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Color entropy is high, suggesting a broad natural-looking color distribution. |
| `data\test_images\ai\ai_009.png` | ai | 43.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\ai\ai_010.png` | ai | 43.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\real\phone_photo_001.jpg` | real | 40.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\real\phone_photo_002.jpg` | real | 36.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\real\phone_photo_003.jpg` | real | 66.0 | likely_ai | medium | No EXIF metadata was found, which is common for generated or heavily processed images.; Edge density is low, which can indicate over-smoothed generated imagery.; JPEG quality estimate is low enough to show clear recompression history. |
| `data\test_images\real\phone_photo_004.jpg` | real | 56.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; JPEG quality estimate is low enough to show clear recompression history. |
| `data\test_images\real\phone_photo_005.jpg` | real | 46.0 | uncertain | low | Color entropy is high, suggesting a broad natural-looking color distribution. |
| `data\test_images\real\phone_photo_006.jpg` | real | 52.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Color entropy is high, suggesting a broad natural-looking color distribution.; JPEG quality estimate is low enough to show clear recompression history. |
| `data\test_images\real\phone_photo_007.jpg` | real | 41.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Color entropy is high, suggesting a broad natural-looking color distribution. |
| `data\test_images\real\phone_photo_008.jpg` | real | 36.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |
| `data\test_images\real\screenshot_real_001.jpg` | real | 45.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Noise and local variance are visible, which supports a real-camera or compressed-photo signal. |
| `data\test_images\real\web_real_001.jpg` | real | 36.0 | uncertain | low | No EXIF metadata was found, which is common for generated or heavily processed images.; Sharpness score is high, indicating strong natural or compressed detail.; Edge density is high, showing many local transitions and details. |

## Interpretation Notes

- A high risk score means the available explainable signals resemble patterns often seen in generated or heavily processed images.
- A low risk score means the available signals contain more camera-like or compression-history evidence.
- The score should be reviewed together with model output, source context, and provenance metadata.
