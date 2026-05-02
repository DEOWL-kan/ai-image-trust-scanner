# Day14 Dataset Expansion Baseline Report

## 1. Day14 Test Set Scale

- Native raw images: `200`
- Paired format images: `400`
- Resolution-control images: `1200`
- Total evaluated rows: `1800`

## 2. AI/Real Quantity

| label | raw | format | resolution | total |
| --- | --- | --- | --- | --- |
| ai | 100 | 200 | 600 | 900 |
| real | 100 | 200 | 600 | 900 |

## 3. Scene Type Quantity

| label | scene_type | count |
| --- | --- | --- |
| ai | food_retail | 135 |
| ai | indoor_home | 135 |
| ai | lowlight_weather | 135 |
| ai | nature_travel | 135 |
| ai | object_closeup | 135 |
| ai | outdoor_street | 135 |
| ai | people_partial | 90 |
| real | food_retail | 135 |
| real | indoor_home | 135 |
| real | lowlight_weather | 135 |
| real | nature_travel | 135 |
| real | object_closeup | 135 |
| real | outdoor_street | 135 |
| real | people_partial | 90 |

## 4. Raw Baseline Result

| metric | value |
| --- | --- |
| overall_accuracy | 0.305 |
| ai_accuracy | 0.39 |
| real_accuracy | 0.22 |
| false_positive_count | 23 |
| false_negative_count | 1 |
| uncertain_count | 115 |
| uncertain_rate | 0.575 |
| hard_candidate_count | 167 |

## 5. Paired Format Result

| metric | value |
| --- | --- |
| overall_accuracy | 0.2775 |
| ai_accuracy | 0.405 |
| real_accuracy | 0.15 |
| false_positive_count | 48 |
| false_negative_count | 2 |
| uncertain_count | 239 |
| uncertain_rate | 0.5975 |
| hard_candidate_count | 346 |

## 6. Resolution Control Result

| metric | value |
| --- | --- |
| overall_accuracy | 0.31 |
| ai_accuracy | 0.62 |
| real_accuracy | 0.0 |
| false_positive_count | 406 |
| false_negative_count | 0 |
| uncertain_count | 422 |
| uncertain_rate | 0.351667 |
| hard_candidate_count | 942 |

## 7. Format Flip Rate Analysis

- Complete PNG/JPG pairs: `200`
- Flip count: `3`
- `format_flip_rate`: `0.015`

## 8. Resolution Flip Rate Analysis

- Complete native/long-edge groups: `400`
- Flip count: `234`
- `resolution_flip_rate`: `0.585`

## 9. Main False Positive Clusters

| scene_type | variant | resolution_type | count |
| --- | --- | --- | --- |
| nature_travel | png_long1024 | long1024 | 15 |
| nature_travel | png_long768 | long768 | 15 |
| nature_travel | png_long512 | long512 | 15 |
| nature_travel | jpg_q95_long1024 | long1024 | 15 |
| nature_travel | jpg_q95_long768 | long768 | 15 |
| nature_travel | jpg_q95_long512 | long512 | 15 |
| outdoor_street | png_long1024 | long1024 | 15 |
| outdoor_street | png_long768 | long768 | 15 |
| outdoor_street | png_long512 | long512 | 15 |
| outdoor_street | jpg_q95_long1024 | long1024 | 15 |

## 10. Main False Negative Clusters

| scene_type | variant | resolution_type | count |
| --- | --- | --- | --- |
| indoor_home | native | native | 1 |
| indoor_home | png | native | 1 |
| indoor_home | jpg_q95 | native | 1 |

## 11. Uncertain Samples

- Raw uncertain count: `115`
- Format uncertain count: `239`
- Resolution uncertain count: `422`
- All uncertain count: `776`

## 12. Baseline @ 0.15 Regression Reference

Yes, as a regression reference only. The run used the configured baseline threshold `0.15` without changing detector weights or final-label policy.

## 13. Day15 Suggestions

- Review hard candidates by scene type before changing any detector threshold or score weights.
- Compare false-positive clusters against EXIF/missing-EXIF and low-light/weather conditions.
- Inspect format and resolution flip samples first; they are the most useful stress cases for regression stability.
- Keep Day14 metadata difficulty unchanged until baseline evidence is reviewed.
