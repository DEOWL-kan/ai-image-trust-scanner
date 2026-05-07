# Day30 MVP Release Notes

## Project Position

AI Image Trust Scanner is currently an AI image trust detection MVP. Day30 closes the local product loop around rules, feature signals, reports, review status, and demo readiness.

Current boundaries:

- No pretrained model is connected.
- No model is trained in this MVP closure.
- Reports are HTML and structured export only; PDF is not part of Day30.
- No login, registration, or user permission system is included.

## Local Startup

Install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start backend:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard-ui/index.html
```

The dashboard is a static frontend served by FastAPI. There is no separate frontend build step for the current MVP.

## MVP Demo Path

1. Open the dashboard and use the Trust Console.
2. Upload one JPG, JPEG, PNG, or WEBP image.
3. Run single image detection.
4. Confirm the result card shows a generated `report_id`.
5. Open the detail drawer from the result card or Report Center.
6. Open the HTML report.
7. Go to Report Center.
8. Search, filter, sort, and inspect the risk review queue.
9. Change `review_status` in the detail drawer.
10. Refresh the page and confirm the review status remains saved.
11. Restart the backend and confirm the report remains in Report Center.
12. Export Report Center records as JSON or CSV.

## Data Persistence

Reports are persisted in SQLite:

```text
data/app/reports.sqlite3
```

Generated HTML reports are stored under:

```text
outputs/html_reports/
```

Do not manually delete the local SQLite file during demos unless you intentionally want to reset stored report data.

The frontend and public API responses avoid exposing local absolute storage paths.

## API Summary

- `GET /health`: legacy lightweight service health.
- `GET /api/health`: Day30 runtime status, reports API status, SQLite status, report count, versions, and feature flags.
- `POST /api/v1/detect`: single image detection.
- `GET /api/v1/reports`: report list with search, filters, sorting, limit, and offset.
- `GET /api/v1/reports/{report_id}`: report detail.
- `PATCH /api/v1/reports/{report_id}/review`: save review status and review note.
- `GET /api/v1/reports/{report_id}/html`: HTML report.
- `GET /api/v1/reports/export?format=json`: JSON export.
- `GET /api/v1/reports/export?format=csv`: CSV export.

## Version Fields

Each persisted report includes:

- `report_schema_version`
- `detector_version`
- `model_version`

Current MVP values are exposed through `GET /api/health`.

## Smoke Test

With the backend already running:

```powershell
python scripts\day30_smoke_test.py
```

Optional custom base URL:

```powershell
$env:BASE_URL="http://127.0.0.1:8000"
python scripts\day30_smoke_test.py
```

The script verifies:

`health -> detect -> report_id -> reports list -> detail -> review PATCH -> HTML report -> export`

## Day31 Direction

After Day30, stop adding frontend breadth for the MVP. Recommended next phase:

- Dataset enhancement.
- Metric and evaluation enhancement.
- Pretrained model evaluation.
- Lightweight or open source model integration.
- Keep the product loop stable while improving detection quality.
