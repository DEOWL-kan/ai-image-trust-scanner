# Day11 Stability - Score Distribution

## Scope

- Re-runs the current baseline detector on `data/test_images/ai` and `data/test_images/real`.
- Analyzes score distribution and threshold stability at baseline threshold `0.15`.
- Near-threshold definition: `abs(score - 0.15) <= 0.03`.

## Class Statistics

| class | count | mean | median | min | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| AI | 30 | 0.167572 | 0.169770 | 0.114600 | 0.208551 |
| Real | 30 | 0.175866 | 0.172545 | 0.096813 | 0.262213 |

## Threshold Stability

- overall_accuracy: `0.550000`
- false_positive_count: `18`
- false_negative_count: `9`
- mean_score_gap_ai_minus_real: `-0.008294`
- median_score_gap_ai_minus_real: `-0.002775`
- overlap_range: `0.1146` to `0.208551`
- near_threshold_count: `30` (0.500000)
- AI near threshold: `17`
- Real near threshold: `13`

## Answers

- AI and Real scores clearly separated? No. AI and Real scores overlap heavily; the Real mean is higher than the AI mean in this run, so the two classes are not cleanly separated by the baseline score.
- Is threshold 0.15 reasonable? Threshold 0.15 remains useful as the regression reference, but it is not stable enough for a hard-only decision. The overlap and near-threshold volume argue against treating it as a final clean separator.
- Should the uncertain decision layer remain? Yes. The uncertain decision layer should be retained because many samples sit near threshold or inside overlapping class score ranges.

## Near-Threshold Samples

| file_name | ground_truth | score | predicted_label | correct | distance_to_threshold |
| --- | --- | ---: | --- | --- | ---: |
| real_007.jpg | real | 0.149587 | real | yes | 0.000413 |
| real_017.jpg | real | 0.147026 | real | yes | 0.002974 |
| ai_010.png | ai | 0.147024 | real | no | 0.002976 |
| ai_020.png | ai | 0.146161 | real | no | 0.003839 |
| real_011.jpg | real | 0.146013 | real | yes | 0.003987 |
| ai_001.png | ai | 0.154768 | ai | yes | 0.004768 |
| ai_015.png | ai | 0.155206 | ai | yes | 0.005206 |
| ai_005.png | ai | 0.144311 | real | no | 0.005689 |
| real_024.jpg | real | 0.142203 | real | yes | 0.007797 |
| real_009.jpg | real | 0.141515 | real | yes | 0.008485 |
| ai_025.png | ai | 0.141403 | real | no | 0.008597 |
| ai_017.png | ai | 0.159653 | ai | yes | 0.009653 |
| real_029.jpg | real | 0.160616 | ai | no | 0.010616 |
| real_008.jpg | real | 0.138499 | real | yes | 0.011501 |
| ai_029.png | ai | 0.162104 | ai | yes | 0.012104 |
| ai_014.png | ai | 0.136960 | real | no | 0.013040 |
| real_003.jpg | real | 0.136630 | real | yes | 0.013370 |
| ai_004.png | ai | 0.164681 | ai | yes | 0.014681 |
| ai_024.png | ai | 0.135133 | real | no | 0.014867 |
| ai_016.png | ai | 0.165766 | ai | yes | 0.015766 |
| ai_013.png | ai | 0.133096 | real | no | 0.016904 |
| real_006.jpg | real | 0.167131 | ai | no | 0.017131 |
| ai_011.png | ai | 0.132229 | real | no | 0.017771 |
| real_014.jpg | real | 0.130118 | real | yes | 0.019882 |
| real_019.jpg | real | 0.170343 | ai | no | 0.020343 |
| ai_012.png | ai | 0.173775 | ai | yes | 0.023775 |
| real_021.jpg | real | 0.174747 | ai | no | 0.024747 |
| ai_003.png | ai | 0.175881 | ai | yes | 0.025881 |
| ai_006.png | ai | 0.178609 | ai | yes | 0.028609 |
| real_023.jpg | real | 0.179521 | ai | no | 0.029521 |

## Charts

- `reports/day11_stability/score_distribution_histogram.png`
- `reports/day11_stability/score_distribution_boxplot.png`

## Output Files

- `reports/day11_stability/score_distribution.csv`
- `reports/day11_stability/score_distribution_summary.json`
- `reports/day11_stability/score_distribution_histogram.png`
- `reports/day11_stability/score_distribution_boxplot.png`
- `reports/day11_stability/score_distribution_report.md`
- `reports/day11_stability/image_reports/score_distribution/`

_Generated at 2026-05-02T02:37:28+08:00._
