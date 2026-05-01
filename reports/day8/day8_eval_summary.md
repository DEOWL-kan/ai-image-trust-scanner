# Day8 Evaluation Summary

## Dataset Scale

- AI images: 30
- Real images: 30
- Total images: 60
- Successful detections: 60
- Detection errors: 0

## Threshold

- Used threshold: `0.1500`
- Threshold source: Loaded from `reports\day7_threshold_sweep.json` recommendations.recommended_default_threshold.

## Metrics

- Overall accuracy: 0.5500
- AI precision / recall / F1: 0.5385 / 0.7000 / 0.6087
- Real precision / recall / F1: 0.5714 / 0.4000 / 0.4706
- False positives: 18
- False negatives: 9

## Confusion Matrix

| Actual \ Predicted | AI-generated | Real |
| --- | ---: | ---: |
| AI-generated | 21 | 9 |
| Real | 18 | 12 |

## Typical Misclassified Samples

- `data\test_images\ai\ai_010.png`: ground truth AI-generated, predicted Real, score 0.147024, false_negative
- `data\test_images\ai\ai_020.png`: ground truth AI-generated, predicted Real, score 0.146161, false_negative
- `data\test_images\ai\ai_005.png`: ground truth AI-generated, predicted Real, score 0.144311, false_negative
- `data\test_images\ai\ai_025.png`: ground truth AI-generated, predicted Real, score 0.141403, false_negative
- `data\test_images\real\real_029.jpg`: ground truth Real, predicted AI-generated, score 0.160616, false_positive
- `data\test_images\ai\ai_014.png`: ground truth AI-generated, predicted Real, score 0.136960, false_negative
- `data\test_images\ai\ai_024.png`: ground truth AI-generated, predicted Real, score 0.135133, false_negative
- `data\test_images\ai\ai_013.png`: ground truth AI-generated, predicted Real, score 0.133096, false_negative
- `data\test_images\real\real_006.jpg`: ground truth Real, predicted AI-generated, score 0.167131, false_positive
- `data\test_images\ai\ai_011.png`: ground truth AI-generated, predicted Real, score 0.132229, false_negative
- `data\test_images\real\real_019.jpg`: ground truth Real, predicted AI-generated, score 0.170343, false_positive
- `data\test_images\real\real_021.jpg`: ground truth Real, predicted AI-generated, score 0.174747, false_positive

## Day7 Comparison

- Day7 used 20 images and recommended threshold 0.15 with accuracy 0.6000, AI precision 0.5714, AI recall 0.8000, and AI F1 0.6667.
- Day8 reran the same detector on the expanded and normalized test set with threshold 0.15.

## Day9 Optimization Suggestions

- Review false positives and false negatives separately before changing feature weights.
- Add a score uncertainty band around the Day7 threshold for manual-review cases.
- Expand real-image coverage across camera photos, screenshots, compressed social-media images, and edited images.
- Add a trained detector only after the heuristic baseline keeps stable regression reports.

## Output Files

- `reports\day8\day8_predictions.csv`
- `reports\day8\day8_eval_summary.md`
- `reports\day8\day8_confusion_matrix.png`
- `reports\day8\image_reports`

_Generated at 2026-05-01T22:14:09+08:00._
