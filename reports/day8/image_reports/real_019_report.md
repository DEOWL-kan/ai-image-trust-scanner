# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T14:14:05.283929+00:00

## Final Result

- Final score: 0.170343
- Risk level: low

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_019.jpg",
  "filename": "real_019.jpg",
  "format": "JPEG",
  "width": 4032,
  "height": 3024,
  "color_mode": "RGB",
  "file_size_bytes": 5731044,
  "file_size_kb": 5596.72,
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
  "brightness_mean": 118.645967,
  "brightness_std": 50.955768,
  "color_channel_mean": {
    "red": 127.904588,
    "green": 118.671653,
    "blue": 94.198873
  },
  "color_channel_std": {
    "red": 48.733939,
    "green": 52.423942,
    "blue": 55.14358
  },
  "edge_density": 0.168555,
  "laplacian_variance": 936.174613,
  "noise_estimate": 7.139341,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.454248,
  "frequency_score": 0.454248,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\real\\real_019.jpg",
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
