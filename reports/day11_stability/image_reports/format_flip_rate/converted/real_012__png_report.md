# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:22:22.689733+00:00

## Final Result

- Final score: 0.128035
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: real
- Final label: uncertain
- Decision status: uncertain
- Confidence distance: 0.021965
- Decision reason: score_inside_uncertain_band

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_012__png.png",
  "filename": "real_012__png.png",
  "format": "PNG",
  "width": 3024,
  "height": 4032,
  "color_mode": "RGB",
  "file_size_bytes": 8885649,
  "file_size_kb": 8677.39,
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
  "brightness_mean": 133.785635,
  "brightness_std": 68.379363,
  "color_channel_mean": {
    "red": 132.725491,
    "green": 138.759659,
    "blue": 111.000964
  },
  "color_channel_std": {
    "red": 71.010766,
    "green": 66.808073,
    "blue": 74.707992
  },
  "edge_density": 0.018411,
  "laplacian_variance": 40.149603,
  "noise_estimate": 1.300813,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.223094,
  "frequency_score": 0.223094,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_012__png.png",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- No EXIF found; this is only a weak provenance signal.
- Noise estimate is very low for this baseline heuristic.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
