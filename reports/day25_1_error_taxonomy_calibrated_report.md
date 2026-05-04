# Day25.1 Error Taxonomy Calibrated Report

Generated: 2026-05-03T15:00:13+08:00

## 1. Day25.1 Summary

- Records loaded: 2241
- Error samples analyzed: 1578
- Source records file: `D:\ai image\ai-image-trust-scanner\data\benchmark_outputs\day23\day23_benchmark_results.json`
- Global error rate: 0.7041
- Day26 recommendation: Prioritize metadata_dependency via metadata_handling_fix before model work.

## 2. Why Calibration Was Needed

Day25 correctly produced a system-wide taxonomy, but generic surface signals were too broad: `format_bias`, `metadata_dependency`, and `source_folder_bias` could be assigned from ordinary file/path/EXIF presence. Day25.1 separates weak surface evidence from medium/strong evidence so root causes are more diagnostic.

## 3. Evidence Strength Rules

- `strong`: direct flip evidence, high-confidence FP/FN evidence, high lift, or explicit score-margin evidence.
- `medium`: elevated cohort lift, uncertain samples with supporting evidence, or relevant debug risk factors without direct flip proof.
- `weak`: field/path/surface evidence only; weak generic tags cannot become primary unless no better calibrated evidence exists.
- Primary selection prefers strong over medium over weak, then applies product-specific precedence such as `no_exif_jpeg` for real-photo FP and `realistic_ai` for AI->Real FN.

## 4. Before vs After Root Cause Distribution

| tag | Day25 count | Day25.1 weak | Day25.1 medium | Day25.1 strong | primary_count | change explanation |
| --- | --- | --- | --- | --- | --- | --- |
| format_bias | 1578 | 778 | 434 | 366 | 6 | surface signals downgraded unless supported by lift/flip/margin evidence |
| high_compression | 788 | 65 | 442 | 346 | 0 | surface signals downgraded unless supported by lift/flip/margin evidence |
| metadata_dependency | 1555 | 0 | 972 | 606 | 211 | surface signals downgraded unless supported by lift/flip/margin evidence |
| no_exif_jpeg | 359 | 0 | 291 | 359 | 359 | calibrated evidence required |
| realistic_ai | 0 | 7 | 0 | 0 | 0 | calibrated evidence required |
| resolution_flip | 969 | 760 | 16 | 203 | 30 | surface signals downgraded unless supported by lift/flip/margin evidence |
| score_overlap | 1153 | 0 | 0 | 972 | 972 | surface signals downgraded unless supported by lift/flip/margin evidence |
| source_folder_bias | 1427 | 840 | 738 | 0 | 0 | mostly weak evidence after calibration |
| uncertain_boundary | 972 | 0 | 0 | 972 | 0 | calibrated evidence required |

## 5. Calibrated FP Root Cause Analysis

| primary_root_cause | count | strong | medium | weak | representative_samples |
| --- | --- | --- | --- | --- | --- |
| no_exif_jpeg | 359 | 359 | 0 | 0 | e8788bb571711a93, a23d246b50c1270d, 4c08d658de8d1ec1 |
| metadata_dependency | 210 | 210 | 0 | 0 | 3ae9f46fdbfa6480, 96453809ddd729ee, 5f6bb538824135f5 |
| resolution_flip | 30 | 30 | 0 | 0 | 2e785f2889600996, 3faeefdd16bdc460, 5ed34a9e4dc4af55 |

## 6. Calibrated FN Root Cause Analysis

| primary_root_cause | count | strong | medium | weak | representative_samples |
| --- | --- | --- | --- | --- | --- |
| format_bias | 6 | 6 | 0 | 0 | 51b496a666effedc, c75aae8f32cd5b41, eb9658fe327e769a |
| metadata_dependency | 1 | 1 | 0 | 0 | 26671651dfa1040e |

## 7. Calibrated Uncertain Root Cause Analysis

| primary_root_cause | count | strong | medium | weak | representative_samples |
| --- | --- | --- | --- | --- | --- |
| score_overlap | 972 | 972 | 0 | 0 | 9ce4c6e227891728, 89ef7f7801183068, 7783285ef7c10699 |

## 8. Folder-level Bias Analysis

| folder | total | errors | error_rate | global_error_rate | lift | dominant_error_type | source_folder_bias_strength |
| --- | --- | --- | --- | --- | --- | --- | --- |
| data/day11_resolution_control/real/long_edge_1024 | 29 | 29 | 1.0 | 0.7041 | 1.4202 | FP | medium |
| data/day11_resolution_control/real/long_edge_768 | 29 | 29 | 1.0 | 0.7041 | 1.4202 | FP | medium |
| data/day11_resolution_control/real/long_edge_1536 | 22 | 22 | 1.0 | 0.7041 | 1.4202 | FP | medium |
| data/test_images/day14_expansion/raw/ai/indoor_home | 15 | 15 | 1.0 | 0.7041 | 1.4202 | Uncertain | medium |
| data/day10_format_control/real/jpeg_q85 | 30 | 28 | 0.9333 | 0.7041 | 1.3255 | FP | medium |
| data/day10_format_control/real/jpeg_q95 | 30 | 28 | 0.9333 | 0.7041 | 1.3255 | FP | medium |
| data/day10_format_control/real/png | 30 | 28 | 0.9333 | 0.7041 | 1.3255 | Uncertain | medium |
| data/day11_resolution_control/real/long_edge_512 | 30 | 28 | 0.9333 | 0.7041 | 1.3255 | FP | medium |
| data/test_images/day14_expansion/raw/ai/food_retail | 15 | 14 | 0.9333 | 0.7041 | 1.3255 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/indoor_home | 15 | 14 | 0.9333 | 0.7041 | 1.3255 | Uncertain | medium |
| data/test_images/legacy/day8_small_30/real | 30 | 26 | 0.8667 | 0.7041 | 1.2308 | FP | medium |
| data/test_images/day14_expansion/paired_format/real_jpg | 100 | 85 | 0.85 | 0.7041 | 1.2071 | Uncertain | medium |
| data/test_images/day14_expansion/paired_format/real_png | 100 | 85 | 0.85 | 0.7041 | 1.2071 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/nature_travel | 15 | 12 | 0.8 | 0.7041 | 1.1361 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/outdoor_street | 15 | 12 | 0.8 | 0.7041 | 1.1361 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/people_partial | 10 | 8 | 0.8 | 0.7041 | 1.1361 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/food_retail | 15 | 11 | 0.7333 | 0.7041 | 1.0414 | Uncertain | medium |
| data/test_images/day14_expansion/raw/real/lowlight_weather | 15 | 11 | 0.7333 | 0.7041 | 1.0414 | FP | weak |
| data/test_images/day14_expansion/raw/ai/people_partial | 10 | 7 | 0.7 | 0.7041 | 0.9941 | Uncertain | medium |
| data/test_images/day14_expansion/resolution_control/long_1024 | 400 | 279 | 0.6975 | 0.7041 | 0.9906 | Uncertain | weak |

## 9. Format-level Bias Analysis

| format | total | errors | error_rate | FP | FN | uncertain | lift | format_bias_strength |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jpg | 1157 | 853 | 0.7373 | 0.3103 | 0.0026 | 0.4244 | 1.047 | weak |
| png | 1084 | 725 | 0.6688 | 0.2214 | 0.0037 | 0.4437 | 0.9498 | weak |

## 10. Metadata Dependency Analysis

| tag | weak | medium | strong | primary | FP | FN | Uncertain | recommended_fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| metadata_dependency | 0 | 972 | 606 | 211 | 599 | 7 | 972 | metadata_handling_fix |
| no_exif_jpeg | 0 | 291 | 359 | 359 | 359 | 0 | 291 | metadata_handling_fix |

## 11. Score Overlap and Uncertain Boundary Analysis

| tag | weak | medium | strong | primary | FP | FN | Uncertain | recommended_fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_overlap | 0 | 0 | 972 | 972 | 0 | 0 | 972 | uncertainty_policy_fix |
| uncertain_boundary | 0 | 0 | 972 | 0 | 0 | 0 | 972 | uncertainty_policy_fix |

## 12. Resolution Flip Analysis

| tag | weak | medium | strong | primary | FP | FN | Uncertain | recommended_fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resolution_flip | 760 | 16 | 203 | 30 | 474 | 0 | 505 | benchmark_protocol_fix |

## 13. Realistic AI Miss Analysis

| tag | weak | medium | strong | primary | FP | FN | Uncertain | recommended_fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| realistic_ai | 7 | 0 | 0 | 0 | 0 | 7 | 0 | model_training_needed |

## 14. Calibrated Fix Priority Ranking

| Rank | Tag | Affected | Strong | Primary | Score | Severity | Fix Category | Need Model |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | metadata_dependency | 1578 | 606 | 211 | 67.28 | critical | metadata_handling_fix | no |
| 2 | no_exif_jpeg | 650 | 359 | 359 | 65.24 | critical | metadata_handling_fix | no |
| 3 | format_bias | 1578 | 366 | 6 | 60.87 | critical | data_pipeline_fix | no |
| 4 | high_compression | 853 | 346 | 0 | 60.48 | critical | decision_policy_patch | no |
| 5 | score_overlap | 972 | 972 | 972 | 59.72 | medium | uncertainty_policy_fix | no |
| 6 | resolution_flip | 979 | 203 | 30 | 58.6 | critical | benchmark_protocol_fix | no |
| 7 | source_folder_bias | 1578 | 0 | 0 | 55.0 | critical | data_pipeline_fix | no |
| 8 | uncertain_boundary | 972 | 972 | 0 | 47.4 | medium | uncertainty_policy_fix | no |
| 9 | realistic_ai | 7 | 0 | 0 | 43.0 | high | model_training_needed | yes |

## 15. Day26 Recommendation

Prioritize metadata_dependency via metadata_handling_fix before model work.

## 16. Whether Model Change Is Needed

Model-change-required root causes: 1.

## 17. Limitations

- Calibration is deterministic evidence scoring, not causal proof.
- Weak evidence is preserved in JSON for auditability but excluded from generic primary selection.
- Flip detection uses available base-image naming patterns and benchmark evidence; richer explicit pair IDs would improve precision.
- No detector weights, uncertain thresholds, or model-training paths were changed.
