# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T18:32:50.137104+00:00

## Final Result

- Final score: 0.147026
- Risk level: low
- Threshold: 0.15
- Uncertainty margin: 0.03
- Binary label at threshold: real
- Final label: uncertain
- Decision status: uncertain
- Confidence distance: 0.002974
- Decision reason: score_inside_uncertain_band

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_017.jpg",
  "filename": "real_017.jpg",
  "format": "JPEG",
  "width": 4032,
  "height": 3024,
  "color_mode": "RGB",
  "file_size_bytes": 6253527,
  "file_size_kb": 6106.96,
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
  "brightness_mean": 119.887774,
  "brightness_std": 54.725042,
  "color_channel_mean": {
    "red": 151.281849,
    "green": 111.773425,
    "blue": 79.342504
  },
  "color_channel_std": {
    "red": 61.696889,
    "green": 58.990448,
    "blue": 60.144014
  },
  "edge_density": 0.157462,
  "laplacian_variance": 632.165473,
  "noise_estimate": 5.959599,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.39207,
  "frequency_score": 0.39207,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_017.jpg",
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
