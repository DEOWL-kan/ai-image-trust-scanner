# Day14 Dataset Organization Report

## 1. Day14 Data Organization Goal

Organize the Day14 expansion dataset into a separated raw scene structure, archive the older small test set as a legacy regression set, normalize native image filenames, and regenerate Day14 native metadata with difficulty initialized to `unknown`.

## 2. Legacy Regression Set

Archived old directly scattered images into:

- `data/test_images/legacy/day8_small_30/ai`
- `data/test_images/legacy/day8_small_30/real`

Moved counts:

- AI: 0
- Real: 0

## 3. Day14 Dataset Path

Day14 raw images are organized under:

- `data/test_images/day14_expansion/raw/ai/<scene_type>/`
- `data/test_images/day14_expansion/raw/real/<scene_type>/`

## 4. Naming Rule

Native Day14 image filenames follow:

`<label>_<id>_<scene_type>_native.<ext>`

Rules applied:

- `label` is `ai` or `real`
- IDs are independent per label and continuous from `001`
- scene folders are sorted first, then original filenames are sorted within each scene
- `scene_type` is lowercased and restricted to `a-z`, `0-9`, and `_`
- difficulty is not included in filenames

## 5. Scene Type List

Detected AI scene folders:

food_retail, indoor_home, lowlight_weather, nature_travel, object_closeup, outdoor_street, people_partial

Detected Real scene folders:

food_retail, indoor_home, lowlight_weather, nature_travel, object_closeup, outdoor_street, people_partial

## 6. AI/Real Counts By Scene

AI:

| scene_type | count |
| --- | --- |
| food_retail | 15 |
| indoor_home | 15 |
| lowlight_weather | 15 |
| nature_travel | 15 |
| object_closeup | 15 |
| outdoor_street | 15 |
| people_partial | 10 |

Real:

| scene_type | count |
| --- | --- |
| food_retail | 15 |
| indoor_home | 15 |
| lowlight_weather | 15 |
| nature_travel | 15 |
| object_closeup | 15 |
| outdoor_street | 15 |
| people_partial | 10 |

## 7. Metadata Fields

`day14_metadata.csv` fields:

`image_id, label, scene_type, source_type, original_filename, original_format, current_filename, current_format, variant, resolution_type, long_edge, width, height, compression_quality, exif_status, source_device, generation_model, prompt_id, variant_group, split, difficulty, difficulty_source, difficulty_reason, notes`

## 8. Current Gaps And Warnings

- `day14_raw_ai_count`: 100
- `day14_raw_real_count`: 100
- `missing_ai_count`: 0
- `missing_real_count`: 0
- `native_metadata_row_count`: 200

Warnings:

- AI scene_type folder count is 7, expected 5 from the Day14 note.
- Real scene_type folder count is 7, expected 5 from the Day14 note.

Invalid files:

- None

Unsupported formats:

- None

Duplicate name or hash findings:

- None

## 9. Suggested Next Steps

- Use `docs/day14_format_resolution_generation_report.md` for paired format and resolution-control generation details.
- Run a baseline evaluation later to label difficulty from measured model behavior rather than subjective judgment.
