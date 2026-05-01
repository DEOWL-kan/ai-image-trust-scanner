# Day11 Stability - Source-Level Accuracy

## Scope

- Scans `data/test_images/ai` and `data/test_images/real`.
- Runs the current baseline detector and groups accuracy by label, format, resolution bucket, and conservative source guess.
- Baseline threshold: `0.15`

## Overall

- total_images: `60`
- success_count: `60`
- error_count: `0`
- overall_accuracy: `0.550000`
- false_positive_count: `18`
- false_negative_count: `9`
- mean_score / median_score: `0.171719` / `0.172059`

## Accuracy By Format

| ground_truth | file_extension | sample_count | accuracy | false_positive_count | false_negative_count | mean_score | min_score | max_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ai | png | 30 | 0.7 | 0 | 9 | 0.167572 | 0.1146 | 0.208551 |
| real | jpg | 30 | 0.4 | 18 | 0 | 0.175866 | 0.096813 | 0.262213 |

## Accuracy By Resolution Bucket

| ground_truth | resolution_bucket | sample_count | accuracy | mean_score | median_score | score_range | std_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai | medium | 30 | 0.7 | 0.167572 | 0.16977 | 0.093951 | 0.024482 |
| real | large | 20 | 0.4 | 0.177159 | 0.183203 | 0.1654 | 0.050482 |
| real | medium | 9 | 0.444444 | 0.167091 | 0.167131 | 0.082949 | 0.026968 |
| real | small | 1 | 0.0 | 0.228971 | 0.228971 | 0.0 | 0.0 |

## Accuracy By Source Guess

| ground_truth | source_guess | sample_count | accuracy | false_positive_count | false_negative_count | mean_score |
| --- | --- | --- | --- | --- | --- | --- |
| ai | png_no_exif_export | 30 | 0.7 | 0 | 9 | 0.167572 |
| real | jpeg_no_exif_export | 18 | 0.277778 | 13 | 0 | 0.187869 |
| real | unknown | 12 | 0.583333 | 5 | 0 | 0.157861 |

## Format Anomalies

- Real `jpg` group has low accuracy `0.400000` with `18` false positives.

## Resolution Score Volatility

- `real` / `large` has score_range `0.165400` and std_score `0.050482`.
- `ai` / `medium` has score_range `0.093951` and std_score `0.024482`.

## Format Tendency Checks

AI set:
- `png`: AI-prediction rate `0.700000`, mean_score `0.167572`, n=30.

Real set:
- `jpg`: AI-prediction rate `0.600000`, mean_score `0.175866`, n=30.

## Interpretation

- Current source guesses are conservative metadata buckets, not verified capture provenance.
- A high AI-prediction rate in a Real format/source bucket indicates likely false-positive pressure.
- A low AI-prediction rate in an AI format/source bucket indicates likely false-negative pressure.
- This report observes possible source, format, and resolution bias only; it does not change model weights or threshold logic.

## Output Files

- `reports/day11_stability/source_level_accuracy.csv`
- `reports/day11_stability/source_level_accuracy_summary.json`
- `reports/day11_stability/source_level_accuracy_report.md`
- `reports/day11_stability/image_reports/source_level_accuracy/`

_Generated at 2026-05-02T02:27:12+08:00._
