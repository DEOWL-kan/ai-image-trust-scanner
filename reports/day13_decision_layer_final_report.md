# Day13 Decision Layer Validation Report

## 1. Purpose

Day13 validates the Day12 `uncertain` decision layer on the current labeled test set. It does not tune core detector feature weights, does not promote `balanced_v2_candidate`, and keeps baseline @ threshold 0.15 as the regression reference.

## 2. Dataset

- Test set root: `data\test_images`
- AI samples: `30`
- Real samples: `30`
- Total usable samples: `60`
- Processing errors: `0`

## 3. Baseline Result

- Baseline rule: `score >= 0.15 -> ai; otherwise real`
- total_samples: `60`
- baseline_accuracy: `0.5500`
- baseline_fp: `18`
- baseline_fn: `9`
- baseline_ai_correct: `21`
- baseline_real_correct: `12`

## 4. Final Label Result

- Final rule: `score >= 0.18 -> ai; score <= 0.12 -> real; otherwise uncertain`
- final_ai_count: `25`
- final_real_count: `5`
- final_uncertain_count: `30`
- uncertain_rate: `0.5000`
- certain_coverage: `0.5000`
- final_accuracy_on_certain: `0.5333`
- certain_fp: `13`
- certain_fn: `1`
- high_confidence_error_rate: `0.4667`

## 5. Error Absorption Analysis

- baseline_wrong_count: `27`
- baseline_wrong_but_final_uncertain_count: `13`
- uncertain_absorption_rate: `0.4815`
- baseline_correct_but_final_uncertain_count: `17`
- uncertain_overblocking_rate: `0.5152`

`uncertain` is measured as an interception/review outcome only. It is not counted as correct accuracy.

Absorbed baseline errors:

| file_path | true | score | baseline | final | ext | exif | size | flags |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `data\test_images\ai\ai_005.png` | ai | 0.144311 | real | uncertain | png | False | 1122x1402 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_010.png` | ai | 0.147024 | real | uncertain | png | False | 1122x1402 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_011.png` | ai | 0.132229 | real | uncertain | png | False | 1448x1086 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_013.png` | ai | 0.133096 | real | uncertain | png | False | 1448x1086 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_014.png` | ai | 0.136960 | real | uncertain | png | False | 1448x1086 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_020.png` | ai | 0.146161 | real | uncertain | png | False | 1448x1086 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_024.png` | ai | 0.135133 | real | uncertain | png | False | 1122x1402 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_025.png` | ai | 0.141403 | real | uncertain | png | False | 1448x1086 | no_exif;baseline_false_negative;uncertain_band;near_threshold_score |
| `data\test_images\real\real_006.jpg` | real | 0.167131 | ai | uncertain | jpg | False | 960x1280 | jpeg_format;no_exif;baseline_false_positive;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_019.jpg` | real | 0.170343 | ai | uncertain | jpg | True | 4032x3024 | jpeg_format;baseline_false_positive;uncertain_band;near_threshold_score |
| `data\test_images\real\real_021.jpg` | real | 0.174747 | ai | uncertain | jpg | False | 720x1280 | jpeg_format;no_exif;baseline_false_positive;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_023.jpg` | real | 0.179521 | ai | uncertain | jpg | False | 884x1916 | jpeg_format;no_exif;baseline_false_positive;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_029.jpg` | real | 0.160616 | ai | uncertain | jpg | False | 1179x2556 | jpeg_format;no_exif;baseline_false_positive;uncertain_band;near_threshold_score;real_jpeg_no_exif |

Overblocked baseline-correct rows:

| file_path | true | score | baseline | final | ext | exif | size | flags |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `data\test_images\ai\ai_001.png` | ai | 0.154768 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_003.png` | ai | 0.175881 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_004.png` | ai | 0.164681 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_006.png` | ai | 0.178609 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_012.png` | ai | 0.173775 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_015.png` | ai | 0.155206 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_016.png` | ai | 0.165766 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_017.png` | ai | 0.159653 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\ai\ai_029.png` | ai | 0.162104 | ai | uncertain | png | False | 1448x1086 | no_exif;uncertain_band;near_threshold_score |
| `data\test_images\real\real_003.jpg` | real | 0.136630 | real | uncertain | jpg | False | 960x1280 | jpeg_format;no_exif;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_007.jpg` | real | 0.149587 | real | uncertain | jpg | False | 960x1280 | jpeg_format;no_exif;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_008.jpg` | real | 0.138499 | real | uncertain | jpg | False | 960x1280 | jpeg_format;no_exif;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_009.jpg` | real | 0.141515 | real | uncertain | jpg | False | 884x1916 | jpeg_format;no_exif;uncertain_band;near_threshold_score;real_jpeg_no_exif |
| `data\test_images\real\real_011.jpg` | real | 0.146013 | real | uncertain | jpg | True | 4032x3024 | jpeg_format;uncertain_band;near_threshold_score |
| `data\test_images\real\real_014.jpg` | real | 0.130118 | real | uncertain | jpg | True | 5712x4284 | jpeg_format;uncertain_band;near_threshold_score |
| `data\test_images\real\real_017.jpg` | real | 0.147026 | real | uncertain | jpg | True | 4032x3024 | jpeg_format;uncertain_band;near_threshold_score |
| `data\test_images\real\real_024.jpg` | real | 0.142203 | real | uncertain | jpg | False | 2016x1225 | jpeg_format;no_exif;uncertain_band;near_threshold_score;real_jpeg_no_exif |

## 6. Remaining High-Confidence Errors

These are samples where `final_label` is still a certain `ai` or `real` label but the label is wrong.

| file_path | true | score | baseline | final | ext | exif | size | flags |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `data\test_images\ai\ai_021.png` | ai | 0.114600 | real | real | png | False | 1122x1402 | no_exif;baseline_false_negative |
| `data\test_images\real\real_001.jpg` | real | 0.208724 | ai | ai | jpg | False | 1279x1706 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_002.jpg` | real | 0.196063 | ai | ai | jpg | False | 1280x1707 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_004.jpg` | real | 0.219579 | ai | ai | jpg | False | 960x1280 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_005.jpg` | real | 0.220945 | ai | ai | jpg | True | 4032x3024 | jpeg_format;baseline_false_positive |
| `data\test_images\real\real_010.jpg` | real | 0.202450 | ai | ai | jpg | False | 4672x7008 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_013.jpg` | real | 0.222499 | ai | ai | jpg | True | 4032x3024 | jpeg_format;baseline_false_positive |
| `data\test_images\real\real_015.jpg` | real | 0.202338 | ai | ai | jpg | True | 5712x4284 | jpeg_format;baseline_false_positive |
| `data\test_images\real\real_022.jpg` | real | 0.225620 | ai | ai | jpg | False | 1179x2556 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_025.jpg` | real | 0.217730 | ai | ai | jpg | False | 1279x1706 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_026.jpg` | real | 0.196612 | ai | ai | jpg | False | 1500x1279 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_027.jpg` | real | 0.262199 | ai | ai | jpg | False | 1279x1706 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_028.jpg` | real | 0.262213 | ai | ai | jpg | False | 1279x1706 | jpeg_format;no_exif;baseline_false_positive;real_jpeg_no_exif |
| `data\test_images\real\real_030.jpg` | real | 0.228971 | ai | ai | jpg | True | 690x504 | jpeg_format;baseline_false_positive |

## 7. Format / Resolution / EXIF Observations

- Real JPG / no-EXIF JPEG false-positive rows in this run: `13`.
- AI score range: `0.114600` to `0.208551`; Real score range: `0.096813` to `0.262213`.
- AI / Real score distributions overlap from `0.114600` to `0.208551` with `30` AI and `18` Real samples inside that interval.
- Resolution bucket spread: large: baseline_acc=0.4091, uncertain=0.3636; medium: baseline_acc=0.6486, uncertain=0.5946; small: baseline_acc=0.0000, uncertain=0.0000.

### By True Label

| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ai | 30 | 0.7000 | 0 | 9 | 0.5667 | 0.4333 | 0.9231 |
| real | 30 | 0.4000 | 18 | 0 | 0.4333 | 0.5667 | 0.2353 |

### By File Extension

| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| jpg | 30 | 0.4000 | 18 | 0 | 0.4333 | 0.5667 | 0.2353 |
| png | 30 | 0.7000 | 0 | 9 | 0.5667 | 0.4333 | 0.9231 |

### By Source Folder

| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| data\test_images\ai | 30 | 0.7000 | 0 | 9 | 0.5667 | 0.4333 | 0.9231 |
| data\test_images\real | 30 | 0.4000 | 18 | 0 | 0.4333 | 0.5667 | 0.2353 |

### By Resolution Bucket

| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large | 22 | 0.4091 | 13 | 0 | 0.3636 | 0.6364 | 0.2857 |
| medium | 37 | 0.6486 | 4 | 9 | 0.5946 | 0.4054 | 0.8000 |
| small | 1 | 0.0000 | 1 | 0 | 0.0000 | 1.0000 | 0.0000 |

### By EXIF Presence

| group | total | baseline_accuracy | FP | FN | uncertain_rate | certain_coverage | final_accuracy_on_certain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| False | 48 | 0.5417 | 13 | 9 | 0.5417 | 0.4583 | 0.5455 |
| True | 12 | 0.5833 | 5 | 0 | 0.3333 | 0.6667 | 0.5000 |

## 8. Conclusion

The Day12 uncertain layer is partially effective, but it should not be treated as an overall success or a final default strategy yet. It has clear diagnostic value: overall, it absorbed `13` of `27` baseline errors, and the effect is especially strong for AI false negatives. Among AI baseline errors, `8` of `9` were moved into `uncertain`, which means the review band is useful for catching near-threshold AI samples that baseline @ `0.15` would otherwise label as Real.

However, the same score-band strategy is not sufficient for the main Real JPG false-positive cluster. Among Real baseline errors, only `5` of `18` were absorbed by `uncertain`; `13` Real samples still received a certain `final_label = ai`. This is the most important Day13 failure mode and matches the earlier Day11 conclusion that Real JPG / no-EXIF JPEG samples remain a major false-positive cluster.

The decided-only quality also does not improve over the baseline in this run. `final_accuracy_on_certain = 0.5333`, which is lower than `baseline_accuracy = 0.5500`, so the current final-label layer has not yet increased the reliability of explicit AI/Real decisions. At the same time, `uncertain_rate = 0.5000` and `certain_coverage = 0.5000`, meaning the policy withholds judgment on half of the current test set while still leaving many Real JPG false positives as certain AI decisions.

Day13 conclusion: the uncertain decision layer has diagnostic value, especially for AI false-negative absorption, but the current `0.12-0.18` score-band-only strategy is not enough to solve Real JPG / no-EXIF JPEG false positives. Day14 should move into format pairing and targeted sample expansion rather than more core weight tuning. The Day12 `final_label` strategy should remain a diagnostic candidate for now, not the final default decision policy.

Recommended Day14 sample expansion:

- More Real JPG/JPEG samples without EXIF, especially camera exports, social-media recompressions, and edited-but-real images.
- More paired resize controls from the same original images to track label stability by resolution.
- More near-threshold AI and Real samples around the 0.12-0.18 uncertain band to validate review-band width.
- Keep baseline @ 0.15 as the regression reference, keep the Day12 `final_label` policy as a diagnostic candidate, and continue avoiding core weight tuning unless a concrete detector bug is found.

## Outputs

- CSV: `reports\day13_decision_layer_validation.csv`
- Summary JSON: `reports\day13_decision_layer_summary.json`
- Markdown report: `reports\day13_decision_layer_final_report.md`

_Generated at 2026-05-02T13:31:00+08:00._
