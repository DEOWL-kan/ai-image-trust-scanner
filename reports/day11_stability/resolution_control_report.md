# Day11 Stability - Resolution Control

## Scope

- Checks whether baseline score and binary label stay stable after resizing the same image.
- Variants preserve aspect ratio and are not cropped.
- The script avoids upscaling: target sizes larger than the source long edge are skipped.
- Original test images are not modified.
- Resolution-control data root: `data\day11_resolution_control`
- Baseline threshold: `0.15`

## Summary

- total_variants: `200`
- success_count: `200`
- error_count: `0`
- skipped_variant_count: `40`
- stale_control_files_removed: `1`
- unstable_sample_count: `86`

## By Resolution

| variant_resolution | count | avg_score_delta_vs_original | label_change_rate |
| --- | ---: | ---: | ---: |
| long_edge_1024 | 59 | 0.030859 | 0.338983 |
| long_edge_1536 | 22 | 0.038043 | 0.409091 |
| long_edge_512 | 60 | 0.035366 | 0.383333 |
| long_edge_768 | 59 | 0.035475 | 0.406780 |

## Unstable Samples

- `ai_005.png` / `long_edge_512`: score 0.144311 -> 0.159033 (delta 0.014722), label real -> ai.
- `ai_005.png` / `long_edge_768`: score 0.144311 -> 0.161261 (delta 0.016950), label real -> ai.
- `ai_005.png` / `long_edge_1024`: score 0.144311 -> 0.157437 (delta 0.013126), label real -> ai.
- `ai_010.png` / `long_edge_768`: score 0.147024 -> 0.153575 (delta 0.006551), label real -> ai.
- `ai_010.png` / `long_edge_1024`: score 0.147024 -> 0.155846 (delta 0.008822), label real -> ai.
- `ai_013.png` / `long_edge_512`: score 0.133096 -> 0.159404 (delta 0.026308), label real -> ai.
- `ai_013.png` / `long_edge_768`: score 0.133096 -> 0.154859 (delta 0.021763), label real -> ai.
- `ai_014.png` / `long_edge_512`: score 0.136960 -> 0.178053 (delta 0.041093), label real -> ai.
- `ai_014.png` / `long_edge_768`: score 0.136960 -> 0.169878 (delta 0.032918), label real -> ai.
- `ai_014.png` / `long_edge_1024`: score 0.136960 -> 0.158611 (delta 0.021651), label real -> ai.
- `ai_015.png` / `long_edge_512`: score 0.155206 -> 0.213669 (delta 0.058463), label ai -> ai.
- `ai_020.png` / `long_edge_512`: score 0.146161 -> 0.168267 (delta 0.022106), label real -> ai.
- `ai_020.png` / `long_edge_768`: score 0.146161 -> 0.171046 (delta 0.024885), label real -> ai.
- `ai_020.png` / `long_edge_1024`: score 0.146161 -> 0.165295 (delta 0.019134), label real -> ai.
- `ai_024.png` / `long_edge_768`: score 0.135133 -> 0.150159 (delta 0.015026), label real -> ai.
- `ai_025.png` / `long_edge_512`: score 0.141403 -> 0.167790 (delta 0.026387), label real -> ai.
- `ai_025.png` / `long_edge_768`: score 0.141403 -> 0.166866 (delta 0.025463), label real -> ai.
- `ai_025.png` / `long_edge_1024`: score 0.141403 -> 0.160283 (delta 0.018880), label real -> ai.
- `real_003.jpg` / `long_edge_512`: score 0.136630 -> 0.197644 (delta 0.061014), label real -> ai.
- `real_003.jpg` / `long_edge_768`: score 0.136630 -> 0.182603 (delta 0.045973), label real -> ai.
- `real_003.jpg` / `long_edge_1024`: score 0.136630 -> 0.155469 (delta 0.018839), label real -> ai.
- `real_004.jpg` / `long_edge_512`: score 0.219579 -> 0.114496 (delta 0.105083), label ai -> real.
- `real_004.jpg` / `long_edge_768`: score 0.219579 -> 0.135731 (delta 0.083848), label ai -> real.
- `real_005.jpg` / `long_edge_512`: score 0.220945 -> 0.144306 (delta 0.076639), label ai -> real.
- `real_005.jpg` / `long_edge_768`: score 0.220945 -> 0.137600 (delta 0.083345), label ai -> real.
- `real_005.jpg` / `long_edge_1024`: score 0.220945 -> 0.137123 (delta 0.083822), label ai -> real.
- `real_005.jpg` / `long_edge_1536`: score 0.220945 -> 0.168600 (delta 0.052345), label ai -> ai.
- `real_006.jpg` / `long_edge_512`: score 0.167131 -> 0.119021 (delta 0.048110), label ai -> real.
- `real_006.jpg` / `long_edge_768`: score 0.167131 -> 0.137928 (delta 0.029203), label ai -> real.
- `real_006.jpg` / `long_edge_1024`: score 0.167131 -> 0.127694 (delta 0.039437), label ai -> real.
- `real_007.jpg` / `long_edge_512`: score 0.149587 -> 0.165538 (delta 0.015951), label real -> ai.
- `real_007.jpg` / `long_edge_768`: score 0.149587 -> 0.162639 (delta 0.013052), label real -> ai.
- `real_007.jpg` / `long_edge_1024`: score 0.149587 -> 0.154953 (delta 0.005366), label real -> ai.
- `real_008.jpg` / `long_edge_512`: score 0.138499 -> 0.166162 (delta 0.027663), label real -> ai.
- `real_008.jpg` / `long_edge_768`: score 0.138499 -> 0.155734 (delta 0.017235), label real -> ai.
- `real_009.jpg` / `long_edge_512`: score 0.141515 -> 0.187840 (delta 0.046325), label real -> ai.
- `real_009.jpg` / `long_edge_768`: score 0.141515 -> 0.181650 (delta 0.040135), label real -> ai.
- `real_009.jpg` / `long_edge_1024`: score 0.141515 -> 0.172411 (delta 0.030896), label real -> ai.
- `real_009.jpg` / `long_edge_1536`: score 0.141515 -> 0.151799 (delta 0.010284), label real -> ai.
- `real_011.jpg` / `long_edge_512`: score 0.146013 -> 0.167702 (delta 0.021689), label real -> ai.

## Skipped Higher-Resolution Variants

- `768px` long-edge variants skipped: `1` because the source image long edge was smaller.
- `1024px` long-edge variants skipped: `1` because the source image long edge was smaller.
- `1536px` long-edge variants skipped: `38` because the source image long edge was smaller.

## Notes

- Resized files are experimental controls only and live under `data/day11_resolution_control/`.
- JPEG/WebP variants are re-encoded, so those rows may include both resolution and encoding effects.
- This phase reports instability only; it does not change feature weights, threshold, or model selection.

## Output Files

- `data/day11_resolution_control/`
- `reports/day11_stability/resolution_control.csv`
- `reports/day11_stability/resolution_control_summary.json`
- `reports/day11_stability/resolution_control_report.md`
- `reports/day11_stability/image_reports/resolution_control/`

_Generated at 2026-05-02T02:33:17+08:00._
