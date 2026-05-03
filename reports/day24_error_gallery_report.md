# Day24 Error Gallery + Misclassification Review UI

Generated: 2026-05-03

## Benchmark Inputs

- Results JSON: `D:\ai image\ai-image-trust-scanner\data\benchmark_outputs\day23\day23_benchmark_results.json`
- Summary JSON: `D:\ai image\ai-image-trust-scanner\data\benchmark_outputs\day23\day23_benchmark_summary.json`
- Day23 report: `D:\ai image\ai-image-trust-scanner\reports\day23\day23_benchmark_protocol_v2_report.md`

## Sample Counts

| Metric | Count |
| --- | ---: |
| Total samples | 2241 |
| Total errors (FP + FN + Uncertain) | 1578 |
| FP | 599 |
| FN | 7 |
| Uncertain | 972 |
| TP | 599 |
| TN | 64 |
| Error rate | 70.41% |

## Error Concentration

- Scenario with most errors: `unknown` with 334 errors from 461 samples.
- Format with most errors: `jpg` with 853 errors from 1157 samples.
- Resolution bucket with most errors: `long_gt_1536` with 326 errors from 388 samples.
- Highest-volume source folders:
  - `test_images/day14_expansion/resolution_control/long_1024`: 279 errors / 400 samples
  - `test_images/day14_expansion/resolution_control/long_512`: 278 errors / 400 samples
  - `test_images/day14_expansion/resolution_control/long_768`: 271 errors / 400 samples
  - `test_images/day14_expansion/paired_format/ai_png`: 61 errors / 100 samples
  - `test_images/day14_expansion/paired_format/ai_jpg`: 58 errors / 100 samples

## Added APIs

- `GET /api/v1/errors/summary`
- `GET /api/v1/errors`
- `GET /api/v1/errors/{id}`
- `POST /api/v1/errors/{id}/review`
- Static image access under `GET /media/...`

## Added Frontend

- Error Gallery page: `/dashboard/errors`
- Alternate page path: `/errors`
- Static dashboard file: `frontend/dashboard/errors.html`

## Review Notes

- Review JSON save path: `D:\ai image\ai-image-trust-scanner\reports\day24_error_review_notes.json`
- Re-saving the same sample id updates the existing record.
- Supported manual tags: `format_bias`, `resolution_flip`, `no_exif_jpeg`, `low_texture`, `high_compression`, `realistic_ai`, `unknown`.

## Field Compatibility Notes

- The adapter accepts common aliases such as `ground_truth` / `true_label`, `final_label` / `predicted_label` / `decision`, `raw_score` / `score` / `ai_score`, and `file_ext` / `format_group`.
- Missing fields are preserved as `None` or `unknown` instead of failing.
- Missing field counts in the Day23 results currently observed:
  - `difficulty`: 2241
  - `scenario`: 461

## Known Limitations

- Day23 result JSON does not include `difficulty`, so difficulty filtering currently groups all samples as `unknown`.
- 461 samples have `scenario=unknown`; source folder and filename remain available for those samples.
- Review notes are local JSON only and do not include user authentication or multi-user locking.
- Image serving is restricted to files under the project `data` directory and does not copy or transform images.

## Day25 Suggestions

- Add review-note aggregation charts for manual tags by scenario, format, and resolution bucket.
- Add export of reviewed FP/FN cohorts to CSV for targeted model-policy analysis.
- Add side-by-side grouped views for format variants and resolution variants to make flips easier to inspect.
- Use reviewed notes to define a Day25 error taxonomy without changing detector weights.
