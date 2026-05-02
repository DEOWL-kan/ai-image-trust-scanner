# Day15 False Positive Cluster + Resolution Flip Root Cause Analysis

## 1. Executive Summary

- main_total_images: 660
- main_ai_count: 330
- main_real_count: 330
- main_unknown_count: 0
- excluded_resolution_control_count: 1200
- raw_false_positive_count: 145
- raw_false_positive_rate: 0.439394
- final_false_positive_count: 84
- final_false_positive_rate: 0.254545
- main_resolution_flip_count: 383
- main_resolution_flip_rate: 0.580303
- main_uncertain_count: 384
- main_uncertain_rate: 0.581818
- Baseline threshold remains 0.150000; no detector weights, threshold, or default model strategy were changed.
- Main metrics include raw_source, paired_format, and legacy only; Day14 resolution_control derivatives are excluded from main conclusions.

## 2. Dataset Overview

- AI categories: 8.
- Real categories: 8.
- Unknown label count: 0.
- Format distribution: {'jpeg': 84, 'jpg': 243, 'png': 333}.
- Transform group distribution: {'ai_jpg': 100, 'ai_png': 100, 'legacy': 60, 'raw': 200, 'real_jpg': 100, 'real_png': 100}.
- Original resolution buckets: {'large': 357, 'small': 1, 'xlarge': 302}.

Top semantic category counts:

| semantic_category | count |
| --- | --- |
| food_retail | 90 |
| indoor_home | 90 |
| lowlight_weather | 90 |
| nature_travel | 90 |
| object_closeup | 90 |
| outdoor_street | 90 |
| people_partial | 60 |
| unknown | 60 |

## 2.1 Data Quality Notes

- Unknown label paths in the full scanned set: 0.
- No unknown-label images were found after filename fallback inference.
- Excluded resolution_control images: 1200. These Day14-derived resize-control images are excluded from main metrics.
- Duplicate base_id groups in raw/paired main rows: 200. Paired JPG/PNG/raw variants increase sample weight; Day16 can add source-level aggregation.

## 3. False Positive Cluster Analysis

Highest FP-rate groups by semantic category:

| group | total_real | false_positive_count | false_positive_rate | avg_score | median_score |
| --- | --- | --- | --- | --- | --- |
| indoor_home | 45 | 27 | 0.600000 | 0.164581 | 0.156948 |
| unknown | 30 | 18 | 0.600000 | 0.175866 | 0.172545 |
| nature_travel | 45 | 24 | 0.533333 | 0.158907 | 0.151936 |
| lowlight_weather | 45 | 23 | 0.511111 | 0.167513 | 0.152135 |
| outdoor_street | 45 | 18 | 0.400000 | 0.146318 | 0.143115 |

Highest FP-rate groups by transform group:

| group | total_real | false_positive_count | false_positive_rate | avg_score | median_score |
| --- | --- | --- | --- | --- | --- |
| legacy | 30 | 18 | 0.600000 | 0.175866 | 0.172545 |
| real_jpg | 100 | 46 | 0.460000 | 0.158829 | 0.147255 |
| real_png | 100 | 46 | 0.460000 | 0.159455 | 0.147949 |
| raw | 100 | 35 | 0.350000 | 0.149804 | 0.138476 |

Highest FP-rate groups by extension:

| group | total_real | false_positive_count | false_positive_rate | avg_score | median_score |
| --- | --- | --- | --- | --- | --- |
| jpg | 143 | 71 | 0.496503 | 0.164427 | 0.149587 |
| png | 103 | 49 | 0.475728 | 0.160290 | 0.148626 |
| jpeg | 84 | 25 | 0.297619 | 0.143593 | 0.135361 |

Highest FP-rate groups by EXIF:

| group | total_real | false_positive_count | false_positive_rate | avg_score | median_score |
| --- | --- | --- | --- | --- | --- |
| no_exif | 219 | 106 | 0.484018 | 0.161816 | 0.148626 |
| has_exif | 111 | 39 | 0.351351 | 0.149974 | 0.138980 |

False Positive top samples:

| image_path | semantic_category | transform_group | extension | width | height | has_exif | score | final_label | difficulty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| data\test_images\day14_expansion\paired_format\real_png\real_023_indoor_home_png.png | indoor_home | real_png | png | 3024 | 4032 | false | 0.269566 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_023_indoor_home_jpg_q95.jpg | indoor_home | real_jpg | jpg | 3024 | 4032 | false | 0.269115 | ai | hard |
| data\test_images\legacy\day8_small_30\real\real_028.jpg | unknown | legacy | jpg | 1279 | 1706 | false | 0.262213 | ai | unknown |
| data\test_images\legacy\day8_small_30\real\real_027.jpg | unknown | legacy | jpg | 1279 | 1706 | false | 0.262199 | ai | unknown |
| data\test_images\day14_expansion\raw\real\indoor_home\real_023_indoor_home_native.jpeg | indoor_home | raw | jpeg | 3024 | 4032 | true | 0.259766 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_003_food_retail_png.png | food_retail | real_png | png | 3024 | 4032 | false | 0.25475 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_003_food_retail_jpg_q95.jpg | food_retail | real_jpg | jpg | 3024 | 4032 | false | 0.252999 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_100_people_partial_jpg_q95.jpg | people_partial | real_jpg | jpg | 2316 | 3088 | false | 0.252387 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_100_people_partial_png.png | people_partial | real_png | png | 2316 | 3088 | false | 0.246597 | ai | hard |
| data\test_images\day14_expansion\raw\real\food_retail\real_003_food_retail_native.jpeg | food_retail | raw | jpeg | 3024 | 4032 | true | 0.244164 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_052_nature_travel_jpg_q95.jpg | nature_travel | real_jpg | jpg | 6227 | 9341 | false | 0.242922 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_099_people_partial_png.png | people_partial | real_png | png | 1980 | 3520 | false | 0.242328 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_005_food_retail_jpg_q95.jpg | food_retail | real_jpg | jpg | 4284 | 5712 | false | 0.241387 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_005_food_retail_png.png | food_retail | real_png | png | 4284 | 5712 | false | 0.241329 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_034_lowlight_weather_png.png | lowlight_weather | real_png | png | 3024 | 4032 | false | 0.241267 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_099_people_partial_jpg_q95.jpg | people_partial | real_jpg | jpg | 1980 | 3520 | false | 0.240302 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_034_lowlight_weather_jpg_q95.jpg | lowlight_weather | real_jpg | jpg | 3024 | 4032 | false | 0.240199 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_052_nature_travel_png.png | nature_travel | real_png | png | 6227 | 9341 | false | 0.239608 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_031_lowlight_weather_png.png | lowlight_weather | real_png | png | 3024 | 4032 | false | 0.238598 | ai | hard |
| data\test_images\day14_expansion\raw\real\people_partial\real_100_people_partial_native.jpeg | people_partial | raw | jpeg | 2316 | 3088 | true | 0.237154 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_031_lowlight_weather_jpg_q95.jpg | lowlight_weather | real_jpg | jpg | 3024 | 4032 | false | 0.236559 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_049_nature_travel_jpg_q95.jpg | nature_travel | real_jpg | jpg | 9504 | 6336 | false | 0.233144 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_png\real_062_object_closeup_png.png | object_closeup | real_png | png | 3024 | 4032 | false | 0.232041 | ai | hard |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_034_lowlight_weather_native.jpeg | lowlight_weather | raw | jpeg | 3024 | 4032 | true | 0.231138 | ai | hard |
| data\test_images\day14_expansion\raw\real\people_partial\real_099_people_partial_native.jpg | people_partial | raw | jpg | 1980 | 3520 | true | 0.231102 | ai | hard |
| data\test_images\day14_expansion\raw\real\food_retail\real_005_food_retail_native.jpeg | food_retail | raw | jpeg | 4284 | 5712 | true | 0.230856 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_062_object_closeup_jpg_q95.jpg | object_closeup | real_jpg | jpg | 3024 | 4032 | false | 0.230462 | ai | hard |
| data\test_images\day14_expansion\raw\real\nature_travel\real_052_nature_travel_native.jpg | nature_travel | raw | jpg | 6227 | 9341 | true | 0.230222 | ai | hard |
| data\test_images\day14_expansion\paired_format\real_jpg\real_046_nature_travel_jpg_q95.jpg | nature_travel | real_jpg | jpg | 1920 | 1080 | false | 0.22903 | ai | hard |
| data\test_images\legacy\day8_small_30\real\real_030.jpg | unknown | legacy | jpg | 690 | 504 | true | 0.228971 | ai | unknown |

## 4. Resolution Flip Analysis

Flip-rate groups by true label:

| group | total_count | flip_count | flip_rate | avg_score_delta | max_score_delta |
| --- | --- | --- | --- | --- | --- |
| real | 330 | 259 | 0.784848 | 0.065112 | 0.156907 |
| ai | 330 | 124 | 0.375758 | 0.031150 | 0.101709 |

Flip-rate groups by semantic category:

| group | total_count | flip_count | flip_rate | avg_score_delta | max_score_delta |
| --- | --- | --- | --- | --- | --- |
| object_closeup | 90 | 64 | 0.711111 | 0.050892 | 0.106604 |
| lowlight_weather | 90 | 60 | 0.666667 | 0.050392 | 0.133538 |
| outdoor_street | 90 | 57 | 0.633333 | 0.054144 | 0.128637 |
| indoor_home | 90 | 54 | 0.600000 | 0.037571 | 0.125815 |
| people_partial | 60 | 33 | 0.550000 | 0.048797 | 0.121557 |

Flip-rate groups by transform group:

| group | total_count | flip_count | flip_rate | avg_score_delta | max_score_delta |
| --- | --- | --- | --- | --- | --- |
| real_jpg | 100 | 79 | 0.790000 | 0.064845 | 0.147505 |
| real_png | 100 | 79 | 0.790000 | 0.063169 | 0.145736 |
| raw | 200 | 121 | 0.605000 | 0.051026 | 0.156907 |
| legacy | 60 | 28 | 0.466667 | 0.040150 | 0.156312 |
| ai_png | 100 | 39 | 0.390000 | 0.031653 | 0.101709 |

Resolution Flip top samples:

| image_path | true_label | semantic_category | transform_group | extension | original_size | original_label | resized_512_label | resized_768_label | resized_1024_label | score_delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| data\test_images\day14_expansion\raw\real\nature_travel\real_050_nature_travel_native.jpeg | real | nature_travel | raw | jpeg | 3024x4032 | real | ai | ai | ai | 0.156907 |
| data\test_images\legacy\day8_small_30\real\real_018.jpg | real | unknown | legacy | jpg | 3024x4032 | real | ai | ai | ai | 0.156312 |
| data\test_images\day14_expansion\raw\real\nature_travel\real_057_nature_travel_native.jpeg | real | nature_travel | raw | jpeg | 4032x3024 | real | ai | ai | ai | 0.148699 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_050_nature_travel_jpg_q95.jpg | real | nature_travel | real_jpg | jpg | 3024x4032 | real | ai | ai | ai | 0.147505 |
| data\test_images\day14_expansion\paired_format\real_png\real_050_nature_travel_png.png | real | nature_travel | real_png | png | 3024x4032 | real | ai | ai | ai | 0.145736 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_057_nature_travel_jpg_q95.jpg | real | nature_travel | real_jpg | jpg | 4032x3024 | real | ai | ai | ai | 0.139370 |
| data\test_images\day14_expansion\paired_format\real_png\real_057_nature_travel_png.png | real | nature_travel | real_png | png | 4032x3024 | real | ai | ai | ai | 0.137236 |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_036_lowlight_weather_native.jpeg | real | lowlight_weather | raw | jpeg | 3024x4032 | real | ai | ai | ai | 0.133538 |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_038_lowlight_weather_native.jpeg | real | lowlight_weather | raw | jpeg | 4284x5712 | real | ai | ai | ai | 0.130435 |
| data\test_images\day14_expansion\raw\real\outdoor_street\real_088_outdoor_street_native.jpeg | real | outdoor_street | raw | jpeg | 4284x5712 | real | ai | ai | ai | 0.128637 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_023_indoor_home_jpg_q95.jpg | real | indoor_home | real_jpg | jpg | 3024x4032 | ai | uncertain | ai | ai | 0.125815 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_036_lowlight_weather_jpg_q95.jpg | real | lowlight_weather | real_jpg | jpg | 3024x4032 | real | ai | ai | ai | 0.124528 |
| data\test_images\day14_expansion\paired_format\real_png\real_036_lowlight_weather_png.png | real | lowlight_weather | real_png | png | 3024x4032 | real | ai | ai | ai | 0.123188 |
| data\test_images\day14_expansion\paired_format\real_png\real_023_indoor_home_png.png | real | indoor_home | real_png | png | 3024x4032 | ai | uncertain | ai | ai | 0.123133 |
| data\test_images\day14_expansion\raw\real\outdoor_street\real_081_outdoor_street_native.jpeg | real | outdoor_street | raw | jpeg | 4284x5712 | real | ai | ai | ai | 0.122545 |
| data\test_images\day14_expansion\paired_format\real_png\real_003_food_retail_png.png | real | food_retail | real_png | png | 3024x4032 | ai | uncertain | uncertain | uncertain | 0.122420 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_003_food_retail_jpg_q95.jpg | real | food_retail | real_jpg | jpg | 3024x4032 | ai | uncertain | uncertain | uncertain | 0.122101 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_100_people_partial_jpg_q95.jpg | real | people_partial | real_jpg | jpg | 2316x3088 | ai | uncertain | uncertain | uncertain | 0.121557 |
| data\test_images\day14_expansion\paired_format\real_png\real_038_lowlight_weather_png.png | real | lowlight_weather | real_png | png | 4284x5712 | real | ai | ai | ai | 0.119788 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_038_lowlight_weather_jpg_q95.jpg | real | lowlight_weather | real_jpg | jpg | 4284x5712 | real | ai | ai | ai | 0.118318 |
| data\test_images\day14_expansion\paired_format\real_png\real_088_outdoor_street_png.png | real | outdoor_street | real_png | png | 4284x5712 | real | ai | ai | ai | 0.117293 |
| data\test_images\legacy\day8_small_30\real\real_016.jpg | real | unknown | legacy | jpg | 3024x4032 | real | ai | ai | ai | 0.116587 |
| data\test_images\day14_expansion\raw\real\indoor_home\real_023_indoor_home_native.jpeg | real | indoor_home | raw | jpeg | 3024x4032 | ai | uncertain | ai | ai | 0.116422 |
| data\test_images\day14_expansion\raw\real\nature_travel\real_059_nature_travel_native.jpeg | real | nature_travel | raw | jpeg | 4032x3024 | real | ai | ai | ai | 0.116323 |
| data\test_images\day14_expansion\paired_format\real_jpg\real_088_outdoor_street_jpg_q95.jpg | real | outdoor_street | real_jpg | jpg | 4284x5712 | real | ai | ai | ai | 0.116040 |
| data\test_images\legacy\day8_small_30\real\real_014.jpg | real | unknown | legacy | jpg | 4284x5712 | uncertain | ai | ai | ai | 0.115835 |
| data\test_images\day14_expansion\paired_format\real_png\real_100_people_partial_png.png | real | people_partial | real_png | png | 2316x3088 | ai | uncertain | uncertain | uncertain | 0.113860 |
| data\test_images\day14_expansion\raw\real\food_retail\real_003_food_retail_native.jpeg | real | food_retail | raw | jpeg | 3024x4032 | ai | uncertain | uncertain | uncertain | 0.113458 |
| data\test_images\day14_expansion\raw\real\lowlight_weather\real_039_lowlight_weather_native.jpeg | real | lowlight_weather | raw | jpeg | 4032x3024 | uncertain | ai | ai | ai | 0.111982 |
| data\test_images\day14_expansion\paired_format\real_png\real_081_outdoor_street_png.png | real | outdoor_street | real_png | png | 4284x5712 | real | ai | ai | ai | 0.111382 |

## 5. FP x Resolution Flip Intersection

| category | real_total | real_fp_count | real_fp_rate | real_flip_count | real_flip_rate | fp_and_flip_count | fp_and_flip_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| __overall__ | 330 | 145 | 0.439394 | 259 | 0.784848 | 100 | 0.689655 |
| food_retail | 45 | 17 | 0.377778 | 34 | 0.755556 | 9 | 0.529412 |
| indoor_home | 45 | 27 | 0.600000 | 36 | 0.800000 | 23 | 0.851852 |
| lowlight_weather | 45 | 23 | 0.511111 | 39 | 0.866667 | 17 | 0.739130 |
| nature_travel | 45 | 24 | 0.533333 | 33 | 0.733333 | 12 | 0.500000 |
| object_closeup | 45 | 12 | 0.266667 | 40 | 0.888889 | 12 | 1.000000 |
| outdoor_street | 45 | 18 | 0.400000 | 39 | 0.866667 | 12 | 0.666667 |
| people_partial | 30 | 6 | 0.200000 | 19 | 0.633333 | 6 | 1.000000 |
| unknown | 30 | 18 | 0.600000 | 19 | 0.633333 | 9 | 0.500000 |

## Appendix: Derived Resolution Control Set

This section describes the Day14-derived resolution control set. It is not included in main FP or main flip conclusions, and is only used to observe whether existing long_512 / long_768 / long_1024 variants are stable.

- resolution_control_total: 1200
- label distribution: {'ai': 600, 'real': 600}
- transform distribution: {'long_1024': 400, 'long_512': 400, 'long_768': 400}
- final_label distribution: {'ai': 778, 'uncertain': 422}
- uncertain count: 422

## 6. Root Cause Hypotheses

### Strong evidence

- Format bias is visible: extension 'jpg' has the highest real FP rate at 0.496503.
- Resolution resizing materially affects decisions: overall flip rate is 0.580303.
- Category-specific FP risk is visible in 'indoor_home' at rate 0.600000.
- Many samples sit near the 0.15 baseline boundary: 429/660 in [0.10, 0.18).

### Medium evidence

- No-EXIF JPEG remains elevated versus overall real FP rate (0.504202 vs 0.439394).
- The uncertain layer already catches some raw FP pressure (145 raw FP vs 84 final FP), but may need stronger handling.

### Weak evidence

- No hypothesis reached this evidence level in the current run.

## 7. Engineering Recommendations for Day16

- Consider enhancing the uncertain layer for score-near-threshold samples instead of moving the default threshold.
- Add image_quality and metadata_quality features so no-EXIF and JPEG compression are contextual signals rather than direct authenticity signals.
- Add soft-decision handling for samples near threshold 0.15 and inside the current 0.12-0.18 final-label band.
- Explore resolution-stability constraints so a single resize cannot silently flip the product-facing label.
- Add more controlled Real JPEG no-EXIF counterexamples, especially in the categories with elevated FP rates.
- Add explainable evidence to reports so FP clusters can be traced to metadata, forensic, or frequency components.

## 8. Files Generated

- `reports\day15_all_predictions.csv`
- `reports\day15_false_positive_samples.csv`
- `reports\day15_false_positive_cluster_summary.csv`
- `reports\day15_resolution_variant_predictions.csv`
- `reports\day15_resolution_flip_samples.csv`
- `reports\day15_resolution_flip_summary.csv`
- `reports\day15_fp_resolution_intersection.csv`
- `reports\day15_false_positive_resolution_report.md`
- `reports\day15_resolution_control_appendix.csv`
