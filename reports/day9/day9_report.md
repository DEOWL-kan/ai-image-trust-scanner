# Day9 Error Attribution and Strategy Report

## Scope

- Day9 does not change the detector, feature code, score weights, or global thresholds.
- It reads Day8 predictions and per-image JSON reports, then explains where current errors come from.
- Single-image entry point: `main.py` -> `run_pipeline(...)`.
- Batch evaluation entry point: `scripts/evaluate_day8.py`.
- Threshold scan entry point: `scripts/sweep_threshold_day8.py`.
- Report output directories: single-image `outputs/reports/`, Day8 `reports/day8/`, Day9 `reports/day9/`.

## Day8 Operating Points

| Mode | Threshold | Accuracy | TP | TN | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| balanced | 0.15 | 0.5500 | 21 | 12 | 18 | 9 |
| conservative | 0.18 | 0.4833 | 12 | 17 | 13 | 18 |

## Misclassification Attribution

Balanced-threshold error buckets:

- frequency_dominated_real_image: 11
- borderline_false_negative: 8
- forensic_triggered_real_image: 5
- borderline_false_positive: 2
- low_forensic_low_frequency_ai_image: 1

Top balanced false positives:

| file | score | scene | bucket | scenario | dominant |
| --- | --- | --- | --- | --- | --- |
| real_028.jpg | 0.262213 | shelf | frequency_dominated_real_image | web_or_social_jpeg_no_exif | frequency |
| real_027.jpg | 0.262199 | shelf | frequency_dominated_real_image | web_or_social_jpeg_no_exif | frequency |
| real_030.jpg | 0.228971 | road | frequency_dominated_real_image | camera_photo_with_exif | frequency |
| real_022.jpg | 0.225620 | indoor | frequency_dominated_real_image | web_or_social_jpeg_no_exif | frequency |
| real_013.jpg | 0.222499 | closeup_object | forensic_triggered_real_image | camera_photo_with_exif | forensic |
| real_005.jpg | 0.220945 | closeup_object | forensic_triggered_real_image | camera_photo_with_exif | forensic |
| real_004.jpg | 0.219579 | closeup_object | forensic_triggered_real_image | web_or_social_jpeg_no_exif | forensic |
| real_025.jpg | 0.217730 | shelf | frequency_dominated_real_image | web_or_social_jpeg_no_exif | frequency |

Top balanced false negatives:

| file | score | scene | bucket | scenario | dominant |
| --- | --- | --- | --- | --- | --- |
| ai_021.png | 0.114600 | closeup_object | low_forensic_low_frequency_ai_image | png_export_no_exif | frequency |
| ai_011.png | 0.132229 | closeup_object | borderline_false_negative | png_export_no_exif | frequency |
| ai_013.png | 0.133096 | closeup_object | borderline_false_negative | png_export_no_exif | frequency |
| ai_024.png | 0.135133 | closeup_object | borderline_false_negative | png_export_no_exif | frequency |
| ai_014.png | 0.136960 | unknown | borderline_false_negative | png_export_no_exif | frequency |
| ai_025.png | 0.141403 | low_light | borderline_false_negative | png_export_no_exif | frequency |
| ai_005.png | 0.144311 | unknown | borderline_false_negative | png_export_no_exif | frequency |
| ai_020.png | 0.146161 | closeup_object | borderline_false_negative | png_export_no_exif | frequency |

## Feature Summary

| Group | Count | Avg score | Avg metadata | Avg forensic | Avg frequency | EXIF ratio | JPEG | PNG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 60 | 0.171719 | 0.040000 | 0.027000 | 0.406417 | 0.200000 | 30 | 30 |
| ground_truth_ai | 30 | 0.167572 | 0.050000 | 0.000000 | 0.421858 | 0.000000 | 0 | 30 |
| ground_truth_real | 30 | 0.175866 | 0.030000 | 0.054000 | 0.390975 | 0.400000 | 30 | 0 |
| balanced_correct | 33 | 0.162240 | 0.039394 | 0.004848 | 0.407285 | 0.212121 | 12 | 21 |
| balanced_false_positive | 18 | 0.206572 | 0.036111 | 0.081111 | 0.438174 | 0.277778 | 18 | 0 |
| balanced_false_negative | 9 | 0.136769 | 0.050000 | 0.000000 | 0.339717 | 0.000000 | 0 | 9 |

## Dataset Bias / Format Confound Warning

- Current AI samples are PNG exports without EXIF.
- Current real samples are JPEG images, some with EXIF.
- Current threshold and weight conclusions may partly reflect file format, compression, and provenance differences rather than pure AI-vs-real visual differences.
- Therefore, Day9 results are diagnostic evidence only and should not be used as production calibration.

## Weight Optimization Suggestions

- frequency is supporting signal only; it separates AI from real only weakly and must be validated per source scenario before increasing its weight.
- forensic/compression signals need independent corroboration before increasing AI suspicion. The current forensic rules are too sparse for AI recall.
- missing EXIF is weak provenance evidence only. It does not separate the current AI and real sets enough to justify a larger metadata weight.
- model_weight must stay 0 until real detector is active; the placeholder probability must not affect calibration.

## Scenario Strategy

- For png_export_no_exif, missing EXIF is expected, so rely more on texture and future model evidence; current FP/FN/total = 0/9/30.
- For web_or_social_jpeg_no_exif, route high-frequency-only hits to manual review or a conservative threshold; current FP/FN/total = 13/0/18.
- For camera_photo_with_exif, camera metadata should lower suspicion unless AI-tool metadata is present; current FP/FN/total = 5/0/12.

## Follow-Up Validation Notes

- Add scenario-aware review labels such as `likely_ai`, `likely_real`, and `needs_review` without replacing the raw score.
- Add per-feature calibration tables for frequency, edge density, noise, and Laplacian variance by image source type.
- Keep the current single-image and batch entry points stable while testing any candidate weight changes behind a separate analysis script.

## Output Files

- `reports\day9\day9_misclassification_attribution.csv`
- `reports\day9\day9_feature_summary_by_group.csv`
- `reports\day9\day9_analysis.json`
- `reports\day9\day9_report.md`
- `reports\day9\day9_scene_strategy_summary.md`

_Generated at 2026-05-02T00:16:38+08:00._
