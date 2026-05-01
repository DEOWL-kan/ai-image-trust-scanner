# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:33:09.161173+00:00

## Final Result

- Final score: 0.18165
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: ai
- Decision status: decided
- Confidence distance: 0.03165
- Decision reason: score_above_threshold_margin

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day11_resolution_control\\real\\long_edge_768\\real_009__long_edge_768.jpg",
  "filename": "real_009__long_edge_768.jpg",
  "format": "JPEG",
  "width": 354,
  "height": 768,
  "color_mode": "RGB",
  "file_size_bytes": 65970,
  "file_size_kb": 64.42,
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
  "brightness_mean": 77.318823,
  "brightness_std": 70.501506,
  "color_channel_mean": {
    "red": 86.666464,
    "green": 74.408799,
    "blue": 67.800671
  },
  "color_channel_std": {
    "red": 69.223807,
    "green": 73.239325,
    "blue": 63.886854
  },
  "edge_density": 0.040188,
  "laplacian_variance": 360.719126,
  "noise_estimate": 3.861332,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.4594,
  "frequency_score": 0.4594,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day11_resolution_control\\real\\long_edge_768\\real_009__long_edge_768.jpg",
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
