# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T14:13:28.572007+00:00

## Final Result

- Final score: 0.208551
- Risk level: low

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\ai\\ai_002.png",
  "filename": "ai_002.png",
  "format": "PNG",
  "width": 1448,
  "height": 1086,
  "color_mode": "RGB",
  "file_size_bytes": 3202876,
  "file_size_kb": 3127.81,
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
  "brightness_mean": 81.881598,
  "brightness_std": 60.019638,
  "color_channel_mean": {
    "red": 94.929007,
    "green": 79.043625,
    "blue": 62.245516
  },
  "color_channel_std": {
    "red": 66.939088,
    "green": 59.336567,
    "blue": 54.687086
  },
  "edge_density": 0.160896,
  "laplacian_variance": 2530.740924,
  "noise_estimate": 12.782267,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.531137,
  "frequency_score": 0.531137,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\ai\\ai_002.png",
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
