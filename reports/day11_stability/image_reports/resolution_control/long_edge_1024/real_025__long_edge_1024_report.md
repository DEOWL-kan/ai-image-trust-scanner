# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:33:15.484106+00:00

## Final Result

- Final score: 0.248791
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: ai
- Decision status: decided
- Confidence distance: 0.098791
- Decision reason: score_above_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day11_resolution_control\\real\\long_edge_1024\\real_025__long_edge_1024.jpg",
  "filename": "real_025__long_edge_1024.jpg",
  "format": "JPEG",
  "width": 768,
  "height": 1024,
  "color_mode": "RGB",
  "file_size_bytes": 365474,
  "file_size_kb": 356.91,
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
  "brightness_mean": 97.197998,
  "brightness_std": 62.241778,
  "color_channel_mean": {
    "red": 101.144075,
    "green": 96.847914,
    "blue": 88.776276
  },
  "color_channel_std": {
    "red": 64.463393,
    "green": 62.676996,
    "blue": 54.997519
  },
  "edge_density": 0.198881,
  "laplacian_variance": 4152.019022,
  "noise_estimate": 16.068817,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.638444,
  "frequency_score": 0.638444,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day11_resolution_control\\real\\long_edge_1024\\real_025__long_edge_1024.jpg",
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
