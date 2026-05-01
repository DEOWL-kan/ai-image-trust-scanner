# Day4 Evaluation Report

- Evaluation time: 2026-05-01T16:48:09+08:00
- Test set path: `D:\ai image\ai-image-trust-scanner\data\test_images`
- Real image count: 10
- AI image count: 10
- Total image count: 20

## Metrics

- Accuracy: 0.5000
- Precision (AI): 0.0000
- Recall (AI): 0.0000
- F1 (AI): 0.0000

- 当前模型没有预测出任何 AI 样本，因此 AI Precision 按 0 处理。

## Confusion Matrix

| True \ Predicted | AI | Real |
| --- | ---: | ---: |
| AI | 0 | 10 |
| Real | 0 | 10 |

## Misclassified Samples

| Image | True Label | Predicted Label | Confidence | Score |
| --- | --- | --- | ---: | ---: |
| `data\test_images\ai\ai_001.png` | ai | real | 0.8452 | 0.1548 |
| `data\test_images\ai\ai_002.png` | ai | real | 0.7914 | 0.2086 |
| `data\test_images\ai\ai_003.png` | ai | real | 0.8241 | 0.1759 |
| `data\test_images\ai\ai_004.png` | ai | real | 0.8353 | 0.1647 |
| `data\test_images\ai\ai_005.png` | ai | real | 0.8557 | 0.1443 |
| `data\test_images\ai\ai_006.png` | ai | real | 0.8214 | 0.1786 |
| `data\test_images\ai\ai_007.png` | ai | real | 0.8129 | 0.1871 |
| `data\test_images\ai\ai_008.png` | ai | real | 0.8195 | 0.1805 |
| `data\test_images\ai\ai_009.png` | ai | real | 0.8055 | 0.1945 |
| `data\test_images\ai\ai_010.png` | ai | real | 0.853 | 0.147 |

## Threshold Scan

Current detector provides `final_score`, so threshold scanning was completed from 0.1 to 0.9.

## Conclusion

Current baseline accuracy is 0.5000, with AI precision 0.0000, AI recall 0.0000, and AI F1 0.0000.

## Next Optimization Suggestions

- Keep this script as the fixed Day4 evaluation baseline.
- Expand the test set while keeping real and AI samples balanced.
- Compare future detector changes with the same dataset and output metrics.
- Use threshold_scan.csv to choose a threshold based on false positive and false negative tradeoffs.
