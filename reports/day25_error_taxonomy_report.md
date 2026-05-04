# Day25 Error Taxonomy Report

Generated: 2026-05-03T14:36:27+08:00

## 1. Day25 Summary

- Records loaded: 2241
- Error samples analyzed: 1578
- Source records file: `D:\ai image\ai-image-trust-scanner\data\benchmark_outputs\day23\day23_benchmark_results.json`
- Day26 recommendation: Prioritize format_bias via data_pipeline_fix before any model work.

## 2. Input Files Detected

- `reports/day24_error_gallery_report.md` (report, 3258 bytes)
- `reports/day24_error_review_notes.json` (review_notes, 165 bytes)
- `data/benchmark_outputs/day23/day23_benchmark_results.csv` (benchmark_results, 1806354 bytes)
- `data/benchmark_outputs/day23/day23_benchmark_results.json` (benchmark_results, 25074369 bytes)
- `data/benchmark_outputs/day23/day23_benchmark_summary.json` (summary, 26061 bytes)
- `data/benchmark_outputs/day23/day23_dataset_discovery_report.json` (report, 11114 bytes)
- `data/benchmark_outputs/day23/day23_skipped_samples.csv` (evidence, 56 bytes)
- `reports/day23/day23_benchmark_protocol_v2_report.md` (report, 7365 bytes)
- `outputs/api_history/batch_20260502_234558_df1236.json` (batch_history, 40259 bytes)
- `outputs/api_history/batch_20260503_004428_45e0b3.json` (batch_history, 25671 bytes)
- `outputs/api_history/batch_20260503_104834_e059a0.json` (batch_history, 208630 bytes)
- `outputs/api_history/single_20260502_234427_17d6fe.json` (batch_history, 509 bytes)
- `outputs/api_history/single_20260502_234427_6fbffc.json` (batch_history, 557 bytes)
- `outputs/api_history/single_20260502_234545_78f879.json` (batch_history, 509 bytes)
- `outputs/api_history/single_20260502_234545_a5d96b.json` (batch_history, 557 bytes)
- `outputs/api_history/single_20260502_234558_cd7666.json` (batch_history, 11541 bytes)
- `outputs/api_history/single_20260502_234631_2ee990.json` (batch_history, 509 bytes)
- `outputs/api_history/single_20260502_234631_cb6de6.json` (batch_history, 557 bytes)
- `outputs/api_history/single_20260502_235946_6647a5.json` (batch_history, 509 bytes)
- `outputs/api_history/single_20260502_235946_977193.json` (batch_history, 557 bytes)
- `outputs/api_history/single_20260503_004428_a61bb5.json` (batch_history, 11519 bytes)
- `outputs/api_history/single_20260503_005118_b5f617.json` (batch_history, 11163 bytes)
- `outputs/api_history/single_20260503_005129_859949.json` (batch_history, 11163 bytes)
- `outputs/api_history/single_20260503_005136_a6aa3c.json` (batch_history, 11156 bytes)
- `outputs/api_history/single_20260503_005144_59bdbe.json` (batch_history, 11157 bytes)

## 3. Error Taxonomy Definition

- `format_bias`: 格式相关偏差，例如 PNG/JPEG 转换后判断明显变化，或某格式集中误判
- `resolution_flip`: 分辨率缩放后 label 或 risk_level 发生不稳定变化
- `no_exif_jpeg`: 无 EXIF 的真实 JPEG 被误判为 AI 或高风险
- `high_compression`: 高压缩、社交平台压缩、低质量 JPEG 导致误判
- `low_texture`: 低纹理、纯色背景、天空、墙面、雾天、水面等细节不足场景
- `realistic_ai`: 高真实感 AI 图，纹理、光照、构图接近真实照片，导致 FN 或 uncertain
- `source_folder_bias`: 样本来源文件夹或采集方式导致模型学到来源偏差，而不是图像真实性
- `metadata_dependency`: 过度依赖 EXIF、文件格式、文件名、路径、编码信息等非视觉证据
- `score_overlap`: AI / Real 分数分布重叠，样本处于决策边界附近
- `uncertain_boundary`: 结果不是明确 FP/FN，而是被 uncertain 层拦截或置信度不足
- `unknown`: 无法从现有 evidence 判断原因

## 4. Root Cause Tagging Method

The analyzer normalizes each benchmark or batch-result sample into a common schema, classifies FP / FN / Uncertain / Correct / Unknown from expected and final labels, then scans `debug_evidence`, decision reasons, recommendations, review notes, source folder, file format, scenario, confidence, score, and path text for deterministic evidence. Folder-level concentration is computed before tagging so repeatable source-folder clusters can be labeled as `source_folder_bias`. Scores near the boundary or uncertain-layer interceptions are tagged separately as `score_overlap` and `uncertain_boundary`.

## 5. Error Distribution Table

| Root Cause | Samples | Share | Main Scenarios | Risk | Recommended Fix | Model Change | Day26 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| format_bias | 1578 | 100.0% | unknown, long_1024, long_512 | critical | data_pipeline_fix | no | yes |
| metadata_dependency | 1555 | 98.54% | unknown, long_1024, long_512 | critical | metadata_handling_fix | no | yes |
| source_folder_bias | 1427 | 90.43% | long_1024, long_512, unknown | critical | data_pipeline_fix | no | yes |
| score_overlap | 1153 | 73.07% | unknown, long_1024, long_512 | critical | uncertainty_policy_fix | no | yes |
| uncertain_boundary | 972 | 61.6% | unknown, long_1024, long_512 | medium | uncertainty_policy_fix | no | yes |
| resolution_flip | 969 | 61.41% | long_1024, long_512, long_768 | critical | benchmark_protocol_fix | no | yes |
| high_compression | 788 | 49.94% | unknown, long_512, long_1024 | critical | decision_policy_patch | no | yes |
| no_exif_jpeg | 359 | 22.75% | long_512, long_768, long_1024 | critical | metadata_handling_fix | no | yes |

## 6. Root Cause Ranking

| Root Cause | Count | Share | Representative Samples |
| --- | --- | --- | --- |
| format_bias | 1578 | 100.0% | 3ae9f46fdbfa6480, 96453809ddd729ee, 5f6bb538824135f5 |
| metadata_dependency | 1555 | 98.54% | 3ae9f46fdbfa6480, 96453809ddd729ee, 5f6bb538824135f5 |
| source_folder_bias | 1427 | 90.43% | 3ae9f46fdbfa6480, 96453809ddd729ee, 5f6bb538824135f5 |
| score_overlap | 1153 | 73.07% | 96453809ddd729ee, b199ed2a8815a0ba, bdb4a2490055cc7b |
| uncertain_boundary | 972 | 61.6% | 9ce4c6e227891728, 89ef7f7801183068, 7783285ef7c10699 |
| resolution_flip | 969 | 61.41% | 13e574bfa6bc8006, 7d85869db6b10366, 575e92b0cb954eef |
| high_compression | 788 | 49.94% | 51b496a666effedc, c75aae8f32cd5b41, 9c7013d753b76aa7 |
| no_exif_jpeg | 359 | 22.75% | e8788bb571711a93, a23d246b50c1270d, 4c08d658de8d1ec1 |

## 7. FP Root Cause Analysis

| sample_id | error_type | root_cause | severity | priority | scenario | format |
| --- | --- | --- | --- | --- | --- | --- |
| 00161195d138f299 | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 0279d4e11b657ee1 | FP | metadata_dependency | critical | 95.01 | long_1024 | png |
| 02a5725bcd9f3ba9 | FP | metadata_dependency | critical | 95.01 | long_768 | png |
| 037fd3f7777713ae | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 049b08f6fa9ae1e9 | FP | metadata_dependency | critical | 95.01 | unknown | png |
| 04c90a17b80f4fb6 | FP | metadata_dependency | critical | 95.01 | long_768 | png |
| 04eddd916e3d99f5 | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 061ff474f8b095a7 | FP | metadata_dependency | critical | 95.01 | long_1024 | png |

## 8. FN Root Cause Analysis

| sample_id | error_type | root_cause | severity | priority | scenario | format |
| --- | --- | --- | --- | --- | --- | --- |
| 26671651dfa1040e | FN | metadata_dependency | high | 87.01 | indoor_home | png |
| 51b496a666effedc | FN | metadata_dependency | high | 87.01 | jpeg_q85 | jpg |
| 6ff5ef455a26d67b | FN | metadata_dependency | high | 87.01 | unknown | png |
| 9c7013d753b76aa7 | FN | metadata_dependency | high | 87.01 | unknown | jpg |
| b68708e038e95a3f | FN | metadata_dependency | high | 87.01 | unknown | png |
| c75aae8f32cd5b41 | FN | metadata_dependency | high | 87.01 | jpeg_q95 | jpg |
| eb9658fe327e769a | FN | metadata_dependency | high | 87.01 | png | png |

## 9. Uncertain Root Cause Analysis

| sample_id | error_type | root_cause | severity | priority | scenario | format |
| --- | --- | --- | --- | --- | --- | --- |
| 00c41e9ac18c6f37 | Uncertain | metadata_dependency | medium | 69.01 | long_1024 | jpg |
| 00d29c6112720c17 | Uncertain | metadata_dependency | medium | 69.01 | long_1024 | png |
| 017e187b228c12d5 | Uncertain | metadata_dependency | medium | 69.01 | long_1024 | jpg |
| 01971fb28a56cc12 | Uncertain | metadata_dependency | medium | 69.01 | long_1024 | jpg |
| 019dae6aa9835edd | Uncertain | metadata_dependency | medium | 69.01 | long_edge_512 | png |
| 01f7e1c1e9f7d88f | Uncertain | metadata_dependency | medium | 69.01 | unknown | jpg |
| 0211f2a85c6a409d | Uncertain | metadata_dependency | medium | 69.01 | unknown | png |
| 02b1c9c0db56bcf2 | Uncertain | metadata_dependency | medium | 69.01 | long_edge_1024 | png |

## 10. Representative Samples

| sample_id | error_type | root_cause | severity | priority | scenario | format |
| --- | --- | --- | --- | --- | --- | --- |
| 00161195d138f299 | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 0279d4e11b657ee1 | FP | metadata_dependency | critical | 95.01 | long_1024 | png |
| 02a5725bcd9f3ba9 | FP | metadata_dependency | critical | 95.01 | long_768 | png |
| 037fd3f7777713ae | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 049b08f6fa9ae1e9 | FP | metadata_dependency | critical | 95.01 | unknown | png |
| 04c90a17b80f4fb6 | FP | metadata_dependency | critical | 95.01 | long_768 | png |
| 04eddd916e3d99f5 | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 061ff474f8b095a7 | FP | metadata_dependency | critical | 95.01 | long_1024 | png |
| 082623117a4fc283 | FP | metadata_dependency | critical | 95.01 | long_768 | png |
| 09ac846e1cad5300 | FP | metadata_dependency | critical | 95.01 | png | png |
| 09cf84a9585dd92e | FP | metadata_dependency | critical | 95.01 | long_512 | png |
| 0a0ea138441a4bc7 | FP | metadata_dependency | critical | 95.01 | long_512 | png |

## 11. Fix Priority Ranking

| Rank | Root Cause | Affected | Score | Severity | Fix Category | Need Model | Day26 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | format_bias | 1578 | 100 | critical | data_pipeline_fix | no | yes |
| 2 | metadata_dependency | 1555 | 99.56 | critical | metadata_handling_fix | no | yes |
| 3 | source_folder_bias | 1427 | 97.13 | critical | data_pipeline_fix | no | yes |
| 4 | score_overlap | 1153 | 91.92 | critical | uncertainty_policy_fix | no | yes |
| 5 | resolution_flip | 969 | 88.42 | critical | benchmark_protocol_fix | no | yes |
| 6 | high_compression | 788 | 84.98 | critical | decision_policy_patch | no | yes |
| 7 | no_exif_jpeg | 359 | 76.83 | critical | metadata_handling_fix | no | yes |
| 8 | uncertain_boundary | 972 | 62.48 | medium | uncertainty_policy_fix | no | yes |

## 12. Day26 Recommendation

Prioritize format_bias via data_pipeline_fix before any model work.

Start with the highest-ranked non-model fix when possible:
| Root Cause | Score | Fix Category | Recommended Fix |
| --- | --- | --- | --- |
| format_bias | 100 | data_pipeline_fix | 修数据集/格式/来源偏差 |
| metadata_dependency | 99.56 | metadata_handling_fix | 降低或校准 metadata 依赖 |
| source_folder_bias | 97.13 | data_pipeline_fix | 修数据集/格式/来源偏差 |
| score_overlap | 91.92 | uncertainty_policy_fix | 优化 uncertain 输出和用户解释 |
| resolution_flip | 88.42 | benchmark_protocol_fix | 补测试协议或分场景指标 |

## 13. Whether Model Change Is Needed

Model-change-required root causes: 0.

No Day26 model change is recommended. Keep detector weights and uncertain_decision_v21 thresholds unchanged.

## 14. Limitations

- Root-cause tags are deterministic evidence tags, not causal proof.
- `unknown` remains visible when evidence is insufficient.
- Existing benchmark evidence may contain missing scenario or difficulty fields.
- The report intentionally does not change detector weights, uncertain thresholds, or training/model configuration.
