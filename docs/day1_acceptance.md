# Day 1 Acceptance Report

## 1. Day 1 Goal

Day 1 validates the local Python CLI prototype for AI Image Trust Scanner. The scope is intentionally limited to local image inspection, metadata extraction, C2PA / Content Credentials checking, basic forensic inspection, score fusion, and JSON report generation.

Out of scope for Day 1: frontend, database, model training, deep learning model integration, hosted services, and accuracy claims.

## 2. Completed Modules

- `backend/detect_image.py`: CLI entry point, input validation, detector orchestration, JSON report writing, and top-level exception handling.
- `backend/detectors/metadata_detector.py`: ExifTool-based metadata extraction, camera EXIF detection, AI tool keyword detection, editing software keyword detection, and metadata risk scoring.
- `backend/detectors/c2pa_detector.py`: C2PA / Content Credentials command integration through `c2patool` or `c2pa`, including explicit handling for `No claim found`.
- `backend/detectors/forensic_detector.py`: Pillow-based image open, format, dimensions, color mode, file size, JPEG detection, and basic file-size-to-resolution heuristic.
- `backend/detectors/score_fusion.py`: Multi-dimensional risk fusion and evidence summary output.

## 3. Acceptance Commands

Run the following from the project root after installing requirements and making ExifTool and c2patool available in PATH:

```bash
python backend/detect_image.py backend/samples/real_phone.jpg
python backend/detect_image.py backend/samples/ai_image2.png
python backend/detect_image.py backend/samples/web_real.jpg
python backend/detect_image.py backend/samples/not_exist.jpg
```

Expected report files:

```text
backend/outputs/real_phone_report.json
backend/outputs/ai_image2_report.json
backend/outputs/web_real_report.json
backend/outputs/not_exist_report.json
```

## 4. Expected Results for the Three Test Images

`real_phone.jpg`:

- The CLI should complete without crashing and write `real_phone_report.json`.
- Pillow should inspect it as a valid JPEG image.
- If ExifTool does not find camera EXIF, `metadata.has_exif=false` is acceptable.
- If C2PA reports `No claim found`, `c2pa.checked=true`, `c2pa.has_manifest=false`, and `c2pa.error=null`.
- The final `fusion.risk.ai_generation_risk` should remain low to moderate unless strong AI metadata is present; missing EXIF and missing C2PA should mainly affect `provenance_risk`.

`ai_image2.png`:

- The CLI should complete without crashing and write `ai_image2_report.json`.
- Pillow should inspect it as a valid PNG image.
- Metadata should be checked through ExifTool.
- If metadata contains AI-related tool strings such as `OpenAI`, the metadata detector should report an AI keyword signal.
- If C2PA returns manifest-like data with no validation failure, the C2PA detector should report a valid manifest signal.
- The final `fusion.risk.ai_generation_risk` should be high when strong AI metadata is present.

`web_real.jpg`:

- The CLI should complete without crashing and write `web_real_report.json`.
- Pillow should inspect it as a valid JPEG image.
- Missing camera EXIF or missing C2PA claims should be treated as limited provenance, not proof of AI generation.
- The final `fusion.risk.provenance_risk` may be elevated while `fusion.risk.ai_generation_risk` remains low to moderate.

## 5. Meaning of `has_exif=false`

`has_exif=false` means the metadata detector did not find camera provenance fields such as camera make, camera model, lens model, exposure time, aperture, ISO, or creation date.

This does not mean the image is AI-generated. It only means the image source cannot be verified from camera EXIF metadata alone. Many real images lose EXIF data after editing, uploading, messaging, screenshotting, or web compression.

## 6. Meaning of `No claim found`

`No claim found` is a normal C2PA result for an image that does not contain a C2PA claim or manifest. It is not a system failure.

The expected interpretation is:

```json
{
  "checked": true,
  "has_manifest": false,
  "valid_signature": null,
  "risk_score": 40,
  "signals": ["No C2PA manifest or claim found. Provenance cannot be verified."],
  "error": null
}
```

No C2PA claim does not mean the image is fake. It only means the image lacks verifiable Content Credentials.

## 7. Current Limitations

- Risk scoring is rule-based and intended for engineering integration only.
- Day 1 scores are not AI-generation probabilities.
- `ai_generation_risk`, `provenance_risk`, `editing_risk`, and `technical_quality_risk` measure different concerns and should not be collapsed into a claim that an image is fake.
- The CLI does not perform deep image forensics such as Error Level Analysis, compression grid analysis, or sensor noise modeling.
- The CLI does not train or run an AI detection model.
- C2PA parsing currently relies on command output keywords rather than a full structured manifest parser.
- Metadata keyword matching is useful for obvious provenance signals but can miss renamed, stripped, or manipulated metadata.
- `overall_risk` is a weighted engineering summary. It should not be presented as a detection accuracy percentage.

## 8. Day 2 Next Steps

- Normalize ExifTool field extraction across EXIF, XMP, IPTC, PNG text, and maker-specific namespaces.
- Improve C2PA parsing by requesting JSON output when supported and preserving structured manifest fields.
- Add small unit tests for metadata, C2PA, forensic, and score fusion edge cases.
- Add fixture-based tests for no EXIF, AI metadata keyword, no C2PA claim, valid C2PA claim, invalid image, and missing input.
- Add a CLI summary printout while keeping the JSON report as the source of truth.
