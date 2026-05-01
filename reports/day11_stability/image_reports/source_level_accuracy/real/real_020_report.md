# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:27:09.656387+00:00

## Final Result

- Final score: 0.112877
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: real
- Final label: real
- Decision status: decided
- Confidence distance: 0.037123
- Decision reason: score_below_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_020.jpg",
  "filename": "real_020.jpg",
  "format": "JPEG",
  "width": 4032,
  "height": 3024,
  "color_mode": "RGB",
  "file_size_bytes": 2607181,
  "file_size_kb": 2546.08,
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
  "brightness_mean": 147.052563,
  "brightness_std": 66.504501,
  "color_channel_mean": {
    "red": 158.541655,
    "green": 144.330482,
    "blue": 131.010588
  },
  "color_channel_std": {
    "red": 59.709836,
    "green": 70.869479,
    "blue": 73.677728
  },
  "edge_density": 0.012233,
  "laplacian_variance": 27.080519,
  "noise_estimate": 1.01185,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.207671,
  "frequency_score": 0.207671,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_020.jpg",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- EXIF metadata exists.
- Noise estimate is very low for this baseline heuristic.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
