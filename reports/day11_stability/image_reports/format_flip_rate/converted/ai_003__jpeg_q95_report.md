# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:21:37.435821+00:00

## Final Result

- Final score: 0.178096
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: uncertain
- Decision status: uncertain
- Confidence distance: 0.028096
- Decision reason: score_inside_uncertain_band

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\ai\\jpeg_q95\\ai_003__jpeg_q95.jpg",
  "filename": "ai_003__jpeg_q95.jpg",
  "format": "JPEG",
  "width": 1448,
  "height": 1086,
  "color_mode": "RGB",
  "file_size_bytes": 605646,
  "file_size_kb": 591.45,
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
  "brightness_mean": 118.523003,
  "brightness_std": 60.25801,
  "color_channel_mean": {
    "red": 116.834828,
    "green": 118.794858,
    "blue": 121.372374
  },
  "color_channel_std": {
    "red": 60.970272,
    "green": 60.315486,
    "blue": 60.839183
  },
  "edge_density": 0.105934,
  "laplacian_variance": 844.44586,
  "noise_estimate": 6.780281,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.449923,
  "frequency_score": 0.449923,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\ai\\jpeg_q95\\ai_003__jpeg_q95.jpg",
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
