# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:37:17.233237+00:00

## Final Result

- Final score: 0.202338
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: ai
- Decision status: decided
- Confidence distance: 0.052338
- Decision reason: score_above_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_015.jpg",
  "filename": "real_015.jpg",
  "format": "JPEG",
  "width": 5712,
  "height": 4284,
  "color_mode": "RGB",
  "file_size_bytes": 5849944,
  "file_size_kb": 5712.84,
  "error": null
}
```

## Metadata Result

```json
{
  "checked": true,
  "has_exif": true,
  "camera_make": null,
  "camera_model": null,
  "software": null,
  "datetime_original": null,
  "exif_field_count": 1,
  "missing_exif_note": null,
  "optional_interfaces": {
    "exiftool": {
      "status": "optional_placeholder",
      "note": "Reserved for deeper EXIF/XMP/IPTC parsing in a later version."
    },
    "c2pa": {
      "status": "optional_placeholder",
      "note": "Reserved for Content Credentials / C2PA manifest parsing."
    }
  },
  "error": null
}
```

## Forensic Result

```json
{
  "checked": true,
  "brightness_mean": 99.855834,
  "brightness_std": 71.99005,
  "color_channel_mean": {
    "red": 99.547205,
    "green": 100.578525,
    "blue": 97.054837
  },
  "color_channel_std": {
    "red": 73.081572,
    "green": 72.566305,
    "blue": 67.800243
  },
  "edge_density": 0.002854,
  "laplacian_variance": 20.52642,
  "noise_estimate": 1.201876,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.306235,
  "frequency_score": 0.306235,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_015.jpg",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- EXIF metadata exists.
- Edge density is outside the broad expected baseline range.
- Noise estimate is very low for this baseline heuristic.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
