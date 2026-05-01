# AI Image Trust Scanner Report

Version: V0.1 baseline

Generated at: 2026-05-01T14:13:36.738890+00:00

## Final Result

- Final score: 0.135133
- Risk level: low

## Image Info

```json
{
  "ok": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\ai\\ai_024.png",
  "filename": "ai_024.png",
  "format": "PNG",
  "width": 1122,
  "height": 1402,
  "color_mode": "RGB",
  "file_size_bytes": 2068027,
  "file_size_kb": 2019.56,
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
  "brightness_mean": 93.979208,
  "brightness_std": 56.284321,
  "color_channel_mean": {
    "red": 101.58805,
    "green": 92.074607,
    "blue": 83.836886
  },
  "color_channel_std": {
    "red": 58.677534,
    "green": 56.206139,
    "blue": 55.729756
  },
  "edge_density": 0.020066,
  "laplacian_variance": 95.166931,
  "noise_estimate": 2.403467,
  "error": null
}
```

## Frequency Result

```json
{
  "checked": true,
  "high_frequency_energy_ratio": 0.335356,
  "frequency_score": 0.335356,
  "note": "Frequency analysis is a heuristic signal only, not an authenticity verdict.",
  "error": null
}
```

## Model Result

```json
{
  "checked": true,
  "image_path": "D:\\ai image\\ai-image-trust-scanner\\data\\test_images\\ai\\ai_024.png",
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
