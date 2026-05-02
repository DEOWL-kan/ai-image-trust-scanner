# Day20 Batch Detection API + Result History JSON Export

## 1. Day20 Goal

Day20 adds batch detection and API history persistence on top of the existing Day19 FastAPI service.

The work keeps the Day17 product output fields stable, keeps the Day18 API adapter in the detection path, and keeps the Day19 single-image endpoint available.

Day20 does not change detector weights, does not connect pretrained models, does not add frontend UI, and does not force `uncertain` into a hard binary class.

## 2. New API List

- `POST /detect/batch`
- `POST /api/v1/detect/batch`
- `GET /history`
- `GET /api/v1/history`
- `GET /history/{filename}`
- `GET /api/v1/history/{filename}`

The existing endpoint remains:

- `POST /api/v1/detect`

## 3. Batch Detection Request And Response

JSON path-based request:

```json
{
  "image_paths": [
    "data/test_images/day14_expansion/paired_format/ai_jpg/ai_001_food_retail_jpg_q95.jpg",
    "data/test_images/day14_expansion/paired_format/ai_jpg/ai_002_food_retail_jpg_q95.jpg",
    "data/test_images/day14_expansion/paired_format/ai_jpg/ai_003_food_retail_jpg_q95.jpg"
  ],
  "save_history": true
}
```

Response shape:

```json
{
  "api_version": "v1",
  "mode": "batch",
  "batch_id": "batch_20260502_223000_abcd12",
  "created_at": "2026-05-02T22:30:00+08:00",
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "results": [
    {
      "input": {
        "filename": "ai_001_food_retail_jpg_q95.jpg",
        "source": "data/test_images/day14_expansion/paired_format/ai_jpg/ai_001_food_retail_jpg_q95.jpg",
        "index": 0
      },
      "status": "success",
      "result": {
        "filename": "ai_001_food_retail_jpg_q95.jpg",
        "final_label": "ai",
        "risk_level": "high",
        "confidence": 0.84,
        "decision_reason": [],
        "recommendation": {},
        "user_facing_summary": "",
        "technical_explanation": {},
        "debug_evidence": {}
      }
    }
  ],
  "errors": [],
  "history": {
    "saved": true,
    "filename": "batch_20260502_223000_abcd12.json",
    "path": "outputs/api_history/batch_20260502_223000_abcd12.json"
  }
}
```

The endpoint also accepts multipart form data with repeated `file` or `files` fields. For the current project, JSON `image_paths` is the simplest repeatable test path.

## 4. History JSON Save Path

History files are written to:

```text
outputs/api_history/
```

Single detection filenames:

```text
single_YYYYMMDD_HHMMSS_xxxxxx.json
```

Batch detection filenames:

```text
batch_YYYYMMDD_HHMMSS_xxxxxx.json
```

Each file is UTF-8 JSON with `indent=2` and `ensure_ascii=False`.

History file shape:

```json
{
  "history_type": "batch",
  "api_version": "v1",
  "created_at": "2026-05-02T22:30:00+08:00",
  "request": {
    "mode": "batch",
    "input_count": 3,
    "inputs": []
  },
  "response": {},
  "runtime": {
    "duration_ms": 1234.56,
    "service": "fastapi"
  }
}
```

History saving defaults to enabled. Use `save_history=false` as a query parameter or request field to disable it.

## 5. History Query Usage

List recent history summaries:

```bash
curl "http://127.0.0.1:8000/history?limit=20&history_type=all"
```

Supported `history_type` values:

- `single`
- `batch`
- `all`

Read one history file:

```bash
curl "http://127.0.0.1:8000/history/batch_20260502_223000_abcd12.json"
```

The detail endpoint only reads JSON filenames directly inside `outputs/api_history`. Path traversal attempts such as `../requirements.txt` are rejected.

## 6. Error Isolation

Batch detection wraps each image independently.

If one image path is missing, empty, unsupported, or fails inside the detector, that item becomes:

```json
{
  "input": {
    "filename": "missing.jpg",
    "source": "data/test_images/missing.jpg",
    "index": 2
  },
  "status": "failed",
  "error": {
    "type": "FileNotFoundError",
    "message": "Image file not found: data/test_images/missing.jpg",
    "recoverable": true
  }
}
```

The batch response still returns `200` with correct `total`, `succeeded`, and `failed` counts. Python tracebacks are not exposed in user-facing API payloads.

## 7. Why Batch Does Not Modify The Core Detector

The batch layer is orchestration only. It prepares inputs, preserves order, calls the existing single-image API detection service, catches per-item errors, and aggregates metadata.

The actual image analysis still lives in the existing pipeline and adapter path:

```text
run_pipeline() -> build_frontend_response() -> detect_image_for_api()
```

This preserves the Day17, Day18, and Day19 contracts while adding a product-facing batch surface.

## 8. Current Limits

- Batch detection currently runs sequentially.
- JSON path input is the primary tested path.
- Multipart batch upload is supported, but large file limits and async job queues are not implemented yet.
- History listing reads compact metadata from recent JSON files; it is not a database.
- No dashboard aggregation API exists yet.

## 9. Day21 Suggestion

Day21: Frontend-ready Dashboard Data API + Summary Statistics

Day21 goal: use Day20 history JSON to add statistics endpoints for:

- Total detection count
- AI / Real / Uncertain counts
- `risk_level` distribution
- `confidence` distribution
- Recent detection records
- Batch success rate
- False-positive / uncertain case review data

This prepares clean backend data for a later frontend dashboard.
