# Day11 Stability - Format Flip Rate

## Scope

- Checks whether the same source image changes score or final label after JPG/PNG conversion.
- Existing Day10 format-control images are used first. Missing conversions are generated under `data/day11_format_control/`.
- Original test images are not modified.
- Baseline threshold: `0.15`

## Summary

- total_pairs: `60`
- flip_count: `3`
- format_flip_rate: `0.050000`
- avg_score_delta: `0.002997`
- max_score_delta: `0.010701`
- threshold_cross_rate: `0.033333`
- error_pairs: `0`

## By Conversion Direction

| direction | total_pairs | flip_count | format_flip_rate | avg_score_delta | max_score_delta | threshold_cross_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JPG -> PNG | 30 | 2 | 0.066667 | 0.004128 | 0.010701 | 0.066667 |
| PNG -> JPG | 30 | 1 | 0.033333 | 0.001866 | 0.002898 | 0.000000 |

## Flipped Final Labels

- `ai/ai_006` PNG -> JPG: uncertain -> ai, score 0.178609 -> 0.180891, delta 0.002282
- `real/real_012` JPG -> PNG: real -> uncertain, score 0.117578 -> 0.128035, delta 0.010457
- `real/real_020` JPG -> PNG: real -> uncertain, score 0.112877 -> 0.123578, delta 0.010701

## Threshold Crossings

- `real/real_011` JPG -> PNG: binary real -> ai, score 0.146013 -> 0.155519
- `real/real_017` JPG -> PNG: binary real -> ai, score 0.147026 -> 0.156504

## Output Files

- `reports/day11_stability/format_flip_rate.csv`
- `reports/day11_stability/format_flip_rate_summary.json`
- `reports/day11_stability/format_flip_rate_report.md`
- `reports/day11_stability/image_reports/format_flip_rate/`

## Dependency Note

- Pillow is already present in `requirements.txt`, so no dependency change was needed.

_Generated at 2026-05-02T02:23:08+08:00._
