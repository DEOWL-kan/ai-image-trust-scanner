# Day11 Stability Evaluation Report

## 1. Background

Day10 confirmed that the current test set has a strong format confound: AI samples are PNG-heavy while Real samples are JPEG-heavy. Because of that, Day11 did not continue tuning feature weights or promoting candidate profiles. Instead, Day11 moved from format-bias audit into stability evaluation.

This report integrates four Day11 checks:

- `format_flip_rate`: same-source JPG/PNG conversion stability
- `source_level_accuracy`: accuracy grouped by label, format, resolution, and source guess
- `resolution_control`: score and label stability under resizing
- `score_distribution`: baseline score separation and threshold stability

## 2. Baseline Setting

- Default reference: `baseline @ threshold 0.15`
- Near-threshold / uncertainty band used for evaluation: `0.12` to `0.18` (`threshold +/- 0.03`)
- `balanced_v2_candidate` remains a diagnostic candidate only.
- No core detection weights were modified during Day11.
- No default model or default threshold was changed during Day11.

## 3. Format Flip Rate

Day11 checked whether the same source image changes score or label after JPG/PNG conversion. Existing Day10 format-control images were used first; all `60` pairs came from Day10 controls.

Summary:

| metric | value |
| --- | ---: |
| total_pairs | 60 |
| flip_count | 3 |
| format_flip_rate | 0.050000 |
| avg_score_delta | 0.002997 |
| max_score_delta | 0.010701 |
| threshold_cross_count | 2 |
| threshold_cross_rate | 0.033333 |

By direction:

| direction | total_pairs | flip_count | format_flip_rate | avg_score_delta | max_score_delta | threshold_cross_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JPG -> PNG | 30 | 2 | 0.066667 | 0.004128 | 0.010701 | 0.066667 |
| PNG -> JPG | 30 | 1 | 0.033333 | 0.001866 | 0.002898 | 0.000000 |

Interpretation: same-source format conversion causes only small average score movement. However, a small number of samples near `0.15` still cross the threshold or change final label. This means the detector is not strongly format-dependent inside the controlled PNG/JPEG test, but threshold-adjacent samples remain fragile.

## 4. Source Level Accuracy

Day11 then grouped the current original test set by class, file extension, resolution bucket, and source guess.

Overall:

| metric | value |
| --- | ---: |
| total_images | 60 |
| success_count | 60 |
| overall_accuracy | 0.550000 |
| false_positive_count | 18 |
| false_negative_count | 9 |
| mean_score | 0.171719 |
| median_score | 0.172059 |

Key grouped results:

| group | sample_count | accuracy | issue |
| --- | ---: | ---: | --- |
| AI PNG | 30 | 0.700000 | 9 false negatives |
| Real JPG | 30 | 0.400000 | 18 false positives |
| Real large resolution | 20 | 0.400000 | score_range 0.165400, std_score 0.050482 |
| Real jpeg_no_exif_export | 18 | 0.277778 | 13 false positives |
| AI medium resolution | 30 | 0.700000 | score_range 0.093951 |

Format tendency:

- AI PNG samples were predicted as AI at rate `0.700000`.
- Real JPG samples were predicted as AI at rate `0.600000`.

Interpretation: the current original test set still shows source/format pressure. Real JPG samples, especially no-EXIF JPEG exports and large-resolution real images, are a major false-positive cluster. This supports the Day10 conclusion that original-set accuracy should not be treated as a clean detector-performance claim.

## 5. Resolution Control

Day11 generated resized variants at long-edge `512`, `768`, `1024`, and `1536` pixels where the source image was large enough. The script preserved aspect ratio and skipped higher-resolution variants that would require upscaling.

Summary:

| metric | value |
| --- | ---: |
| total_variants | 200 |
| success_count | 200 |
| skipped_variant_count | 40 |
| unstable_sample_count | 86 |

By resolution:

| variant_resolution | count | avg_score_delta_vs_original | label_change_rate |
| --- | ---: | ---: | ---: |
| long_edge_512 | 60 | 0.035366 | 0.383333 |
| long_edge_768 | 59 | 0.035475 | 0.406780 |
| long_edge_1024 | 59 | 0.030859 | 0.338983 |
| long_edge_1536 | 22 | 0.038043 | 0.409091 |

Unstable samples were defined as:

- `score_delta_vs_original >= 0.05`, or
- `label_changed_vs_original = true`

Interpretation: resolution sensitivity is the strongest Day11 stability warning. Even when average score deltas are moderate, many samples cross the `0.15` threshold after resizing. This shows that the current baseline score is sensitive to scale-dependent features and should not be used as a hard binary signal without an uncertainty layer.

## 6. Score Distribution

Day11 re-ran baseline detection on the original AI/Real test set and analyzed score separation.

Class statistics:

| class | count | mean | median | min | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| AI | 30 | 0.167572 | 0.169770 | 0.114600 | 0.208551 |
| Real | 30 | 0.175866 | 0.172545 | 0.096813 | 0.262213 |

Threshold stability:

| metric | value |
| --- | ---: |
| overlap_low | 0.114600 |
| overlap_high | 0.208551 |
| near_threshold_count | 30 |
| near_threshold_rate | 0.500000 |
| AI near threshold | 17 |
| Real near threshold | 13 |
| false_positive_count | 18 |
| false_negative_count | 9 |

Interpretation: AI and Real score distributions are not clearly separated. The Real mean score is slightly higher than the AI mean score in this run, and half of the test set sits inside the near-threshold band. This is direct evidence that threshold `0.15` is useful for regression continuity but weak as a hard-only production boundary.

Charts:

- `reports/day11_stability/score_distribution_histogram.png`
- `reports/day11_stability/score_distribution_boxplot.png`

## 7. Key Findings

- Format dependency still exists, but controlled JPG/PNG conversion produced small average deltas. The main format issue is not large same-source conversion drift; it is that the original test set is format-confounded.
- The detector is resolution-sensitive. Resizing produced high label-change rates, from `0.338983` to `0.409091` depending on target resolution.
- Unstable samples are common. Day11 found `86` unstable resolution-control variants and `30` near-threshold original samples.
- Threshold `0.15` should continue as the baseline regression reference, but it is not stable enough to be the only decision layer.
- Real JPG/no-EXIF samples are a major false-positive cluster. AI PNG samples still include a meaningful false-negative cluster.
- The current baseline behaves like a weak heuristic risk score, not a robust binary detector.

## 8. Decision

Day11 conclusion:

- Keep `baseline @ threshold 0.15` as the default regression reference.
- Do not promote `balanced_v2_candidate` to the default model.
- Do not modify core detection weights based on the current biased and unstable evidence.
- Add or formalize an `uncertain` decision layer around the baseline threshold.
- Treat scores in `0.12` to `0.18` as low-confidence / review-needed by default.
- Continue reporting raw score and binary threshold label for regression continuity, but prefer product-facing `final_label` values: `ai`, `real`, `uncertain`.

The practical Day11 decision is: threshold `0.15` remains useful, but only with an uncertainty band and clearer final-label semantics.

## 9. Suggested Day12 Plan

Day12 should move from evaluation into decision-output stabilization:

1. Formalize the uncertain decision layer.
   - Use `threshold = 0.15`.
   - Use `uncertainty_margin = 0.03`.
   - Map `score >= 0.18` to `final_label = ai`.
   - Map `score <= 0.12` to `final_label = real`.
   - Map `0.12 < score < 0.18` to `final_label = uncertain`.

2. Standardize final output fields.
   - Preserve `raw_score`.
   - Preserve `threshold`.
   - Preserve `binary_label_at_threshold` for regression.
   - Add or consistently expose `final_label`, `decision_status`, `confidence_distance`, and `decision_reason`.

3. Split stable and unstable samples.
   - Stable samples: no label flip across format/resolution checks and not near threshold.
   - Unstable samples: threshold-adjacent, format-flipped, resolution-flipped, or score delta above stability limits.
   - Use this split for future regression reports instead of a single flat accuracy number.

4. Improve dataset construction strategy.
   - Build balanced AI and Real subsets across PNG/JPEG/WebP.
   - Include matched resolution buckets.
   - Include camera EXIF, no-EXIF exports, web/social JPEGs, screenshots, and edited images as explicit strata.
   - Avoid using the current AI-PNG vs Real-JPG original set as the sole performance benchmark.

5. Keep model and weights unchanged until the dataset is less confounded.
   - Do not tune weights against the current biased test set.
   - Re-run threshold sweeps only after a balanced, stratified validation set exists.

Day11 outputs integrated:

- `reports/day11_stability/format_flip_rate.csv`
- `reports/day11_stability/format_flip_rate_summary.json`
- `reports/day11_stability/source_level_accuracy.csv`
- `reports/day11_stability/source_level_accuracy_summary.json`
- `reports/day11_stability/resolution_control.csv`
- `reports/day11_stability/resolution_control_summary.json`
- `reports/day11_stability/score_distribution.csv`
- `reports/day11_stability/score_distribution_summary.json`

_Generated at 2026-05-02T02:45:00+08:00._
