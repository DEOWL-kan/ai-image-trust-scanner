# AI Image Trust Scanner

## Overview

AI Image Trust Scanner is a local CLI prototype for analyzing image provenance and AI-generation risk signals. It inspects image files, metadata, C2PA / Content Credentials claims, and basic forensic properties, then writes a JSON report with multi-dimensional risk scores.

This project does not claim to determine with 100% certainty whether an image is real or AI-generated. The current output is a risk-oriented signal summary, not a final authenticity verdict or an AI-generation probability.

## Current Status

Day 1 Beta CLI prototype.

The current version is focused on local command-line inspection only. It does not include a web frontend, database, model training, or deep learning model integration.

## Features

- Image file inspection
- EXIF / XMP metadata analysis through ExifTool
- C2PA / Content Credentials claim check
- Basic forensic image inspection
- Rule-based multi-dimensional risk fusion
- JSON report output

## Architecture

```text
Image input
-> Metadata detector
-> C2PA detector
-> Forensic detector
-> Score fusion
-> JSON report
```

## Installation

Requirements:

- Python 3.10+
- ExifTool installed and available in PATH
- `c2pa` or `c2patool` installed and available in PATH, optional but recommended

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python backend/detect_image.py backend/samples/example.jpg
```

The report is written to:

```text
backend/outputs/example_report.json
```

## Output Example

```json
{
  "ok": true,
  "image_path": "backend/samples/example.jpg",
  "metadata": {
    "checked": true,
    "has_exif": false,
    "risk_score": 45
  },
  "c2pa": {
    "checked": true,
    "has_manifest": false,
    "valid_signature": null,
    "risk_score": 40
  },
  "forensic": {
    "checked": true,
    "format": "JPEG",
    "width": 1279,
    "height": 1706,
    "risk_score": 30
  },
  "fusion": {
    "risk": {
      "ai_generation_risk": 30,
      "provenance_risk": 75,
      "editing_risk": 15,
      "technical_quality_risk": 20,
      "overall_risk": 38,
      "risk_level": "medium"
    },
    "conclusion": "No strong AI-generation evidence detected, but provenance is limited."
  }
}
```

## Important Notes

- No EXIF does not mean AI-generated.
- No C2PA claim does not mean fake.
- The current version is not a final AI detector.
- The Day 1 scores are multi-dimensional risk indicators, not AI-generation probabilities.
- Provenance risk means the source is hard to verify; it does not prove AI generation.
- The result is a risk-oriented analysis, not legal or forensic proof.

## Project Roadmap

- Day 1: CLI pipeline
- Day 2-3: Improve metadata and C2PA parsing
- Day 4-7: FastAPI backend
- Week 2: Web interface
- Week 3: AI model integration
- Week 4: Benchmark and public beta

## Privacy

- Sample images are ignored by git by default.
- Output reports are ignored by git by default.
- The tool is designed to support local-first analysis.

## License

MIT License, if LICENSE file is added.
