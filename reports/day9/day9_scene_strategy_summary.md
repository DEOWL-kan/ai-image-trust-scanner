# Day9 Scene-Aware Strategy Summary

## Scope

- Scene tags are weak engineering rules based on filename keywords, EXIF, dimensions, brightness, edge density, blur/detail, noise, and format context.
- Binary output is preserved as `predicted_label`; scene-aware strategy may add `final_label=uncertain` with a reason.
- This is a small-scale 60-image Day9 strategy report, not production-grade scene detection.

## Scene Statistics

| scene_tag | samples | FP | FN | accuracy | avg ai_score | mode |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| closeup_object | 20 | 7 | 5 | 0.4000 | 0.152425 | uncertain_protection |
| unknown | 16 | 0 | 3 | 0.8125 | 0.171358 | uncertain_protection |
| shelf | 8 | 5 | 0 | 0.3750 | 0.216497 | conservative |
| low_light | 7 | 1 | 1 | 0.7143 | 0.163664 | uncertain_protection |
| road | 6 | 3 | 0 | 0.5000 | 0.178119 | conservative |
| indoor | 3 | 2 | 0 | 0.3333 | 0.188856 | conservative |

## High-FP Scenes

- closeup_object: FP 7 / samples 20.
- shelf: FP 5 / samples 8.
- road: FP 3 / samples 6.
- indoor: FP 2 / samples 3.
- low_light: FP 1 / samples 7.

## High-FN Scenes

- closeup_object: FN 5 / samples 20.
- unknown: FN 3 / samples 16.
- low_light: FN 1 / samples 7.

## Threshold Strategy

- Conservative threshold candidate: shelf (Use a more conservative threshold because false positives are high for this scene.)
- Conservative threshold candidate: road (Use a more conservative threshold because false positives are high for this scene.)
- Conservative threshold candidate: indoor (Use a more conservative threshold because false positives are high for this scene.)
- No scene clearly asks for an aggressive threshold from this small slice.
- Uncertain-protection candidate: closeup_object (Use uncertain output because both false positives and false negatives appear in this scene.)
- Uncertain-protection candidate: unknown (Use uncertain output because many samples are low-confidence or protected by scene rules.)
- Uncertain-protection candidate: low_light (Use uncertain output because both false positives and false negatives appear in this scene.)

## Initial Scene-Aware Rules

- If the image is low-light, blur-like, or heavily compressed, route it into an uncertain protection zone.
- If an image has no EXIF but natural real-image features are strong, avoid directly strengthening the AI label.
- If texture is over-smooth, edges are unusually uniform, and local noise is consistently low, raise AI suspicion.
- If phone/camera metadata, natural noise, and plausible detail are present, lower false-positive risk.
- If the score is within threshold +/- low_confidence_margin, output `final_label=uncertain` while preserving the binary `predicted_label`.

## Output Files

- `reports\day9\day9_scene_strategy_summary.md`
- `reports\day9\day9_misclassification_attribution.csv`

_Generated at 2026-05-02T00:16:38+08:00._
