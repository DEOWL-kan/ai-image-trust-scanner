# Day16 Uncertain Decision Layer v2 + Multi-resolution Consistency

## Day16 Goal
Day16 adds a decision layer above the existing detector. The detector score and fusion weights remain unchanged; the new layer asks whether the score is stable across image resolutions before returning a definite AI or real label.

## Why 0.15 Alone Is Not Enough
The 0.15 threshold remains the baseline regression reference, but Day15 showed that AI and real score distributions overlap, real JPG/no-EXIF JPEG samples form a false-positive cluster, and resizing can change labels. A single hard boundary cannot express those unstable cases, so Day16 measures consistency and can return `uncertain` instead of forcing a brittle binary label.

## Multi-resolution Consistency Design
Each image is scanned as `original`, `long_edge_1024`, `long_edge_768`, and `long_edge_512`. Aspect ratio is preserved. If the source is smaller than a target long edge, that variant is recorded as `no_upscale` and skipped for aggregation. Every successful variant uses the same existing detector stack.

## Uncertain Decision Layer v2 Rules
- baseline_threshold: 0.15
- real_safe_threshold: 0.12
- ai_safe_threshold: 0.18
- score_std_limit: 0.035
- score_range_limit: 0.06

Rules: high mean score plus stable AI votes becomes `ai`; low mean score plus stable real votes becomes `real`; near-band means, large score variance/range, high-range resolution flips, and weak vote majorities become `uncertain` with an explicit reason.

## Raw Baseline vs Final Decision Layer
- raw_accuracy_at_0_15: 0.669697
- selective_accuracy: 0.719149
- final_accuracy_count_uncertain_wrong: 0.256061
- coverage: 0.356061
- uncertain_rate: 0.643939

## FP / FN Changes
- definite_fp_count: 66
- definite_fn_count: 0
- uncertain_ai_count: 161
- uncertain_real_count: 264

## Resolution Flip Samples
- resolution_flip_rate: 0.451515
- avg_score_std: 0.019295
- avg_score_range: 0.048131

| image_path | true_label | category | format | score_range | resolution_flip_count | decision_reason | final_label |
| --- | --- | --- | --- | --- | --- | --- | --- |
| data\test_images\day14_expansion\raw\real\nature_travel\real_050_nature_travel_native.jpeg | real | nature_travel | jpeg | 0.156907 | 1 | resolution_flip | uncertain |
| data\test_images\legacy\day8_small_30\real\real_018.jpg | real | day8_small_30 | jpg | 0.156312 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\raw\real\nature_travel\real_057_nature_travel_native.jpeg | real | nature_travel | jpeg | 0.148699 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_050_nature_travel_jpg_q95.jpg | real | real_jpg | jpg | 0.147505 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_050_nature_travel_png.png | real | real_png | png | 0.145736 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_057_nature_travel_jpg_q95.jpg | real | real_jpg | jpg | 0.13937 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_057_nature_travel_png.png | real | real_png | png | 0.137236 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_036_lowlight_weather_native.jpeg | real | lowlight_weather | jpeg | 0.133538 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_038_lowlight_weather_native.jpeg | real | lowlight_weather | jpeg | 0.130435 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\raw\real\outdoor_street\real_088_outdoor_street_native.jpeg | real | outdoor_street | jpeg | 0.128637 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_023_indoor_home_jpg_q95.jpg | real | real_jpg | jpg | 0.125815 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_036_lowlight_weather_jpg_q95.jpg | real | real_jpg | jpg | 0.124528 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_036_lowlight_weather_png.png | real | real_png | png | 0.123188 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_023_indoor_home_png.png | real | real_png | png | 0.123133 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\raw\real\outdoor_street\real_081_outdoor_street_native.jpeg | real | outdoor_street | jpeg | 0.122545 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_003_food_retail_png.png | real | real_png | png | 0.12242 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_003_food_retail_jpg_q95.jpg | real | real_jpg | jpg | 0.122101 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_100_people_partial_jpg_q95.jpg | real | real_jpg | jpg | 0.121557 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_png\real_038_lowlight_weather_png.png | real | real_png | png | 0.119788 | 1 | resolution_flip | uncertain |
| data\test_images\day14_expansion\paired_format\real_jpg\real_038_lowlight_weather_jpg_q95.jpg | real | real_jpg | jpg | 0.118318 | 1 | resolution_flip | uncertain |

## Decision Reason Summary

| decision_reason | count |
| --- | --- |
| stable_ai_high_confidence | 235 |
| near_threshold_band | 204 |
| resolution_flip | 163 |
| unstable_score_range | 39 |
| weak_vote_majority | 14 |
| unstable_score_std | 5 |

## Category-level Summary

| group | total_images | coverage | selective_accuracy | raw_accuracy_at_0_15 | definite_fp_count | definite_fn_count | resolution_flip_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai_jpg | 100 | 0.54 | 1.0 | 0.8 | 0 | 0 | 0.23 |
| ai_png | 100 | 0.49 | 1.0 | 0.78 | 0 | 0 | 0.24 |
| day8_small_30 | 60 | 0.466667 | 0.607143 | 0.55 | 11 | 0 | 0.416667 |
| food_retail | 30 | 0.133333 | 0.75 | 0.6 | 1 | 0 | 0.566667 |
| indoor_home | 30 | 0.133333 | 0.0 | 0.566667 | 4 | 0 | 0.566667 |
| lowlight_weather | 30 | 0.4 | 0.833333 | 0.666667 | 2 | 0 | 0.433333 |
| nature_travel | 30 | 0.566667 | 0.764706 | 0.8 | 4 | 0 | 0.3 |
| object_closeup | 30 | 0.233333 | 1.0 | 0.766667 | 0 | 0 | 0.633333 |
| outdoor_street | 30 | 0.5 | 0.866667 | 0.866667 | 2 | 0 | 0.366667 |
| people_partial | 20 | 0.15 | 1.0 | 0.75 | 0 | 0 | 0.65 |
| real_jpg | 100 | 0.22 | 0.0 | 0.54 | 22 | 0 | 0.64 |
| real_png | 100 | 0.2 | 0.0 | 0.54 | 20 | 0 | 0.63 |

## Format-level Summary

| group | total_images | coverage | selective_accuracy | raw_accuracy_at_0_15 | definite_fp_count | definite_fn_count | resolution_flip_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| jpeg | 84 | 0.083333 | 0.0 | 0.702381 | 7 | 0 | 0.809524 |
| jpg | 243 | 0.378601 | 0.586957 | 0.625514 | 38 | 0 | 0.460905 |
| png | 333 | 0.408408 | 0.845588 | 0.693694 | 21 | 0 | 0.354354 |

## False-positive Cluster Summary

| analysis_type | group | total_images | false_positive_count | false_positive_rate |
| --- | --- | --- | --- | --- |
| decision_reason | stable_ai_high_confidence | 235 | 66 | 0.280851 |
| category | real_jpg | 100 | 22 | 0.22 |
| category | real_png | 100 | 20 | 0.2 |
| category | day8_small_30 | 60 | 11 | 0.183333 |
| format | jpg | 243 | 38 | 0.156379 |
| category | indoor_home | 30 | 4 | 0.133333 |
| category | nature_travel | 30 | 4 | 0.133333 |
| has_exif | true | 111 | 13 | 0.117117 |
| has_exif | false | 549 | 53 | 0.096539 |
| format | jpeg | 84 | 7 | 0.083333 |
| category | lowlight_weather | 30 | 2 | 0.066667 |
| category | outdoor_street | 30 | 2 | 0.066667 |
| format | png | 333 | 21 | 0.063063 |
| category | food_retail | 30 | 1 | 0.033333 |

## False-negative Cluster Summary

No rows.

## Current Issues
The decision layer improves how the system communicates low-confidence cases, but it does not create new signal. Cases with stable but overlapping scores remain limited by the baseline detector. Coverage must be read together with selective accuracy: higher uncertainty is useful only if it removes risky calls without hiding too much of the dataset.

## Day17 Suggestions
- Review uncertain real JPEG/no-EXIF samples separately from unstable resize samples.
- Add a calibration view that compares mean score, original score, and score range by category.
- Consider a non-weight-changing metadata reliability feature that distinguishes camera JPEGs from recompressed/no-EXIF web JPEGs.
- Keep threshold 0.15 as the regression baseline while evaluating decision-layer coverage targets.

## Output Files
- multi_resolution_csv: `reports\day16_multi_resolution_consistency.csv`
- decision_results_csv: `reports\day16_uncertain_decision_v2_results.csv`
- summary_json: `reports\day16_uncertain_v2_summary.json`
