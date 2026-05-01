# Day12 Uncertain Decision Report

## Goal

- Baseline @ 0.15 remains the default regression reference.
- `final_label` is an output-layer trusted decision: `ai`, `real`, or `uncertain`.
- `uncertain` is a refusal/review band, not an error category.
- Core detector scoring weights were not modified.
- `balanced_v2_candidate` remains diagnostic only and is not the default model.

## Decision Policy

- `BASELINE_THRESHOLD = 0.15`
- `FINAL_REAL_THRESHOLD = 0.12`
- `FINAL_AI_THRESHOLD = 0.18`
- Binary baseline: `score >= 0.15 -> ai`, `score < 0.15 -> real`.
- Final label: `score >= 0.18 -> ai`, `score <= 0.12 -> real`, otherwise `uncertain`.

## Three-Way Label Distribution

- final_ai_count: `179`
- final_real_count: `16`
- final_uncertain_count: `165`
- uncertain_rate: `0.4583`
- coverage_rate: `0.5417`

## Binary Baseline Metrics

- binary accuracy: `0.5222`
- binary false positives: `128`
- binary false negatives: `44`

| true_label | pred_ai | pred_real |
| --- | ---: | ---: |
| ai | 136 | 44 |
| real | 128 | 52 |

## Decided-Only Metrics

- decided_total: `195`
- decided_accuracy: `0.5077`
- residual_fp_after_uncertain: `92`
- residual_fn_after_uncertain: `4`

## Binary Error Capture

- binary_fp_captured_by_uncertain: `36`
- binary_fn_captured_by_uncertain: `40`
- binary_error_capture_rate: `0.4419`

## Scenario Analysis

| group | total | binary_accuracy | FP | FN | decided_total | decided_accuracy | uncertain_rate | coverage_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| real_jpeg_exif_unknown | 150 | 0.2800 | 108 | 0 | 89 | 0.1124 | 0.4067 | 0.5933 |
| ai_png | 120 | 0.7833 | 0 | 26 | 63 | 0.9683 | 0.4750 | 0.5250 |
| converted_samples | 180 | 0.5111 | 61 | 27 | 90 | 0.4889 | 0.5000 | 0.5000 |
| resized_samples | 120 | 0.5250 | 49 | 8 | 75 | 0.5200 | 0.3750 | 0.6250 |

Notes:

- `real_jpeg_exif_unknown` covers Real JPEG/JPG rows visible in the current CSV inputs, but the normalized Day10/Day11 CSVs do not include a `has_exif` field, so no-EXIF JPEG cannot be separated yet.
- `converted_samples` comes from Day10 PNG/JPEG controlled variants.
- `resized_samples` comes from Day11 resolution-control variants.

## By Format Group

| group | total | binary_accuracy | FP | FN | decided_total | decided_accuracy | uncertain_rate | coverage_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| jpeg_q85 | 60 | 0.5167 | 20 | 9 | 31 | 0.4839 | 0.4833 | 0.5167 |
| jpeg_q95 | 60 | 0.5000 | 21 | 9 | 31 | 0.4839 | 0.4833 | 0.5167 |
| original | 60 | 0.5500 | 18 | 9 | 30 | 0.5333 | 0.5000 | 0.5000 |
| png | 60 | 0.5167 | 20 | 9 | 28 | 0.5000 | 0.5333 | 0.4667 |

## By Resolution Group

| group | total | binary_accuracy | FP | FN | decided_total | decided_accuracy | uncertain_rate | coverage_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| long_edge_1024 | 60 | 0.5167 | 25 | 4 | 34 | 0.5294 | 0.4333 | 0.5667 |
| long_edge_512 | 60 | 0.5333 | 24 | 4 | 41 | 0.5122 | 0.3167 | 0.6833 |

## Sample-Level Residual False Positives

| image_path | true_label | score | binary | final | source_id | variant |
| --- | --- | ---: | --- | --- | --- | --- |
| `data\test_images\real\real_001.jpg` | real | 0.208724 | ai | ai | real/real_001 | original |
| `data\test_images\real\real_002.jpg` | real | 0.196063 | ai | ai | real/real_002 | original |
| `data\test_images\real\real_004.jpg` | real | 0.219579 | ai | ai | real/real_004 | original |
| `data\test_images\real\real_005.jpg` | real | 0.220945 | ai | ai | real/real_005 | original |
| `data\test_images\real\real_010.jpg` | real | 0.202450 | ai | ai | real/real_010 | original |
| `data\test_images\real\real_013.jpg` | real | 0.222499 | ai | ai | real/real_013 | original |
| `data\test_images\real\real_015.jpg` | real | 0.202338 | ai | ai | real/real_015 | original |
| `data\test_images\real\real_022.jpg` | real | 0.225620 | ai | ai | real/real_022 | original |
| `data\test_images\real\real_025.jpg` | real | 0.217730 | ai | ai | real/real_025 | original |
| `data\test_images\real\real_026.jpg` | real | 0.196612 | ai | ai | real/real_026 | original |
| `data\test_images\real\real_027.jpg` | real | 0.262199 | ai | ai | real/real_027 | original |
| `data\test_images\real\real_028.jpg` | real | 0.262213 | ai | ai | real/real_028 | original |
| `data\test_images\real\real_030.jpg` | real | 0.228971 | ai | ai | real/real_030 | original |
| `data\day10_format_control\real\png\real_001__png.png` | real | 0.208750 | ai | ai | real/real_001 | png |
| `data\day10_format_control\real\png\real_002__png.png` | real | 0.196118 | ai | ai | real/real_002 | png |
| `data\day10_format_control\real\png\real_004__png.png` | real | 0.220430 | ai | ai | real/real_004 | png |
| `data\day10_format_control\real\png\real_005__png.png` | real | 0.230967 | ai | ai | real/real_005 | png |
| `data\day10_format_control\real\png\real_010__png.png` | real | 0.202471 | ai | ai | real/real_010 | png |
| `data\day10_format_control\real\png\real_013__png.png` | real | 0.232756 | ai | ai | real/real_013 | png |
| `data\day10_format_control\real\png\real_015__png.png` | real | 0.212012 | ai | ai | real/real_015 | png |
| `data\day10_format_control\real\png\real_022__png.png` | real | 0.225534 | ai | ai | real/real_022 | png |
| `data\day10_format_control\real\png\real_025__png.png` | real | 0.217722 | ai | ai | real/real_025 | png |
| `data\day10_format_control\real\png\real_026__png.png` | real | 0.196639 | ai | ai | real/real_026 | png |
| `data\day10_format_control\real\png\real_027__png.png` | real | 0.262196 | ai | ai | real/real_027 | png |
| `data\day10_format_control\real\png\real_028__png.png` | real | 0.262177 | ai | ai | real/real_028 | png |
| ... 67 more rows in CSV/JSON |  |  |  |  |  |  |

## Sample-Level Residual False Negatives

| image_path | true_label | score | binary | final | source_id | variant |
| --- | --- | ---: | --- | --- | --- | --- |
| `data\test_images\ai\ai_021.png` | ai | 0.114600 | real | real | ai/ai_021 | original |
| `data\day10_format_control\ai\png\ai_021__png.png` | ai | 0.114600 | real | real | ai/ai_021 | png |
| `data\day10_format_control\ai\jpeg_q95\ai_021__jpeg_q95.jpg` | ai | 0.112943 | real | real | ai/ai_021 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q85\ai_021__jpeg_q85.jpg` | ai | 0.110164 | real | real | ai/ai_021 | jpeg_q85 |

## Uncertain Samples

| image_path | true_label | score | binary | final | source_id | variant |
| --- | --- | ---: | --- | --- | --- | --- |
| `data\test_images\ai\ai_001.png` | ai | 0.154768 | ai | uncertain | ai/ai_001 | original |
| `data\test_images\ai\ai_003.png` | ai | 0.175881 | ai | uncertain | ai/ai_003 | original |
| `data\test_images\ai\ai_004.png` | ai | 0.164681 | ai | uncertain | ai/ai_004 | original |
| `data\test_images\ai\ai_005.png` | ai | 0.144311 | real | uncertain | ai/ai_005 | original |
| `data\test_images\ai\ai_006.png` | ai | 0.178609 | ai | uncertain | ai/ai_006 | original |
| `data\test_images\ai\ai_010.png` | ai | 0.147024 | real | uncertain | ai/ai_010 | original |
| `data\test_images\ai\ai_011.png` | ai | 0.132229 | real | uncertain | ai/ai_011 | original |
| `data\test_images\ai\ai_012.png` | ai | 0.173775 | ai | uncertain | ai/ai_012 | original |
| `data\test_images\ai\ai_013.png` | ai | 0.133096 | real | uncertain | ai/ai_013 | original |
| `data\test_images\ai\ai_014.png` | ai | 0.136960 | real | uncertain | ai/ai_014 | original |
| `data\test_images\ai\ai_015.png` | ai | 0.155206 | ai | uncertain | ai/ai_015 | original |
| `data\test_images\ai\ai_016.png` | ai | 0.165766 | ai | uncertain | ai/ai_016 | original |
| `data\test_images\ai\ai_017.png` | ai | 0.159653 | ai | uncertain | ai/ai_017 | original |
| `data\test_images\ai\ai_020.png` | ai | 0.146161 | real | uncertain | ai/ai_020 | original |
| `data\test_images\ai\ai_024.png` | ai | 0.135133 | real | uncertain | ai/ai_024 | original |
| `data\test_images\ai\ai_025.png` | ai | 0.141403 | real | uncertain | ai/ai_025 | original |
| `data\test_images\ai\ai_029.png` | ai | 0.162104 | ai | uncertain | ai/ai_029 | original |
| `data\day10_format_control\ai\png\ai_001__png.png` | ai | 0.154768 | ai | uncertain | ai/ai_001 | png |
| `data\day10_format_control\ai\png\ai_003__png.png` | ai | 0.175881 | ai | uncertain | ai/ai_003 | png |
| `data\day10_format_control\ai\png\ai_004__png.png` | ai | 0.164681 | ai | uncertain | ai/ai_004 | png |
| `data\day10_format_control\ai\png\ai_005__png.png` | ai | 0.144311 | real | uncertain | ai/ai_005 | png |
| `data\day10_format_control\ai\png\ai_006__png.png` | ai | 0.178609 | ai | uncertain | ai/ai_006 | png |
| `data\day10_format_control\ai\png\ai_010__png.png` | ai | 0.147024 | real | uncertain | ai/ai_010 | png |
| `data\day10_format_control\ai\png\ai_011__png.png` | ai | 0.132229 | real | uncertain | ai/ai_011 | png |
| `data\day10_format_control\ai\png\ai_012__png.png` | ai | 0.173775 | ai | uncertain | ai/ai_012 | png |
| ... 140 more rows in CSV/JSON |  |  |  |  |  |  |

## Uncertain Samples That Were Binary Errors

| image_path | true_label | score | binary | final | source_id | variant |
| --- | --- | ---: | --- | --- | --- | --- |
| `data\test_images\ai\ai_005.png` | ai | 0.144311 | real | uncertain | ai/ai_005 | original |
| `data\test_images\ai\ai_010.png` | ai | 0.147024 | real | uncertain | ai/ai_010 | original |
| `data\test_images\ai\ai_011.png` | ai | 0.132229 | real | uncertain | ai/ai_011 | original |
| `data\test_images\ai\ai_013.png` | ai | 0.133096 | real | uncertain | ai/ai_013 | original |
| `data\test_images\ai\ai_014.png` | ai | 0.136960 | real | uncertain | ai/ai_014 | original |
| `data\test_images\ai\ai_020.png` | ai | 0.146161 | real | uncertain | ai/ai_020 | original |
| `data\test_images\ai\ai_024.png` | ai | 0.135133 | real | uncertain | ai/ai_024 | original |
| `data\test_images\ai\ai_025.png` | ai | 0.141403 | real | uncertain | ai/ai_025 | original |
| `data\day10_format_control\ai\png\ai_005__png.png` | ai | 0.144311 | real | uncertain | ai/ai_005 | png |
| `data\day10_format_control\ai\png\ai_010__png.png` | ai | 0.147024 | real | uncertain | ai/ai_010 | png |
| `data\day10_format_control\ai\png\ai_011__png.png` | ai | 0.132229 | real | uncertain | ai/ai_011 | png |
| `data\day10_format_control\ai\png\ai_013__png.png` | ai | 0.133096 | real | uncertain | ai/ai_013 | png |
| `data\day10_format_control\ai\png\ai_014__png.png` | ai | 0.136960 | real | uncertain | ai/ai_014 | png |
| `data\day10_format_control\ai\png\ai_020__png.png` | ai | 0.146161 | real | uncertain | ai/ai_020 | png |
| `data\day10_format_control\ai\png\ai_024__png.png` | ai | 0.135133 | real | uncertain | ai/ai_024 | png |
| `data\day10_format_control\ai\png\ai_025__png.png` | ai | 0.141403 | real | uncertain | ai/ai_025 | png |
| `data\day10_format_control\ai\jpeg_q95\ai_005__jpeg_q95.jpg` | ai | 0.146809 | real | uncertain | ai/ai_005 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_010__jpeg_q95.jpg` | ai | 0.148600 | real | uncertain | ai/ai_010 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_011__jpeg_q95.jpg` | ai | 0.133507 | real | uncertain | ai/ai_011 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_013__jpeg_q95.jpg` | ai | 0.131651 | real | uncertain | ai/ai_013 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_014__jpeg_q95.jpg` | ai | 0.138817 | real | uncertain | ai/ai_014 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_020__jpeg_q95.jpg` | ai | 0.145644 | real | uncertain | ai/ai_020 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_024__jpeg_q95.jpg` | ai | 0.135217 | real | uncertain | ai/ai_024 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q95\ai_025__jpeg_q95.jpg` | ai | 0.142036 | real | uncertain | ai/ai_025 | jpeg_q95 |
| `data\day10_format_control\ai\jpeg_q85\ai_005__jpeg_q85.jpg` | ai | 0.145932 | real | uncertain | ai/ai_005 | jpeg_q85 |
| ... 51 more rows in CSV/JSON |  |  |  |  |  |  |

## Inputs And Outputs

- Missing input files: None.
- `reports\day12_final_label_outputs.csv`
- `reports\day12_final_label_summary.json`
- `reports\day12_uncertain_decision_report.md`

_Generated at 2026-05-02T03:00:02+08:00._
