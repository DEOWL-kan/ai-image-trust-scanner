# Day7 Threshold Calibration Report

## Day7 Goal

Day7 validates the current detector across multiple decision thresholds without changing the detector itself. The goal is to make the score-to-label tradeoff visible and choose stable operating modes for later regression checks.

## Dataset

- Real directory: `data\test_images\real`
- AI directory: `data\test_images\ai`
- Real image count: 10
- AI image count: 10
- Total image count: 20
- Successful detections: 20
- Detection errors: 0

## Input Warnings

- No input warnings.

## Threshold Sweep Results

| Threshold | Accuracy | Precision | Recall | F1 | TP | TN | FP | FN | FPR | FNR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.10 | 0.5000 | 0.5000 | 1.0000 | 0.6667 | 10 | 0 | 10 | 0 | 1.0000 | 0.0000 |
| 0.15 | 0.6000 | 0.5714 | 0.8000 | 0.6667 | 8 | 4 | 6 | 2 | 0.6000 | 0.2000 |
| 0.20 | 0.3500 | 0.2000 | 0.1000 | 0.1333 | 1 | 6 | 4 | 9 | 0.4000 | 0.9000 |
| 0.25 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.30 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.35 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.40 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.45 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.50 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.55 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.60 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.65 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.70 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.75 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.80 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.85 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |
| 0.90 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 | 10 | 0 | 10 | 0.0000 | 1.0000 |

## Recommended Thresholds

- best_f1_threshold: 0.15 (accuracy=0.6000, precision=0.5714, recall=0.8000, f1=0.6667, FP=6, FN=2)
- no_reliable_high_precision_threshold_found: Current sweep did not find a threshold with precision >= 0.80.
- high_recall_threshold: 0.10 (accuracy=0.5000, precision=0.5000, recall=1.0000, f1=0.6667, FP=10, FN=0)
- Recommended default threshold: `0.15`

The recommended default threshold uses the best-F1 operating point for the current small test set. It is a calibration baseline, not a production guarantee.

Current sweep did not find a truly high-precision operating point if `no_reliable_high_precision_threshold_found` appears above. In that case, the detector cannot currently reduce real-image false positives to a reliable level by threshold selection alone.

## Current Model Strengths

- The detector exposes a continuous `final_score`, so threshold calibration is possible.
- Batch evaluation can be repeated without changing the core detector.
- Reports keep weak evidence, score fusion, and limitations visible for review.

## Current Model Limitations

- The current system is heuristic and does not include a trained deep AI-image detector.
- The dataset is small, so threshold recommendations are sensitive to sample changes.
- Lower thresholds improve AI recall but can increase false positives on real images.
- Missing metadata, screenshots, compression, and editing can affect real and AI images in similar ways.

## Day8 Suggestions

- Add more real-camera, screenshot, social-media, compressed, and generated samples.
- Keep Day7 threshold outputs as a regression baseline before changing fusion weights.
- Review false positives and false negatives separately before changing the default threshold.
- Consider adding an uncertainty band so borderline images are routed to manual review.

## Output Files

- `reports\day7_threshold_sweep.csv`
- `reports\day7_threshold_sweep.json`
- `reports\day7_threshold_report.md`

_Generated at 2026-05-01T21:20:49+08:00._
