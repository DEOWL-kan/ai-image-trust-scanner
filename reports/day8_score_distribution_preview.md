# Day8 Score Distribution Preview

## Purpose

This Day8 preparation report analyzes the Day7 `final_score` distribution without changing the detector. It explains why threshold tuning is currently fragile and where optimization should focus next.

## Inputs

- Source JSON: `reports\day7_threshold_sweep.json`
- Generated at: 2026-05-01T21:20:37+08:00

## Real Score Distribution

| Count | Min | Max | Mean | Median | Std |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.136630 | 0.220945 | 0.178112 | 0.181597 | 0.033120 |

## AI Score Distribution

| Count | Min | Max | Mean | Median | Std |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.144311 | 0.208551 | 0.173587 | 0.177245 | 0.019788 |

## Score Overlap

- Overlap interval: 0.144311 to 0.208551 (width 0.064240)
- Separability judgment: `poorly_separable`

The current real and AI score ranges overlap strongly. This means a single threshold cannot cleanly separate both classes on the current dataset.

## Highest-Scoring Real Samples

| File | Score |
| --- | ---: |
| `data\test_images\real\phone_photo_005.jpg` | 0.220945 |
| `data\test_images\real\phone_photo_004.jpg` | 0.219579 |
| `data\test_images\real\phone_photo_001.jpg` | 0.208724 |
| `data\test_images\real\web_real_001.jpg` | 0.202450 |
| `data\test_images\real\phone_photo_002.jpg` | 0.196063 |

These are the real images most likely to become false positives when the threshold is lowered.

## Lowest-Scoring AI Samples

| File | Score |
| --- | ---: |
| `data\test_images\ai\ai_005.png` | 0.144311 |
| `data\test_images\ai\ai_010.png` | 0.147024 |
| `data\test_images\ai\ai_001.png` | 0.154768 |
| `data\test_images\ai\ai_004.png` | 0.164681 |
| `data\test_images\ai\ai_003.png` | 0.175881 |

These are the AI images most likely to become false negatives when the threshold is raised.

## Why 0.15 Is Currently Best

- Best-F1 threshold from Day7: `0.150000`
- Metrics at 0.15: accuracy=0.6000, precision=0.5714, recall=0.8000, f1=0.6667, FP=6, FN=2

The 0.15 threshold catches most AI samples while still preserving some true negatives. It is not a clean boundary; it is simply the least-bad point among the scanned thresholds for this small dataset.

## Why Performance Drops After 0.20

- Metrics at 0.20: accuracy=0.3500, precision=0.2000, recall=0.1000, f1=0.1333, FP=4, FN=9

Most AI samples have scores below or near 0.20, so raising the threshold quickly turns many AI images into false negatives. At the same time, several real images sit above 0.15, so lowering the threshold produces many false positives.

## Main Problems in Current final_score

- The score is compressed into a narrow low range rather than spreading real and AI images apart.
- Frequency features dominate many examples, but they do not consistently separate real and AI images.
- Metadata and forensic heuristics are intentionally weak, so they provide limited class separation.
- The placeholder model score is excluded from fusion, so there is no trained detector signal.
- Day5 and Day6 analysis improves explainability and calibration, but does not change `final_score`.

## Next Optimization Suggestions

- Before changing weights, compare component scores for the highest-real and lowest-AI samples.
- Add a component-level diagnostic report that lists metadata, forensic, frequency, and model scores per image.
- Consider an uncertainty band around 0.15 instead of forcing a binary label for overlapping scores.
- For Day8, optimize score separation first, then recalibrate thresholds afterward.
- Keep Day7 and this Day8 preview as regression baselines for future changes.
