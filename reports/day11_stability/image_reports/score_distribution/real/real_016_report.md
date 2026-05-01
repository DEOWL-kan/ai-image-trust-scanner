# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:37:18.824978+00:00

## Final Result

- Final score: 0.096813
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: real
- Final label: real
- Decision status: decided
- Confidence distance: 0.053187
- Decision reason: score_below_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_016.jpg",
  "filename": "real_016.jpg",
  "format": "JPEG",
  "width": 4032,
  "height": 3024,
  "color_mode": "RGB",
  "file_size_bytes": 4558124,
  "file_size_kb": 4451.29,
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
  "brightness_mean": 114.523562,
  "brightness_std": 58.320622,
  "color_channel_mean": {
    "red": 113.771771,
    "green": 117.67416,
    "blue": 100.312004
  },
  "color_channel_std": {
    "red": 64.056618,
    "green": 56.780184,
    "blue": 63.041578
  },
  "edge_density": 0.044008,
  "laplacian_variance": 101.895747,
  "noise_estimate": 2.166016,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.258167,
  "frequency_score": 0.258167,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_016.jpg",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- EXIF metadata exists.
- Basic forensic features did not trigger strong baseline warnings.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
