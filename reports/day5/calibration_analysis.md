# Day5 Calibration Analysis

Generated from `reports/day5/feature_summary.csv`.

This analysis is a calibration note for the current explainable heuristics. It does not change the scoring logic and should not be treated as a final detector evaluation.

## Dataset Summary

| true_label | count | avg risk_score | min risk_score | max risk_score | avg sharpness_score | avg edge_density | avg color_entropy | avg noise_score | has_exif ratio | avg jpeg_quality_estimate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ai | 10 | 46.5000 | 43.0000 | 59.0000 | 1294.4889 | 0.1786 | 7.5009 | 62.1387 | 0.0000 | N/A |
| real | 10 | 45.4000 | 36.0000 | 66.0000 | 1063.1433 | 0.1417 | 7.2804 | 50.0697 | 0.1000 | 59.8290 |

## Prediction Distribution

| true_label | likely_real | uncertain | likely_ai |
| --- | ---: | ---: | ---: |
| ai | 0 | 10 | 0 |
| real | 0 | 9 | 1 |

## Calibration Notes

- Risk score has weak separation on the current small test set.
- Sharpness, edge density, color entropy, and noise score show some separation, but this dataset has AI images with higher averages than Real images.
- Missing EXIF is weak as a standalone signal because Real images can also lack EXIF after phone, web, or platform processing.
- JPEG quality is only available for JPEG files here, while AI samples are PNG, so it should be treated as source context rather than general AI evidence.
- Current thresholds are conservative; lowering the likely-AI threshold before recalibrating feature weights would likely increase real-image false positives.

## Misjudged Real Images

| file_name | risk_score | prediction | sharpness_score | edge_density | color_entropy | noise_score | has_exif | jpeg_quality_estimate |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| phone_photo_003.jpg | 66.0000 | likely_ai | 277.4828 | 0.0301 | 6.8689 | 10.7103 | False | 54.5000 |

## Low-Risk AI Images

| file_name | risk_score | sharpness_score | edge_density | color_entropy | noise_score |
| --- | ---: | ---: | ---: | ---: | ---: |
| ai_001.png | 43.0000 | 1151.7681 | 0.1814 | 7.3232 | 56.3377 |
| ai_002.png | 43.0000 | 2144.3703 | 0.2546 | 7.5230 | 96.8278 |
| ai_003.png | 43.0000 | 1595.5557 | 0.2151 | 7.7694 | 78.8130 |
| ai_009.png | 43.0000 | 2321.8043 | 0.2791 | 7.3373 | 82.9816 |
| ai_010.png | 43.0000 | 1200.5606 | 0.2010 | 7.6199 | 65.7932 |

## Recommendations

- Keep scoring weights unchanged for Day5 closeout; this file is analysis only.
- Recalibrate detail-feature direction before changing the likely-AI threshold.
- Reduce reliance on missing EXIF as a standalone risk signal in future tuning.
- Treat JPEG quality and file format as collection-context notes, not direct authenticity proof.
- Add more diverse real and AI samples before using risk_score as a stronger decision aid.
