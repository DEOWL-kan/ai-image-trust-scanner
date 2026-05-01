# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:21:38.667618+00:00

## Final Result

- Final score: 0.146809
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: real
- Final label: uncertain
- Decision status: uncertain
- Confidence distance: 0.003191
- Decision reason: score_inside_uncertain_band

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\ai\\jpeg_q95\\ai_005__jpeg_q95.jpg",
  "filename": "ai_005__jpeg_q95.jpg",
  "format": "JPEG",
  "width": 1122,
  "height": 1402,
  "color_mode": "RGB",
  "file_size_bytes": 494972,
  "file_size_kb": 483.37,
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
  "brightness_mean": 141.691227,
  "brightness_std": 62.517224,
  "color_channel_mean": {
    "red": 150.251198,
    "green": 140.024215,
    "blue": 127.890771
  },
  "color_channel_std": {
    "red": 62.164006,
    "green": 63.196511,
    "blue": 63.985017
  },
  "edge_density": 0.037555,
  "laplacian_variance": 299.770556,
  "noise_estimate": 3.858109,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.366492,
  "frequency_score": 0.366492,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\ai\\jpeg_q95\\ai_005__jpeg_q95.jpg",
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
