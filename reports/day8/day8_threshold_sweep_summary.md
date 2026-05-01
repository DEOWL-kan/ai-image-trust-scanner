# Day8 Threshold Sweep Summary

## Scope

- Source: `reports/day8/day8_predictions.csv`
- Scan range: `0.05` to `0.95`
- Step: `0.01`
- The detector and image set were not modified; only score-to-label thresholds were rescored.

## Threshold Performance

- Current Day7 threshold: threshold `0.15`, accuracy 0.5500, AI P/R/F1 0.5385/0.7000/0.6087, Real P/R/F1 0.5714/0.4000/0.4706, macro F1 0.5396, FP 18, FN 9
- Day8 balanced_threshold: threshold `0.15`, accuracy 0.5500, AI P/R/F1 0.5385/0.7000/0.6087, Real P/R/F1 0.5714/0.4000/0.4706, macro F1 0.5396, FP 18, FN 9
- Day8 conservative_threshold: threshold `0.18`, accuracy 0.4833, AI P/R/F1 0.4800/0.4000/0.4364, Real P/R/F1 0.4857/0.5667/0.5231, macro F1 0.4798, FP 13, FN 18
- Day8 strict_threshold: threshold `0.12`, accuracy 0.5500, AI P/R/F1 0.5273/0.9667/0.6824, Real P/R/F1 0.8000/0.1333/0.2285, macro F1 0.4555, FP 26, FN 1

## Recommendation for Day9

- Recommended Day9 threshold: `0.18` (conservative_threshold)
- Reason: Day8 shows many real images being flagged as AI, so the next regression baseline should reduce false positives while retaining a non-degenerate macro F1.

## Why Day7 Threshold May Have Failed on Day8

- Day7 was calibrated on only 20 images, while Day8 expanded the test set to 60 images.
- The added real images include harder cases, so the low Day7 threshold creates more real-image false positives.
- The current score range is narrow and overlapping across AI and real samples, making a single threshold unstable.
- The detector is still heuristic; metadata, compression, screenshots, and image processing can produce similar evidence for both classes.

## Should We Enter Algorithm Optimization?

- Yes. Threshold scanning improves operating-point selection, but it does not fix the overlap between AI and real scores.
- Day9 should first lock a conservative regression threshold, then inspect false-positive and false-negative feature patterns before changing weights or adding new detector signals.

## Output Files

- `reports\day8\day8_threshold_sweep.csv`
- `reports\day8\day8_threshold_sweep_summary.md`
- `reports\day8\day8_threshold_sweep_curve.png`
