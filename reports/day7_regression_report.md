# Day7 Regression Evaluation Report

## Goal

This report reruns the current detector on the test set and compares the best-F1 operating point with the Day6 threshold baseline when that baseline is available.

## Baseline Status

- Loaded Day6 baseline from `outputs\day6\threshold_calibration.csv`.

## Current Dataset

- Real images: 10
- AI images: 10
- Total images: 20
- Successful detections: 20
- Detection errors: 0

## Current Best-F1 Metrics

- Recommended threshold: 0.1500
- Accuracy: 0.6000
- Precision: 0.5714
- Recall: 0.8000
- F1: 0.6667
- 真实图误判数量: 6
- AI 图漏判数量: 2

## Day6 vs Day7 Comparison

| Metric | Day6 Baseline | Day7 Current | Delta |
| --- | ---: | ---: | ---: |
| threshold | 0.1500 | 0.1500 | 0.0000 |
| accuracy | 0.6000 | 0.6000 | 0.0000 |
| precision | 0.5714 | 0.5714 | 0.0000 |
| recall | 0.8000 | 0.8000 | 0.0000 |
| f1 | 0.6667 | 0.6667 | 0.0000 |
| false_positive | 6 | 6 | 0.0000 |
| false_negative | 2 | 2 | 0.0000 |

## 误判样本列表 Real Images Flagged as AI

| File | Ground Truth | Score | Predicted Label |
| --- | --- | ---: | --- |
| `data\test_images\real\phone_photo_001.jpg` | real | 0.208724 | ai |
| `data\test_images\real\phone_photo_002.jpg` | real | 0.196063 | ai |
| `data\test_images\real\phone_photo_004.jpg` | real | 0.219579 | ai |
| `data\test_images\real\phone_photo_005.jpg` | real | 0.220945 | ai |
| `data\test_images\real\phone_photo_006.jpg` | real | 0.167131 | ai |
| `data\test_images\real\web_real_001.jpg` | real | 0.202450 | ai |

## 漏判样本列表 AI Images Marked as Real

| File | Ground Truth | Score | Predicted Label |
| --- | --- | ---: | --- |
| `data\test_images\ai\ai_005.png` | ai | 0.144311 | real |
| `data\test_images\ai\ai_010.png` | ai | 0.147024 | real |

## Interpretation

- This regression report checks score-to-label behavior only; it does not prove real-world detector quality.
- If Day7 metrics match Day6, the current detector is stable relative to the existing small test set.
- Any future detector or scoring change should regenerate this report and inspect false positives and false negatives before adoption.

## Outputs

- `reports\day7_regression_report.md`
- `reports\day7_threshold_sweep.csv`
- `reports\day7_threshold_sweep.json`
- `reports\day7_threshold_report.md`

_Generated at 2026-05-01T21:20:49+08:00._
