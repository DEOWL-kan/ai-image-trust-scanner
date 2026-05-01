# AI Image Trust Scanner

AI Image Trust Scanner is a local Python command-line project for baseline AI image risk analysis.

The project combines multiple weak signals instead of making a single absolute claim. V0.1 inspects image properties, basic EXIF metadata, simple forensic features, simple frequency-domain features, and a placeholder model interface, then writes JSON and Markdown reports.

V0.1 does not prove whether an image is real or AI-generated. It is a baseline engineering prototype, not a final detector, not a trained model, and not a legal forensic conclusion.

## Current Version

V0.1 baseline CLI.

The project remains a Python command-line tool. It does not include Flask, FastAPI, a web frontend, GUI, database, model training, or downloaded model weights.

## Features

- Read local JPG, JPEG, PNG, and WEBP files
- Report file name, format, resolution, color mode, and file size
- Read basic EXIF fields with Pillow
- Preserve the distinction between missing EXIF and AI evidence
- Compute baseline forensic features with OpenCV and numpy
- Compute a basic FFT high-frequency energy ratio
- Provide a placeholder deep model detector interface
- Fuse metadata, forensic, and frequency heuristics into a baseline risk level
- Exclude placeholder model probability from score fusion until a future model reports `model_status: active`
- Generate JSON and Markdown reports in `outputs/reports/`
- Run labeled test-set evaluation with threshold scanning
- Generate explainable feature reports for image-level review
- Analyze threshold calibration, error cases, and borderline samples in Day6 reports

## Project Structure

```text
ai-image-trust-scanner/
|-- main.py
|-- requirements.txt
|-- README.md
|-- core/
|   |-- image_loader.py
|   |-- metadata_analyzer.py
|   |-- forensic_analyzer.py
|   |-- frequency_analyzer.py
|   |-- model_detector.py
|   |-- score_fusion.py
|   `-- report_generator.py
|-- data/
|   |-- samples_real/
|   |-- samples_ai/
|   `-- test_images/
|-- outputs/
|   |-- reports/
|   `-- day6/
|-- reports/
|   |-- day4_eval/
|   `-- day5/
|-- scripts/
|   |-- run_batch_test.py
|   |-- evaluate_results.py
|   `-- day6_threshold_analysis.py
|-- tools/
|   `-- evaluate_testset.py
|-- src/
|   |-- day5.py
|   |-- day5_reports.py
|   |-- explainable.py
|   `-- features.py
|-- tests/
|   `-- test_pipeline.py
|-- docs/
|   |-- day1_acceptance.md
|   `-- day2_plan.md
`-- backend/
    `-- Day 1 historical CLI implementation
```

## Installation

Use Python 3.10+.

```bash
pip install -r requirements.txt
```

## Run

Place an image under `data/test_images/`, then run:

```bash
python main.py --image data/test_images/example.jpg
```

Reports are written to:

```text
outputs/reports/
```

You can also choose another output directory:

```bash
python main.py --image data/test_images/example.jpg --output-dir outputs/reports
```

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

## Test

```bash
pytest
```

or:

```bash
python -m pytest
```

## Output Meaning

The final score is a V0.1 baseline heuristic score from `0.0` to `1.0`:

- `0.00-0.35`: low
- `0.35-0.65`: medium
- `0.65-0.85`: high
- `0.85-1.00`: very_high

The risk level is a baseline risk level, not a final authenticity judgment.

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
- Later: Add optional ExifTool and C2PA structured parsing
- Later: Add benchmark datasets and evaluation scripts
- Later: Integrate real model detectors only after the baseline is stable
