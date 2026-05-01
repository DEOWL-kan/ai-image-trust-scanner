# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:22:15.381135+00:00

## Final Result

- Final score: 0.202471
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: ai
- Decision status: decided
- Confidence distance: 0.052471
- Decision reason: score_above_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_010__png.png",
  "filename": "real_010__png.png",
  "format": "PNG",
  "width": 4672,
  "height": 7008,
  "color_mode": "RGB",
  "file_size_bytes": 30970500,
  "file_size_kb": 30244.63,
  "error": null
}
```

## Metadata Result

```json
{
  "checked": true,
  "has_exif": false,
  "camera_make": null,
  "camera_model": null,
  "software": null,
  "datetime_original": null,
  "exif_field_count": 0,
  "missing_exif_note": "No EXIF found. This limits provenance, but does not mean the image is AI-generated.",
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
  "brightness_mean": 112.820293,
  "brightness_std": 70.722081,
  "color_channel_mean": {
    "red": 113.977963,
    "green": 113.176682,
    "blue": 107.76977
  },
  "color_channel_std": {
    "red": 72.019218,
    "green": 70.714738,
    "blue": 69.723962
  },
  "edge_density": 0.080392,
  "laplacian_variance": 1048.765061,
  "noise_estimate": 7.561304,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.514923,
  "frequency_score": 0.514923,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_010__png.png",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- No EXIF found; this is only a weak provenance signal.
- Basic forensic features did not trigger strong baseline warnings.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
