# Day10 Summary

## What Changed

- Added a dataset format audit for `data/test_images/ai` and `data/test_images/real`.
- Added PNG/JPEG controlled copies under `data/day10_format_control/`.
- Added a format-control evaluation that reuses the current detector pipeline.
- Added a default uncertain decision layer and product-facing `final_label` output.

## Why Dataset Debiasing Matters

- The current original test set can mix label signal with file-format signal.
- If AI images are mostly PNG and Real images are mostly JPEG, accuracy can reflect encoding/provenance differences instead of genuine visual authenticity detection.
- Controlled PNG/JPEG copies let the same source image be scored under different encodings.

## PNG/JPEG Format-Control Results

| format_group | accuracy | FP | FN | TP | TN | decided_accuracy | coverage | uncertain_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.5500 | 18 | 9 | 21 | 12 | 0.5333 | 0.5000 | 0.5000 |
| png | 0.5167 | 20 | 9 | 21 | 10 | 0.5000 | 0.4667 | 0.5333 |
| jpeg_q95 | 0.5000 | 21 | 9 | 21 | 9 | 0.4839 | 0.5167 | 0.4833 |
| jpeg_q85 | 0.5167 | 20 | 9 | 21 | 10 | 0.4839 | 0.5167 | 0.4833 |

Format deltas:

- mean_abs_delta_png_vs_jpeg_q95: `0.002084`
- mean_abs_delta_png_vs_jpeg_q85: `0.004386`
- max_delta: `0.040620`

## Uncertain Decision Layer

- `threshold = 0.15`
- `uncertainty_margin = 0.03`
- `score >= 0.18` -> `final_label=ai`, `decision_status=decided`
- `score <= 0.12` -> `final_label=real`, `decision_status=decided`
- `0.12 < score < 0.18` -> `final_label=uncertain`, `decision_status=uncertain`
- `uncertain` is a refusal to force a low-confidence hard judgment, not an error.

## Final Label Output

- Product-facing outputs now include `raw_score`, `threshold`, `uncertainty_margin`, `binary_label_at_threshold`, `final_label`, `decision_status`, `confidence_distance`, and `decision_reason`.
- Legacy score fields such as `final_score` and Day8 binary prediction fields are preserved for regression continuity.

## Current Default Strategy

- baseline threshold: `0.15`
- uncertainty_margin: `0.03`
- final_label values: `ai`, `real`, `uncertain`
- `balanced_v2_candidate` remains diagnostic only and is not enabled as default.

## Conclusions Not Supported Yet

- Do not use the format-biased original test set alone to claim real detector performance.
- Do not promote `balanced_v2_candidate` to the default strategy from the current evidence.
- Original baseline @ 0.15 accuracy in this run: `0.5500` with FP `18` and FN `9`.
- Controlled-format sensitivity flag: `no`.

## Day11 Suggestions

- Expand a debiased balanced test set.
- Ensure both AI and Real classes include PNG and JPEG sources.
- Add compression quality variants, resolution variants, screenshots, and social-platform compressed images.
- Re-run threshold scans only after the debiased set is in place.

## Day10 Outputs

- `reports/day10_dataset_format_audit.csv`
- `reports/day10_dataset_format_audit.md`
- `reports/day10_format_control_mapping.csv`
- `reports/day10_format_eval_results.csv`
- `reports/day10_format_eval_report.md`
- `reports/day10_summary.md`
- `data/day10_format_control/`

_Generated at 2026-05-02T02:08:32+08:00._
