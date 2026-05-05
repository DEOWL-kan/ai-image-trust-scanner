# AI Image Trust Scanner

## Project Overview

AI Image Trust Scanner is a product-oriented AI image authenticity detection system with Web/API dashboard, uncertainty decision layer, error taxonomy, and benchmark reports.

The project combines multiple weak signals instead of making a single absolute claim. It should be treated as an engineering prototype and product risk-assessment workflow, not a legal forensic conclusion or a final trained detector.

## Current Progress

- Day16: uncertain decision layer v2.1 calibration
- Day17: product-level output schema
- Day19: FastAPI single-image detect endpoint
- Day20: batch detection API and result history export
- Day21: dashboard data API
- Day22: web dashboard v1
- Day23: benchmark protocol v2
- Day24: error gallery and misclassification review UI
- Day25: error taxonomy, root cause tagging, and fix priority ranking
- Day25.1: calibrated root cause tagging with evidence strength scoring

## Core Features

- Single image detection
- Batch detection
- Product-level JSON output
- Dashboard summary and recent-results API
- Error gallery for FP / FN / uncertain samples
- Error taxonomy and root cause tagging
- Calibrated evidence strength scoring
- Fix priority ranking
- Benchmark protocol v2 reports
- JSON, CSV, and Markdown reporting outputs

## API Endpoints

- `POST /api/v1/detect`
- `POST /api/v1/detect/batch`
- `GET /dashboard/summary`
- `GET /dashboard/recent-results`
- `GET /dashboard/chart-data`
- `GET /dashboard/error-taxonomy`
- `GET /dashboard/error-taxonomy?version=calibrated`
- `GET /api/v1/error-taxonomy`
- `GET /api/v1/error-taxonomy?version=calibrated`

## Day25 / Day25.1 Reports

- `reports/day25_error_taxonomy_report.md`: human-readable Day25 taxonomy and fix-priority report.
- `reports/day25_error_taxonomy_samples.json`: machine-readable Day25 sample-level root cause tags.
- `reports/day25_error_taxonomy_summary.csv`: Day25 root cause summary table.
- `reports/day25_fix_priority_ranking.csv`: Day25 fix priority ranking.
- `reports/day25_1_error_taxonomy_calibrated_report.md`: calibrated Day25.1 report with evidence strength scoring.
- `reports/day25_1_error_taxonomy_samples.json`: machine-readable calibrated sample-level output.
- `reports/day25_1_error_taxonomy_summary.csv`: calibrated weak / medium / strong root cause summary.
- `reports/day25_1_fix_priority_ranking.csv`: calibrated fix priority ranking.

## How to Run

Use Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run the original CLI detector:

```powershell
python main.py --image data/test_images/example.jpg
```

Regenerate Day25.1 calibrated taxonomy outputs:

```powershell
python tools/day25_error_taxonomy.py --calibrated
```

## Run Tests

```powershell
$env:PYTHONPATH='.'; pytest -q
```

## Roadmap

- Day26: Metadata Handling Policy Patch v1 + No-EXIF JPEG FP Guard
- Day27-Day30: Product-level website and report export
- Day31-Day35: Public dataset manager + Benchmark v3 + open-source detector integration
- Day36-Day40: self-trained baseline + model adapter + ensemble v1
- Day41-Day50: calibration, robustness benchmark, product demo, competition-ready version

## Notes

- Current project status: prototype / pre-product stage.
- Detection results are risk hints, not legal final judgments.
- Large public datasets, model weights, private user uploads, secrets, and local environment files should not be committed to GitHub.
- Day25 / Day25.1 reports are intentionally committed as milestone evidence and dashboard/API data sources.

## Historical Development Notes

## Day 3 Batch Detection

Place real images under:

```text
data/test_images/real
```

Place AI-generated images under:

```text
data/test_images/ai
```

Run batch detection:

```bash
python scripts/run_batch_test.py
```

Batch results are written to:

```text
data/outputs/results.csv
```

Run evaluation:

```bash
python scripts/evaluate_results.py
```

Evaluation summary is written to:

```text
data/outputs/summary.json
```

### Day 3 Smoke Test Result

Day 3 batch detection and evaluation have run successfully. The pipeline now generates:

- `data/outputs/results.csv`
- `data/outputs/summary.json`

Current 8-image smoke test result:

- Total images: 8
- Successful detections: 8
- Errors: 0
- Accuracy: 0.5
- AI recall: 0.0
- Balanced accuracy: 0.5

Current baseline behavior:

- The baseline predicted all 8 smoke test images as `real`.
- This means the engineering loop is working, but the detector is heavily biased toward `real`.
- The current result should not be treated as a reliable AI-image detection result.

Day 4 should focus on improving the detector or introducing a stronger baseline.

## Day 4 Standard Evaluation

Day 4 adds a fixed evaluation pipeline for the labeled test set under
`data/test_images/real` and `data/test_images/ai`. It records each image score,
predicted label, confidence, and a compact raw detector summary for later
analysis.

Run from the project root:

```bash
python tools/evaluate_testset.py --dataset data/test_images --output reports/day4_eval
```

Day 4 outputs:

```text
reports/day4_eval/predictions.csv
reports/day4_eval/summary.json
reports/day4_eval/threshold_scan.csv
reports/day4_eval/report.md
reports/day4_eval/image_reports/
```

`predictions.csv` is the main calibration input for later days because it
contains a continuous `score` field as well as `true_label` and
`predicted_label`.

## Day 5 Explainable Feature Extraction

Day 5 adds a separate explainable feature extraction and rule-scoring system.
It is not the final detector and it is not an absolute real-vs-AI judgment.
It is intended to help inspect image-level signals, compare samples, and
understand why a rule-based risk score moved up or down.

Run from the project root:

```bash
python -m src.day5 --input data/test_images --output reports/day5
```

Day 5 scans recursively and supports `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`,
`.tif`, and `.tiff` files with case-insensitive suffix matching. Unsupported
files are skipped. Corrupted supported images are recorded as errors in the
reports instead of stopping the run.

Day 5 outputs:

```text
reports/day5/feature_report.jsonl
reports/day5/feature_summary.csv
reports/day5/explainable_report.md
reports/day5/day5_metrics.json
reports/day5/calibration_analysis.md
```

Output file meanings:

- `feature_report.jsonl`: detailed per-image features, risk score, prediction, confidence, and reasons.
- `feature_summary.csv`: flat table for spreadsheet review and calibration work.
- `explainable_report.md`: human-readable run summary, scan details, image results, and feature guide.
- `day5_metrics.json`: aggregate counts, average risk score, output paths, and scan metadata.
- `calibration_analysis.md`: label-group calibration notes derived from `feature_summary.csv`, including AI/Real averages, weak signals, false positives, and next-step tuning suggestions.

Day 5 feature groups:

- Basic info: file name, format, width, height, aspect ratio, and file size.
- Metadata: EXIF presence, camera model, software field, and timestamp fields.
- Sharpness: Laplacian-style variance for local detail and clarity.
- Edges: edge density from neighboring pixel transitions.
- Color: RGB means, RGB standard deviations, and color entropy.
- Noise/texture: local variance after light smoothing.
- Compression: JPEG quantization estimate when available, otherwise an 8x8 blockiness fallback.

Current Day 5 calibration notes:

- `risk_score` ranges from `0` to `100`, but the current test set is small.
- `likely_real`, `uncertain`, and `likely_ai` are rule-based review labels, not truth labels.
- A high or low `risk_score` should be read as supporting analysis only.
- Current results are useful for debugging and calibration, but cannot be used as absolute proof that an image is real or AI-generated.
- Do not force fewer `uncertain` results without more calibration data; uncertainty is expected while this remains a small heuristic baseline.

## Day 6 Threshold Calibration and Error Analysis

Day 6 keeps the detector unchanged and analyzes existing Day4 and Day5 outputs.
It scans thresholds from `0.10` to `0.90` in `0.05` steps, computes standard
classification metrics, selects a recommended threshold by F1-score with a
balanced FP/FN tie-break, and exports misclassified and borderline samples for
manual review.

Run from the project root:

```bash
python scripts/day6_threshold_analysis.py
```

Optional explicit paths:

```bash
python scripts/day6_threshold_analysis.py --input reports/day4_eval/predictions.csv --explanations reports/day5/feature_report.jsonl --out outputs/day6
```

Day 6 outputs:

```text
outputs/day6/threshold_calibration.csv
outputs/day6/error_cases.csv
outputs/day6/borderline_cases.csv
outputs/day6/day6_summary.md
outputs/day6/threshold_curve.png
```

Output file meanings:

- `threshold_calibration.csv`: threshold, accuracy, precision, recall, F1, TP, TN, FP, FN, false positive rate, and false negative rate.
- `error_cases.csv`: false positives and false negatives at the recommended threshold, with Day5 explanations when available.
- `borderline_cases.csv`: samples within `0.10` of the recommended threshold.
- `day6_summary.md`: human-readable calibration summary, confusion matrix, system interpretation, and Day7 suggestions.
- `threshold_curve.png`: visual curve for threshold vs accuracy, precision, recall, and F1. The script uses `matplotlib` when available and falls back gracefully if plotting support is missing.

Current Day 6 calibration result:

- Recommended threshold: `0.15`
- Accuracy: `0.6000`
- Precision: `0.5714`
- Recall: `0.8000`
- F1: `0.6667`
- Confusion matrix at threshold `0.15`: TP `8`, TN `4`, FP `6`, FN `2`

This threshold is a calibration result for the current small test set, not a
claim that the detector is production-ready. The score distribution remains low,
so the default `0.50` threshold is too strict for detecting the current AI
samples.

## Day 7 Threshold Calibration and Regression Evaluation

Day 7 adds a stable threshold sweep and regression evaluation workflow. It does
not change the detector, score fusion, Day3 batch test, Day4 evaluation, Day5
explainable analysis, or Day6 reports. The purpose is to make threshold behavior
repeatable and easier to compare before future detector changes.

Run threshold sweep from the project root:

```bash
python scripts/threshold_sweep.py --real-dir data/test_images/real --ai-dir data/test_images/ai --output-dir reports
```

Optional threshold range:

```bash
python scripts/threshold_sweep.py --start 0.10 --end 0.90 --step 0.05
```

Run regression evaluation:

```bash
python scripts/regression_eval.py --real-dir data/test_images/real --ai-dir data/test_images/ai --output-dir reports
```

Day 7 outputs:

```text
reports/day7_threshold_sweep.csv
reports/day7_threshold_sweep.json
reports/day7_threshold_report.md
reports/day7_regression_report.md
reports/day7_image_reports/
```

Output file meanings:

- `day7_threshold_sweep.csv`: per-threshold, per-image predictions plus metrics.
- `day7_threshold_sweep.json`: structured dataset, image scores, threshold metrics, and recommended thresholds.
- `day7_threshold_report.md`: human-readable threshold calibration report with best-F1, high-precision, and high-recall operating points.
- `day7_regression_report.md`: current test-set result compared with the Day6 baseline when available.
- `day7_image_reports/`: per-image JSON and Markdown reports generated by the existing pipeline during Day7 runs.

Current project capability boundary:

- This is an experimental AI image detection system.
- It supports batch testing, explainable analysis, false-positive / false-negative review, threshold calibration, and regression reporting.
- It still needs larger datasets, harder real-world samples, and scenario-specific validation before any production or high-stakes use.
- Day7 thresholds are calibration aids for the current small test set, not universal authenticity rules.

## Day 8 Test Set Normalization and Evaluation

Day 8 normalizes the test-set filenames under `data/test_images/ai` and
`data/test_images/real`, with a target of 30 AI images and 30 real images. It
adds a rename map, a test-set inventory, and a Day8 evaluation using the Day7
recommended threshold. All Day8 outputs are written to:

```text
reports/day8/
```

## Day 9 Error Attribution and Scenario Strategy

Day 9 stops blind global-threshold tuning and analyzes why Day8 mistakes happen.
It reads the existing Day8 prediction CSV plus per-image JSON reports, then
exports attribution tables, feature summaries, and a readable strategy report.
It does not modify `main.py`, `core/score_fusion.py`, feature extraction, or
the Day1-Day8 command behavior.

Run from the project root:

```bash
python scripts/day9_error_analysis.py
```

Day9 outputs:

```text
reports/day9/day9_misclassification_attribution.csv
reports/day9/day9_feature_summary_by_group.csv
reports/day9/day9_analysis.json
reports/day9/day9_report.md
reports/day9/day9_scene_strategy_summary.md
```

Day9 also includes a configurable weight-ablation experiment. The default
runtime fusion weights and experimental feature-weight profiles live in:

```text
configs/detector_weights.json
```

Run the ablation from the project root:

```bash
python scripts/day9_weight_ablation.py
```

Weight-ablation outputs:

```text
reports/day9/day9_weight_ablation.csv
reports/day9/day9_weight_ablation_summary.md
```

Current Day9 focus:

- Attribute false positives and false negatives to dominant feature groups.
- Add weak `scene_tag` labels and scene-level FP/FN/accuracy summaries.
- Compare balanced threshold `0.15` and conservative threshold `0.18`.
- Preserve binary `predicted_label` while adding optional `final_label`, `confidence_level`, and `strategy_reason`.
- Suggest weight optimization directions without changing current weights.
- Propose scenario-specific handling for camera photos, web/social JPEGs, PNG exports, and metadata-stripped images.

## Day 10 Format Bias Audit and Final Labels

Day10 keeps `baseline @ 0.15` as the default regression reference and adds a
format-bias audit, PNG/JPEG controlled test set, format-control evaluation, and
product-facing uncertain decision layer. `balanced_v2_candidate` remains a
diagnostic profile only and is not enabled by default.

Run from the project root:

```bash
python scripts/day10_dataset_format_audit.py
python scripts/day10_create_format_controls.py
python scripts/day10_run_format_eval.py
```

Day10 outputs:

```text
reports/day10_dataset_format_audit.csv
reports/day10_dataset_format_audit.md
reports/day10_format_control_mapping.csv
reports/day10_format_eval_results.csv
reports/day10_format_eval_report.md
reports/day10_summary.md
data/day10_format_control/
```

Current Day10 default output policy:

- `threshold = 0.15`
- `uncertainty_margin = 0.03`
- `score >= 0.18`: `final_label=ai`
- `score <= 0.12`: `final_label=real`
- `0.12 < score < 0.18`: `final_label=uncertain`

The Day10 audit found the current original test set is format-confounded: AI
samples are PNG and Real samples are JPEG. Because of that, original-set
accuracy must not be used alone as a final detector-performance claim.

## Test

```bash
pytest
```

or:

```bash
python -m pytest
```

## Dashboard API

Day21 adds frontend-ready dashboard data endpoints built from Day20 history JSON files in `outputs/api_history/`.

These APIs summarize existing detection results for future dashboard cards, charts, and lists. They do not change detector weights, do not improve model accuracy, do not add a database, and do not connect pretrained models.

Start the API service:

```bash
uvicorn app.main:app --reload
```

### GET /dashboard/summary

Returns summary statistics, recent results, recent batches, chart data, alerts, and optional debug metadata.

Parameters:

- `limit_recent`: integer, default `10`
- `include_debug`: boolean, default `false`

Example:

```bash
curl "http://127.0.0.1:8000/dashboard/summary?limit_recent=10"
```

Main response fields:

- `summary.total_detections`
- `summary.single_detection_count`
- `summary.batch_detection_count`
- `summary.total_images_processed`
- `summary.final_label_distribution`
- `summary.risk_level_distribution`
- `summary.confidence_distribution`
- `summary.decision_quality`
- `recent_results`
- `recent_batches`
- `chart_data`
- `alerts`

### GET /dashboard/recent-results

Returns compact image-level history records for tables or cards. Full `debug_evidence` is intentionally excluded.

Parameters:

- `limit`: integer, default `20`
- `final_label`: optional, one of `ai_generated`, `real`, `uncertain`
- `risk_level`: optional, one of `low`, `medium`, `high`, `unknown`

Examples:

```bash
curl "http://127.0.0.1:8000/dashboard/recent-results?limit=20"
curl "http://127.0.0.1:8000/dashboard/recent-results?final_label=uncertain"
curl "http://127.0.0.1:8000/dashboard/recent-results?risk_level=high"
```

Each result includes:

- `id`
- `timestamp`
- `filename`
- `final_label`
- `risk_level`
- `confidence`
- `user_facing_summary`
- `recommendation`

### GET /dashboard/chart-data

Returns chart-only arrays that can be passed directly to ECharts, Recharts, Chart.js, or similar libraries.

Example:

```bash
curl "http://127.0.0.1:8000/dashboard/chart-data"
```

Chart fields:

- `label_distribution`
- `risk_distribution`
- `confidence_distribution`
- `daily_detection_trend`

See `docs/day21_dashboard_api.md` for full JSON contracts and examples.

## Output Meaning

The final score is a V0.1 baseline heuristic score from `0.0` to `1.0`:

- `0.00-0.35`: low
- `0.35-0.65`: medium
- `0.65-0.85`: high
- `0.85-1.00`: very_high

The risk level is a baseline risk level, not a final authenticity judgment.

The product-facing decision fields are:

- `raw_score`: the baseline AI-risk score used by the decision layer.
- `threshold`: default `0.15`, kept as the baseline regression reference.
- `uncertainty_margin`: default `0.03`.
- `binary_label_at_threshold`: hard threshold label, `ai` or `real`.
- `final_label`: `ai`, `real`, or `uncertain`.
- `decision_status`: `decided` or `uncertain`.
- `confidence_distance`: absolute distance from the threshold.
- `decision_reason`: one of `score_above_threshold_margin`, `score_below_threshold_margin`, or `score_inside_uncertain_band`.

`uncertain` is not an error. It means the score is close enough to the
threshold that the system refuses to force a hard product-facing judgment.

The evidence summary is a heuristic evidence summary. It should be read as engineering context, not as proof.

Missing EXIF is treated only as weak provenance evidence. It does not mean the image is AI-generated.

The V0.1 deep model detector is a placeholder. It returns a neutral placeholder value and is not used as trained evidence in score fusion. A model result may participate in fusion only in a future version where `model_status` is `active`.

## Current Limitations

- No model is trained or loaded.
- No CNN, ViT, DIRE, CLIP, or deep detector is integrated yet.
- Frequency analysis is heuristic and should not be interpreted as proof.
- Basic forensic features can be affected by compression, resizing, screenshots, editing, and platform processing.
- Pillow EXIF reading is limited compared with ExifTool.
- C2PA / Content Credentials parsing is reserved as an optional future interface.
- V0.1 output is a baseline risk report, not a final authenticity verdict.

## Roadmap

- Day 2: Build V0.1 local CLI baseline with multi-evidence fusion
- Day 3: Add stronger fixtures, improve report quality, and refine scoring calibration
- Day 4: Add standard labeled test-set evaluation
- Day 5: Add explainable feature extraction and calibration notes
- Day 6: Add threshold calibration, error-case analysis, borderline review, and threshold curve output
- Day 7: Add threshold sweep, regression evaluation, and stable calibration reports
- Day 8: Normalize test-set filenames, inventory 30 AI / 30 real images, and evaluate with the Day7 threshold
- Day 9: Add misclassification attribution, feature-weight suggestions, and scenario-specific strategy reporting
- Day 10: Audit dataset format bias, create PNG/JPEG controls, add final_label and uncertain output
- Later: Add optional ExifTool and C2PA structured parsing
- Later: Add benchmark datasets and evaluation scripts
- Later: Integrate real model detectors only after the baseline is stable
