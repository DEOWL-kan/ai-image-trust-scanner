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
|   `-- reports/
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
- Later: Add optional ExifTool and C2PA structured parsing
- Later: Add benchmark datasets and evaluation scripts
- Later: Integrate real model detectors only after the baseline is stable
