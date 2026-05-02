# Day16.1 Uncertain Decision Layer v2.1 Calibration

## Day16 v2 Problem Recap
Day16 v2 correctly exposed instability, but it rejected too many images and its definite real branch was effectively absent. Real JPG/PNG definite outputs were all false positives, and `stable_ai_high_confidence` still contained real images.

## Why v2.1 Does Not Only Use Mean Score
The multi-resolution mean can be lifted by resized variants. v2.1 separates `original_score`, `resize_mean_score`, and `resize_delta`, then requires AI decisions to pass an original-score guard while allowing low-original/high-resize-delta samples to recover into a real-safe branch.

## Resize Delta Diagnostics
- resize_delta_mean: 0.028597
- resize_delta_median: 0.027744
- resize_delta_max: 0.155256
- original_vs_mean_diff_mean: 0.021448

## v2 vs v2.1 Core Metrics

| metric | v2 | v21 |
| --- | --- | --- |
| selective_accuracy | 0.719149 | 0.816456 |
| coverage | 0.356061 | 0.478788 |
| uncertain_rate | 0.643939 | 0.521212 |
| definite_fp_count | 66 | 58 |
| definite_fn_count | 0 | 0 |

## Final Label Distribution

| final_label | count |
| --- | --- |
| ai | 221 |
| real | 95 |
| uncertain | 344 |

## Real Branch Recovery
- v21_real_output_count: 95
- stable_real_safe_v21_count: 95

## real_jpg / real_png Improvement

| group | total_images | definite_count | uncertain_count | coverage | selective_accuracy | definite_fp_count | definite_fn_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| real_jpg | 100 | 47 | 53 | 0.47 | 0.617021 | 18 | 0 |
| real_png | 100 | 43 | 57 | 0.43 | 0.604651 | 17 | 0 |

## stable_ai_high_confidence FP
- v2 definite_fp_count: 66
- v2.1 definite_fp_count: 58
- stable_ai_but_resize_biased_count: 70

## Coverage And Selective Accuracy
- v21_coverage: 0.478788
- v21_selective_accuracy: 0.816456
Coverage returns to the target band while selective accuracy remains above Day16 v2.

## Current Remaining Issues
The v2.1 real-safe branch is calibrated to a resize-bias pattern. It recovers many real outputs, but the detector score space still overlaps, so this is not a substitute for stronger underlying evidence. Remaining false positives are mostly stable high-score real images that do not show enough resize bias to reject.

## Git Recommendation
Do not commit automatically. This is a stronger Day16 candidate than v2, but it should be reviewed with the generated reports before committing.

## Day17 Suggestions
- Add a small calibration table for original-score/resize-delta quadrants.
- Investigate remaining stable AI false positives without changing fusion weights.
- Decide a product coverage target before making v2.1 the default final decision layer.

## Output Files
- resize_diagnostics_csv: `reports\day16_1_resize_bias_diagnostics.csv`
- resize_summary_json: `reports\day16_1_resize_bias_summary.json`
- v21_results_csv: `reports\day16_1_uncertain_decision_v21_results.csv`
- v21_summary_json: `reports\day16_1_uncertain_v21_summary.json`
