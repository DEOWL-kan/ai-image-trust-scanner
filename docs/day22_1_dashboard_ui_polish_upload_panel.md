# Day22.1 Dashboard UI Polish + Upload Detection Panel v0

## What Day22.1 Added

Day22.1 upgrades the dashboard from a basic data view into a compact product-console style UI and adds upload-based detection actions on top of the existing API.

No detection algorithm, score weight, pretrained model, or dashboard API response schema was changed.

## Updated Page Modules

- Top header with service status and Refresh action.
- Main Image Detection action panel.
- Single image upload and detection flow.
- Batch image upload and detection flow.
- Detection result preview area.
- Compact summary cards.
- Polished distribution chart cards.
- Recent results table with tighter badges, filename truncation, confidence formatting, and two-line summaries.

## Single Upload API

The frontend calls:

```text
POST /api/v1/detect
```

Request format:

```text
multipart/form-data
file=<selected image>
```

The backend parameter is `file: UploadFile = File(...)`.

## Batch Upload API

The frontend first calls:

```text
POST /detect/batch
```

If that route is unavailable, it falls back to:

```text
POST /api/v1/detect/batch
```

Request format:

```text
multipart/form-data
files=<image 1>
files=<image 2>
...
```

The backend accepts both `files` and `file` form fields and merges their values.

## Frontend Access

Start the API server from the project root:

```bash
uvicorn app.main:app --reload
```

If port `8000` is already occupied:

```bash
uvicorn app.main:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8000/dashboard-ui
```

or with the alternate port:

```text
http://127.0.0.1:8001/dashboard-ui
```

## Current Limits

- Upload is intentionally minimal and uses the existing synchronous API.
- There is no drag-and-drop upload yet.
- There is no client-side image preview yet.
- Batch upload displays a compact summary and result list, not a detailed per-image report drawer.
- Failed upload states are displayed in the panel but are not persisted by the frontend.

## Next Steps

- Add drag-and-drop support.
- Add a recent-result detail drawer.
- Add filters for label and risk level.
- Add a small daily trend chart.
- Add browser smoke tests for upload and refresh flows.
