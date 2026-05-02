# Day14 Format And Resolution Generation Report

## 1. Input Raw Data Quantity

- `raw_ai_count`: 100
- `raw_real_count`: 100

## 2. Paired Format Output Quantity

- `generated_ai_png_count`: 100
- `generated_ai_jpg_count`: 100
- `generated_real_png_count`: 100
- `generated_real_jpg_count`: 100

## 3. Resolution Control Output Quantity

- `generated_long1024_count`: 400
- `generated_long768_count`: 400
- `generated_long512_count`: 400

## 4. Counts By Label

| label | native | paired_format | resolution_control | total |
| --- | --- | --- | --- | --- |
| ai | 100 | 200 | 600 | 900 |
| real | 100 | 200 | 600 | 900 |

## 5. Counts By Scene Type

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

## 6. No Upscale

- `no_upscale_count`: 0

_None_

## 7. Error List

- None

## 8. Metadata

- `metadata_total_rows`: 1800
- `skipped_existing_count`: 0

## 9. How To Run Day14 Baseline Evaluation Later

Use the updated `data/test_images/day14_expansion/metadata/day14_metadata.csv` to select evaluation splits:

- `day14_main_eval` for native raw images
- `day14_format_eval` for PNG/JPG format comparison
- `day14_resolution_eval` for long-edge resolution control

Keep threshold, final label logic, and score weights unchanged during the first Day14 baseline run so that differences reflect dataset, format, and resolution behavior rather than detector changes.
