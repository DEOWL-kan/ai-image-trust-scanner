# Day7 Threshold Calibration

## 1. 什么是阈值

当前项目会为每张图片生成一个 `final_score`，范围是 `0.0` 到 `1.0`。这个分数不是绝对概率，而是多种弱信号融合后的实验性风险分数。

阈值就是把分数转换成标签的分界线：

- 当 `final_score >= threshold` 时，判为 `ai`
- 当 `final_score < threshold` 时，判为 `real`

例如阈值为 `0.50` 时，分数 `0.62` 会被判为 AI，分数 `0.31` 会被判为真实图。

## 2. 为什么不能只用一个固定结论

AI 图像检测不是一个只看单点结论的问题。真实照片可能丢失 EXIF、被压缩、被截图、被社交平台处理；AI 图片也可能带有复杂纹理、压缩痕迹或看起来像真实照片。

因此，同一个分数在不同使用场景下可能需要不同解释：

- 审核系统可能更重视抓出 AI 图
- 证据审查可能更重视避免误伤真实图
- 日常批量筛查可能需要在两者之间平衡

Day7 的目标就是把这种取舍显式写进报告，而不是假装一个固定阈值适合所有场景。

## 3. Precision 和 Recall 的区别

`precision` 表示：所有被判为 AI 的图片里，有多少真的属于 AI。

高 precision 适合减少误伤真实图。如果 precision 高，说明系统比较少把真实图误判为 AI。

`recall` 表示：所有真实的 AI 图片里，有多少被系统抓出来。

高 recall 适合尽量抓出 AI 图。如果 recall 高，说明系统比较少漏掉 AI 图。

## 4. 为什么降低误判可能会增加漏判

如果把阈值调高，系统会更谨慎地判 AI。这样真实图被误判为 AI 的数量通常会下降，但一些分数偏低的 AI 图也可能被放过，漏判会增加。

如果把阈值调低，系统会更敏感地判 AI。这样能抓出更多 AI 图，但真实图也更容易被误判为 AI。

这就是 precision 和 recall 的核心取舍。

## 5. 当前项目推荐的三个模式

### Strict Mode

严格判 AI，优先减少误伤真实图。

- 适合对误报很敏感的场景
- 使用 `high_precision_threshold`
- 代价是可能漏掉更多 AI 图

### Balanced Mode

默认平衡模式。

- 适合当前项目的默认实验性报告
- 使用 `best_f1_threshold`
- 在 precision 和 recall 之间做折中

### Sensitive Mode

敏感检测模式，更容易抓出 AI 图。

- 适合初筛、批量排查、人工复核前置筛选
- 使用 `high_recall_threshold`
- 代价是更容易把真实图标成 AI

## 6. 如何运行 Day7 脚本

从项目根目录运行：

```bash
python scripts/threshold_sweep.py --real-dir data/test_images/real --ai-dir data/test_images/ai --output-dir reports
```

可选调整阈值范围：

```bash
python scripts/threshold_sweep.py --start 0.10 --end 0.90 --step 0.05
```

生成回归评估报告：

```bash
python scripts/regression_eval.py --real-dir data/test_images/real --ai-dir data/test_images/ai --output-dir reports
```

如果 `outputs/day6/threshold_calibration.csv` 存在，回归报告会和 Day6 baseline 对比。如果不存在，脚本会降级为 Day7 当前版本评估报告，并在报告中说明原因。

## 7. 如何阅读 Day7 报告

主要看三个文件：

- `reports/day7_threshold_sweep.csv`：每个阈值下，每张图片的预测结果和整体指标。
- `reports/day7_threshold_sweep.json`：结构化结果，适合后续脚本读取。
- `reports/day7_threshold_report.md`：人类可读的阈值校准报告。
- `reports/day7_regression_report.md`：当前版本和 Day6 baseline 的回归对比报告。

阅读建议：

- 先看 `best_f1_threshold`，了解当前平衡点。
- 再看 `high_precision_threshold`，了解减少真实图误判时的表现。
- 再看 `high_recall_threshold`，了解尽量抓出 AI 图时的表现。
- 最后检查误判样本和漏判样本，判断问题来自阈值选择、数据集偏差，还是核心检测信号不足。

当前项目仍是实验性 AI 图像检测系统。Day7 报告用于工程校准和回归检查，不应被解释为生产级真实性判定。
