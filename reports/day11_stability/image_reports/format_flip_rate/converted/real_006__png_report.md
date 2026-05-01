# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:22:01.605751+00:00

## Final Result

- Final score: 0.168431
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: ai
- Final label: uncertain
- Decision status: uncertain
- Confidence distance: 0.018431
- Decision reason: score_inside_uncertain_band

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_006__png.png",
  "filename": "real_006__png.png",
  "format": "PNG",
  "width": 960,
  "height": 1280,
  "color_mode": "RGB",
  "file_size_bytes": 753792,
  "file_size_kb": 736.12,
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
  "brightness_mean": 130.501067,
  "brightness_std": 43.925473,
  "color_channel_mean": {
    "red": 140.402402,
    "green": 131.335988,
    "blue": 100.484258
  },
  "color_channel_std": {
    "red": 41.109119,
    "green": 46.323616,
    "blue": 51.96198
  },
  "edge_density": 0.007332,
  "laplacian_variance": 18.304463,
  "noise_estimate": 0.854955,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.21415,
  "frequency_score": 0.21415,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\day10_format_control\\real\\png\\real_006__png.png",
  "ai_probability": 0.5,
  "model_name": "v0.1-baseline-placeholder",
  "model_status": "placeholder",
  "note": "No deep model is trained or loaded in V0.1. This neutral value is placeholder metadata and is not used as trained evidence.",
  "error": null
}
```

## Evidence Summary

- No EXIF found; this is only a weak provenance signal.
- Laplacian variance is low, suggesting a very smooth image.
- Noise estimate is very low for this baseline heuristic.
- Frequency score is a weak heuristic based on high-frequency energy, not a final judgment.
- Deep model detector is placeholder and is not used as trained evidence.

## Limitation Note

This is AI Image Trust Scanner V0.1 baseline output. It combines simple metadata, forensic, frequency, and placeholder model signals. It is not a final detection conclusion and should not be treated as proof that an image is real or AI-generated.
