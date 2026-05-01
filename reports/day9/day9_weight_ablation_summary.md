# Day9 Weight Ablation Summary

## Scope

- This is a configurable feature-weight experiment on the current 60-image Day8 test set.
- It does not change the production/default detector decision path.
- Config source: `configs\detector_weights.json`
- Dataset size: 30 AI images and 30 real images.
- Results are small-scale stage results, not production-grade model claims.

## Experiment Results

| Profile | Threshold | Accuracy | Precision | Recall | Specificity | F1 | FP | FN | TP | TN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.15 | 0.5500 | 0.5385 | 0.7000 | 0.4000 | 0.6087 | 18 | 9 | 21 | 12 |
| baseline | 0.18 | 0.4833 | 0.4800 | 0.4000 | 0.5667 | 0.4364 | 13 | 18 | 12 | 17 |
| balanced_v2_candidate | 0.15 | 0.5667 | 0.5526 | 0.7000 | 0.4333 | 0.6176 | 17 | 9 | 21 | 13 |
| balanced_v2_candidate | 0.18 | 0.4333 | 0.4091 | 0.3000 | 0.5667 | 0.3462 | 13 | 21 | 9 | 17 |
| review_safe_candidate | 0.15 | 0.5500 | 0.5385 | 0.7000 | 0.4000 | 0.6087 | 18 | 9 | 21 | 12 |
| review_safe_candidate | 0.18 | 0.4833 | 0.4800 | 0.4000 | 0.5667 | 0.4364 | 13 | 18 | 12 | 17 |
| reduce_false_positive | 0.15 | 0.3000 | 0.0000 | 0.0000 | 0.6000 | 0.0000 | 12 | 30 | 0 | 18 |
| reduce_false_positive | 0.18 | 0.4000 | 0.0000 | 0.0000 | 0.8000 | 0.0000 | 6 | 30 | 0 | 24 |
| improve_ai_recall | 0.15 | 0.5000 | 0.5000 | 0.9667 | 0.0333 | 0.6591 | 29 | 1 | 29 | 1 |
| improve_ai_recall | 0.18 | 0.5000 | 0.5000 | 0.8667 | 0.1333 | 0.6342 | 26 | 4 | 26 | 4 |

## Recommended Reading

- Best balanced-mode candidate: balanced_v2_candidate @ 0.15 (accuracy 0.5667, precision 0.5526, recall 0.7000, specificity 0.4333, F1 0.6176, FP 17, FN 9).
- Conservative stress-test profile: reduce_false_positive @ 0.18 (accuracy 0.4000, precision 0.0000, recall 0.0000, specificity 0.8000, F1 0.0000, FP 6, FN 30).
- The conservative stress-test lowers false positives by sacrificing all AI recall, so it is not suitable as a default conservative mode.
- Best metric row on the current 60-image test set: balanced_v2_candidate @ 0.15 (accuracy 0.5667, precision 0.5526, recall 0.7000, specificity 0.4333, F1 0.6176, FP 17, FN 9).
- Default recommendation remains `baseline @ 0.15` because candidate gains are diagnostic only and must be validated outside this test set.

## Interpretation

- `baseline` preserves the Day8 score behavior and remains the regression reference.
- `balanced_v2_candidate` lightly reduces frequency, forensic, and compression influence while keeping missing EXIF weak.
- `review_safe_candidate` preserves baseline binary scores but expands low-confidence routing for uncertain review.
- `reduce_false_positive` intentionally lowers weak provenance, compression/context, and blur-like signals to reduce real-image false positives.
- `improve_ai_recall` intentionally raises smooth-texture, local-consistency, frequency, and edge-anomaly signals to reduce AI false negatives.
- In this run, `reduce_false_positive` is only a conservative stress-test candidate because it lowers FP by sacrificing all AI recall.
- In this run, `improve_ai_recall` proves which signals can reduce FN, but its FP count is too high for a balanced default.
- If a profile improves one metric while worsening another, treat it as an operating-mode tradeoff rather than a universal improvement.

## Overfitting Risk

- Overfitting risk is high because this experiment uses only 60 samples: 30 AI and 30 real.
- Do not tune the default detector directly to the best row in this table.
- Record these results as Day9 ablation evidence, then validate candidate profiles on a separate holdout set before changing defaults.
- None of these results should be described as production-grade detection performance.

## Output Files

- `reports\day9\day9_weight_ablation.csv`
- `reports\day9\day9_weight_ablation_summary.md`

_Generated at 2026-05-01T23:57:12+08:00._
