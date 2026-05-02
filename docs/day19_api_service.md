# Day19 Minimal FastAPI Service

## What Changed

Day19 adds a minimal HTTP service around the existing detector pipeline. It does not change detector weights, `uncertain_decision_v21`, model behavior, CLI scanning, or report generation.

New service files:

- `app/main.py`
- `app/schemas.py`
- `app/services/detection_service.py`

The detection service calls the existing `run_pipeline()` function, then reuses the Day18 `build_frontend_response()` adapter before returning the compact Day19 `success/data/error` API envelope.

## Start The Service

From the project root:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful URLs:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `POST http://127.0.0.1:8000/api/v1/detect`

## Health Check

Request:

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok",
  "service": "ai-image-trust-scanner",
  "version": "0.1.0"
}
```

## Detect Image

The endpoint accepts `multipart/form-data` with a single file field named `file`.

Supported filename extensions:

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`

Windows CMD example:

```cmd
curl -X POST "http://127.0.0.1:8000/api/v1/detect" ^
  -F "file=@data/test_images/day14_expansion/paired_format/ai_jpg/ai_001_food_retail_jpg_q95.jpg"
```

PowerShell example:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/detect" `
  -Method Post `
  -Form @{ file = Get-Item "data/test_images/day14_expansion/paired_format/ai_jpg/ai_001_food_retail_jpg_q95.jpg" }
```

Standard-library smoke test:

```bash
python scripts/test_api_detect.py
```

## Success Response Shape

```json
{
  "success": true,
  "data": {
    "filename": "example.jpg",
    "final_label": "ai",
    "risk_level": "high",
    "confidence": 0.84,
    "decision_reason": [
      {
        "code": "stable_ai_high_confidence_v21",
        "message": "Stable AI-like score pattern across resolution checks.",
        "severity": "critical"
      }
    ],
    "recommendation": {
      "action": "warn",
      "message": "Treat this image as high risk and request stronger provenance before use."
    },
    "user_facing_summary": "Frontend-safe product summary text.",
    "technical_explanation": {
      "score": 0.191,
      "threshold_used": 0.15,
      "decision_layer": "day17_product_output_schema",
      "main_signals": ["stable_ai_high_confidence_v21"]
    },
    "debug_evidence": {
      "enabled": true,
      "raw_score": 0.191,
      "feature_summary": {},
      "consistency_checks": {},
      "format_evidence": {},
      "resolution_evidence": {}
    }
  },
  "error": null
}
```

`final_label` is normalized for this HTTP endpoint to `ai`, `real`, or `uncertain`. Internally, the service still uses the Day18 frontend adapter values before this final mapping.

## Error Response Shape

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "Unsupported file type. Supported formats: jpg, jpeg, png, webp."
  }
}
```

Supported Day19 error codes:

- `INVALID_FILE_TYPE`
- `DETECTION_FAILED`
- `EMPTY_FILE`
- `INTERNAL_ERROR`

Tracebacks are not exposed in API responses.

## Current Limits

- This is a minimal service layer, not a dashboard.
- It performs one-image detection per request.
- Uploaded files are saved temporarily and removed after processing.
- The existing detector still writes internal reports under `.tmp/api_reports`.
- The deep model detector remains a placeholder and is not connected to pretrained weights.

## Suggested Day20 Work

- Add optional response mode for returning the full Day18 nested contract directly.
- Add CORS only when a frontend origin exists.
- Add batch scan endpoint design.
- Add API-level tests once FastAPI test dependencies are pinned.
- Add frontend/dashboard integration using the stable Day19 envelope.
