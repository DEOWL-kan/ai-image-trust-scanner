# Day23 Benchmark Protocol v2 Report

## 1. Objective

Day23 does not optimize detection weights, add pretrained models, or change the product/API output contract. The goal is to establish a reproducible Benchmark Protocol v2 for long-term regression tracking of the current AI image trust scanner.

## 2. Dataset Structure

| Item | Value |
| --- | ---: |
| ai samples | 1111 |
| real samples | 1130 |
| total images before label filter | 2241 |
| labeled images | 2241 |
| skipped unknown label images | 0 |
| ai label dirs | data\day10_format_control\ai, data\day11_resolution_control\ai, data\samples_ai, data\test_images\day14_expansion\paired_format\ai_jpg, data\test_images\day14_expansion\paired_format\ai_png, data\test_images\day14_expansion\raw\ai, data\test_images\day14_expansion\resolution_control, data\test_images\legacy\day8_small_30\ai |
| real label dirs | data\day10_format_control\real, data\day11_resolution_control\real, data\test_images\day14_expansion\paired_format\real_jpg, data\test_images\day14_expansion\paired_format\real_png, data\test_images\day14_expansion\raw\real, data\test_images\day14_expansion\resolution_control, data\test_images\legacy\day8_small_30\real |
| scenarios | food_retail, indoor_home, jpeg_q85, jpeg_q95, long_1024, long_512, long_768, long_edge_1024, long_edge_1536, long_edge_512, long_edge_768, lowlight_weather, nature_travel, object_closeup, outdoor_street, people_partial, png, unknown |
| formats | jpeg, jpg, png |

## 3. Evaluation Views

- strict_binary_view: uncertain outputs are counted as incorrect when computing strict accuracy.
- selective_view: uncertain outputs are removed from binary accuracy; coverage_rate and uncertain_rate are reported separately.
- triage_view: ai, real, and uncertain are treated as three product-routing buckets.

## Dataset Discovery Diagnostics

| Item | Value |
| --- | ---: |
| total_image_files_found_before_label_filter | 2241 |
| labeled_image_count | 2241 |
| ai_count | 1111 |
| real_count | 1130 |
| skipped_unknown_label_count | 0 |
| preprocessing_label_lost | no visible skipped label-loss cluster |

Top skipped directories:

| Parent Directory | Skipped Images |
| --- | ---: |
| none | 0 |

Skipped reason: unknown ground-truth label. When transformed files lose ai/real in both output path and safe filename prefix, preserve ai/real in the output path or metadata before using them as benchmark samples.

## 4. Overall Metrics

| Metric | Value |
| --- | ---: |
| total_samples | 2241 |
| valid_samples | 2241 |
| error_count | 0 |
| ai_samples | 1111 |
| real_samples | 1130 |
| accuracy_strict | 29.59% |
| precision_ai | 50.00% |
| recall_ai | 98.84% |
| f1_ai | 0.6641 |
| specificity | 9.65% |
| false_positive_rate | 53.01% |
| false_negative_rate | 0.63% |
| uncertain_rate | 43.37% |
| coverage_rate | 56.63% |
| selective_accuracy | 52.25% |
| average_confidence | 0.6923 |
| median_confidence | 0.8200 |

## 5. Confusion Matrix

| Ground Truth / Prediction | AI | Real | Uncertain |
| --- | ---: | ---: | ---: |
| AI | 599 | 7 | 505 |
| Real | 599 | 64 | 467 |

Metric definitions: TP = ground_truth=ai and predicted=ai; TN = ground_truth=real and predicted=real; FP = ground_truth=real and predicted=ai; FN = ground_truth=ai and predicted=real. strict_accuracy = (TP + TN) / valid_samples. coverage_rate = clear ai or real predictions / valid_samples. selective_accuracy = correct clear predictions / clear predictions. uncertain_rate = uncertain predictions / valid_samples. precision_ai = TP / (TP + FP). recall_ai = TP / (TP + FN). f1_ai = 2 * precision_ai * recall_ai / (precision_ai + recall_ai). false_positive_rate = FP / real_samples. false_negative_rate = FN / ai_samples.

## 6. Scenario Metrics

| Scenario | Total | AI | Real | Strict Acc | Selective Acc | Uncertain | FP | FN | FPR | FNR | Avg Conf | Main Failure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| food_retail | 30 | 15 | 15 | 16.67% | 62.50% | 73.33% | 3 | 0 | 20.00% | 0.00% | 0.5883 | high_uncertainty |
| indoor_home | 30 | 15 | 15 | 3.33% | 20.00% | 83.33% | 3 | 1 | 20.00% | 6.67% | 0.5507 | high_uncertainty |
| jpeg_q85 | 60 | 30 | 30 | 25.00% | 48.39% | 48.33% | 15 | 1 | 50.00% | 3.33% | 0.6700 | high_uncertainty |
| jpeg_q95 | 60 | 30 | 30 | 25.00% | 48.39% | 48.33% | 15 | 1 | 50.00% | 3.33% | 0.6688 | high_uncertainty |
| long_1024 | 400 | 200 | 200 | 30.25% | 49.19% | 38.50% | 125 | 0 | 62.50% | 0.00% | 0.7135 | high_uncertainty |
| long_512 | 400 | 200 | 200 | 30.50% | 45.86% | 33.50% | 144 | 0 | 72.00% | 0.00% | 0.7287 | mixed |
| long_768 | 400 | 200 | 200 | 32.25% | 48.50% | 33.50% | 137 | 0 | 68.50% | 0.00% | 0.7305 | mixed |
| long_edge_1024 | 59 | 30 | 29 | 30.51% | 52.94% | 42.37% | 16 | 0 | 55.17% | 0.00% | 0.7000 | high_uncertainty |
| long_edge_1536 | 22 | 0 | 22 | 0.00% | 0.00% | 40.91% | 13 | 0 | 59.09% | n/a | 0.7064 | mixed |
| long_edge_512 | 60 | 30 | 30 | 35.00% | 51.22% | 31.67% | 20 | 0 | 66.67% | 0.00% | 0.7312 | mixed |
| long_edge_768 | 59 | 30 | 29 | 33.90% | 54.05% | 37.29% | 17 | 0 | 58.62% | 0.00% | 0.7173 | high_uncertainty |
| lowlight_weather | 30 | 15 | 15 | 36.67% | 64.71% | 43.33% | 6 | 0 | 40.00% | 0.00% | 0.6867 | high_uncertainty |
| nature_travel | 30 | 15 | 15 | 50.00% | 78.95% | 36.67% | 4 | 0 | 26.67% | 0.00% | 0.7133 | high_uncertainty |
| object_closeup | 30 | 15 | 15 | 40.00% | 80.00% | 50.00% | 3 | 0 | 20.00% | 0.00% | 0.6650 | high_uncertainty |
| outdoor_street | 30 | 15 | 15 | 40.00% | 85.71% | 53.33% | 2 | 0 | 13.33% | 0.00% | 0.6550 | high_uncertainty |
| people_partial | 20 | 10 | 10 | 25.00% | 71.43% | 65.00% | 2 | 0 | 20.00% | 0.00% | 0.6190 | high_uncertainty |
| png | 60 | 30 | 30 | 23.33% | 50.00% | 53.33% | 13 | 1 | 43.33% | 3.33% | 0.6550 | high_uncertainty |
| unknown | 461 | 231 | 230 | 27.55% | 66.49% | 58.57% | 61 | 3 | 26.52% | 1.30% | 0.6324 | high_uncertainty |

## 7. Format Metrics

| Format | Total | Strict Acc | Selective Acc | Uncertain | FPR | FNR | Avg Conf |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| jpg | 1157 | 26.27% | 45.65% | 42.44% | 51.51% | 0.65% | 0.6952 |
| png | 1084 | 33.12% | 59.54% | 44.37% | 55.43% | 0.61% | 0.6891 |
| webp | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| others | 0 | n/a | n/a | n/a | n/a | n/a | n/a |

## 8. Key Findings

- False positives are elevated: FP=599, FPR=53.01%.
- False negatives are currently contained: FN=7, FNR=0.63%.
- Least stable scenarios by strict accuracy/uncertainty: long_edge_1536, indoor_home, food_retail.
- Least stable formats by strict accuracy/uncertainty: jpg, png.
- Selective view is stronger than strict view: 52.25% vs 29.59%.
- Uncertainty is high at 43.37%.

## 9. Current Bottlenecks

- Some samples route to uncertain, reducing strict binary accuracy.
- Real-image false positives still need case-level review.
- AI-image misses still need scenario-level review.

## 10. Recommended Day24 Direction

- Build an Error Gallery + Misclassification Review UI.
- Add FP/FN case browser filters by scenario and format.
- Add difficult sample tagging for uncertain, false-positive, and false-negative cases.
- Lock this benchmark output as the first Protocol v2 regression baseline.
