# Day14 Difficulty Update Report

## 1. Update Goal

Update `day14_metadata.csv` with source-level and variant-level difficulty fields derived only from Day14 baseline evaluation outputs, then produce hard sample and stability issue review lists.

## 2. Rules Used

- Source difficulty uses raw native result plus format and resolution stability flips.
- Variant difficulty uses that variant's own `final_label`, `score`, and `is_uncertain` state.
- AI near-boundary scores use `0.12` to `0.20`.
- Real near-boundary scores use `0.10` to `0.18`.
- Existing `difficulty` is synchronized to `source_difficulty` for backward compatibility.

## 3. Why No Subjective Image Judging

`difficulty` here means how difficult the current detector finds the sample, not whether the image looks realistic, attractive, or visually complex. The update uses only baseline CSV results so the labels are reproducible and auditable.

## 4. Source-Level Difficulty Distribution

| label | easy | medium | hard |
| --- | --- | --- | --- |
| ai | 0 | 8 | 92 |
| real | 0 | 0 | 100 |

## 5. Variant-Level Difficulty Distribution

| difficulty | count |
| --- | --- |
| easy | 13 |
| medium | 293 |
| hard | 1494 |

## 6. Hard Source Images Distribution

| label | scene_type | count |
| --- | --- | --- |
| ai | food_retail | 15 |
| ai | indoor_home | 15 |
| ai | lowlight_weather | 15 |
| real | food_retail | 15 |
| real | indoor_home | 15 |
| real | lowlight_weather | 15 |
| real | nature_travel | 15 |
| real | object_closeup | 15 |
| real | outdoor_street | 15 |
| ai | object_closeup | 14 |
| ai | outdoor_street | 14 |
| ai | people_partial | 10 |
| real | people_partial | 10 |
| ai | nature_travel | 9 |

## 7. Hard Samples By Scene Type

| label | scene_type | count |
| --- | --- | --- |
| ai | food_retail | 135 |
| ai | indoor_home | 135 |
| ai | lowlight_weather | 135 |
| real | food_retail | 135 |
| real | indoor_home | 135 |
| real | lowlight_weather | 135 |
| real | nature_travel | 135 |
| real | object_closeup | 135 |
| real | outdoor_street | 135 |
| ai | object_closeup | 126 |
| ai | outdoor_street | 126 |
| ai | people_partial | 90 |
| real | people_partial | 90 |
| ai | nature_travel | 83 |

## 8. Hard Samples By Label

| label | count |
| --- | --- |
| real | 900 |
| ai | 830 |

## 9. Stability Issue Distribution

| stability_issue_type | source_count |
| --- | --- |
| format_flip | 0 |
| resolution_flip | 115 |
| format_and_resolution_flip | 3 |
| any_format_flip | 3 |
| any_resolution_flip | 118 |

## 10. Top 30 Image IDs For Manual Review

| image_id | label | scene_type | raw_score | raw_final_label | source_difficulty_source | stability_issue_type | hard_variant_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai_001 | ai | food_retail | 0.173999 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_002 | ai | food_retail | 0.154717 | uncertain | baseline_uncertain | none | 9 |
| ai_003 | ai | food_retail | 0.120662 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_004 | ai | food_retail | 0.151531 | uncertain | baseline_uncertain | none | 9 |
| ai_005 | ai | food_retail | 0.125919 | uncertain | baseline_uncertain | none | 9 |
| ai_006 | ai | food_retail | 0.148031 | uncertain | baseline_uncertain | none | 9 |
| ai_008 | ai | food_retail | 0.155961 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_009 | ai | food_retail | 0.157663 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_010 | ai | food_retail | 0.130857 | uncertain | baseline_uncertain | none | 9 |
| ai_011 | ai | food_retail | 0.135379 | uncertain | baseline_uncertain | none | 9 |
| ai_013 | ai | food_retail | 0.149349 | uncertain | baseline_uncertain | none | 9 |
| ai_014 | ai | food_retail | 0.144058 | uncertain | baseline_uncertain | none | 9 |
| ai_015 | ai | food_retail | 0.156034 | uncertain | baseline_uncertain | none | 9 |
| ai_016 | ai | indoor_home | 0.170478 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_017 | ai | indoor_home | 0.138900 | uncertain | baseline_uncertain | none | 9 |
| ai_018 | ai | indoor_home | 0.154507 | uncertain | baseline_uncertain | none | 9 |
| ai_019 | ai | indoor_home | 0.179842 | uncertain | baseline_uncertain | format_and_resolution_flip | 9 |
| ai_020 | ai | indoor_home | 0.162374 | uncertain | baseline_uncertain | none | 9 |
| ai_021 | ai | indoor_home | 0.167078 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_022 | ai | indoor_home | 0.132865 | uncertain | baseline_uncertain | none | 9 |
| ai_023 | ai | indoor_home | 0.157968 | uncertain | baseline_uncertain | none | 9 |
| ai_024 | ai | indoor_home | 0.121859 | uncertain | baseline_uncertain | none | 9 |
| ai_025 | ai | indoor_home | 0.167106 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_026 | ai | indoor_home | 0.147618 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_027 | ai | indoor_home | 0.142878 | uncertain | baseline_uncertain | none | 9 |
| ai_028 | ai | indoor_home | 0.116275 | real | baseline_error | resolution_flip | 9 |
| ai_029 | ai | indoor_home | 0.150586 | uncertain | baseline_uncertain | none | 9 |
| ai_030 | ai | indoor_home | 0.150396 | uncertain | baseline_uncertain | none | 9 |
| ai_032 | ai | lowlight_weather | 0.169755 | uncertain | baseline_uncertain | resolution_flip | 9 |
| ai_033 | ai | lowlight_weather | 0.135753 | uncertain | baseline_uncertain | none | 9 |

## 11. Warnings

- None

## 12. Day15 Suggestions

- Start with `day14_stability_issue_sources.csv`, because resolution flips dominate Day14 instability.
- Review Real false-positive hard sources before changing threshold or score weights.
- Keep format flip investigation secondary; PNG/JPG flips were much smaller than resolution flips.
- Use `source_difficulty` for dataset balancing and `variant_difficulty` for stress-test slicing.
