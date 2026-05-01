# Day10 Format Control Evaluation

## Scope

- Evaluates original images plus controlled PNG, JPEG quality 95, and JPEG quality 85 versions.
- Baseline threshold: `0.15`
- Uncertainty margin: `0.03`
- `balanced_v2_candidate` is included only as a diagnostic CSV field and is not the default strategy.

## Metrics By Format Group

| format_group | accuracy | FP | FN | TP | TN | precision | recall | F1 | decided_accuracy | coverage | uncertain_count | uncertain_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 0.5500 | 18 | 9 | 21 | 12 | 0.5385 | 0.7000 | 0.6087 | 0.5333 | 0.5000 | 30 | 0.5000 |
| png | 0.5167 | 20 | 9 | 21 | 10 | 0.5122 | 0.7000 | 0.5916 | 0.5000 | 0.4667 | 32 | 0.5333 |
| jpeg_q95 | 0.5000 | 21 | 9 | 21 | 9 | 0.5000 | 0.7000 | 0.5833 | 0.4839 | 0.5167 | 29 | 0.4833 |
| jpeg_q85 | 0.5167 | 20 | 9 | 21 | 10 | 0.5122 | 0.7000 | 0.5916 | 0.4839 | 0.5167 | 29 | 0.4833 |

## Average Raw Score

| true_label | format_group | count | avg_raw_score |
| --- | --- | ---: | ---: |
| ai | jpeg_q85 | 30 | 0.169061 |
| ai | jpeg_q95 | 30 | 0.169196 |
| ai | original | 30 | 0.167572 |
| ai | png | 30 | 0.167572 |
| real | jpeg_q85 | 30 | 0.183223 |
| real | jpeg_q95 | 30 | 0.182058 |
| real | original | 30 | 0.175866 |
| real | png | 30 | 0.179985 |

## Same-Source Format Deltas

- mean_abs_delta_png_vs_jpeg_q95: `0.002084`
- mean_abs_delta_png_vs_jpeg_q85: `0.004386`
- max_delta: `0.040620`

## Conclusion

- The controlled PNG/JPEG score deltas are small, so this run does not show strong format sensitivity inside the controlled set.
- Original-set accuracy is not far from the controlled-format average, but the original dataset still has a known format-distribution confound.
- If PNG/JPEG conversion causes large score movement, treat current detector behavior as format-sensitive.
- If original results differ from controlled PNG/JPEG results, treat the original test-set evaluation as biased.
- Baseline @ 0.15 remains the regression reference; it is not replaced by `balanced_v2_candidate`.

## Output Files

- `reports\day10_format_eval_results.csv`
- `reports\day10_format_eval_report.md`
- `reports\day10_format_eval_image_reports`

_Generated at 2026-05-02T02:08:32+08:00._
