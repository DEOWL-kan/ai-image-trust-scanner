# Day22 Web Dashboard Frontend v1

## What Day22 Added

Day22 adds a minimal web dashboard frontend for the Day21 dashboard APIs. It is a lightweight native HTML/CSS/JS interface that displays summary statistics, compact distribution charts, and recent detection results.

This stage does not modify detection algorithms, score fusion, model behavior, or the dashboard API response schemas.

## New File Structure

```text
frontend/
  dashboard/
    index.html
    styles.css
    app.js
    README.md

docs/
  day22_web_dashboard_frontend_v1.md
```

`app/main.py` also has a small FastAPI static mount for the dashboard UI.

## Frontend Access

Start the API server from the project root:

```bash
uvicorn app.main:app --reload
```

If port `8000` is already occupied, use:

```bash
uvicorn app.main:app --reload --port 8001
```

Then open:

```text
http://127.0.0.1:8000/dashboard-ui
```

When using the alternate port:

```text
http://127.0.0.1:8001/dashboard-ui
```

The static UI is mounted at `/dashboard-ui` to avoid conflicts with the existing `/dashboard/*` API endpoints.

## APIs Called

- `GET /dashboard/summary`
- `GET /dashboard/recent-results?limit=20`
- `GET /dashboard/chart-data`

## v1 Features

- Header with product name, subtitle, service status, and Refresh button.
- Service status is based on `GET /dashboard/summary`.
- Six summary cards:
  - Total Scans
  - AI Detected
  - Real Detected
  - Uncertain
  - High Risk
  - Average Confidence
- Lightweight CSS bar charts:
  - Label Distribution
  - Risk Distribution
  - Confidence Distribution
- Recent results table with timestamp, filename, label, risk, confidence, and summary.
- Badge styling for labels and risk levels.
- Empty states for no chart data and no recent detection results.
- Error states for chart and recent-result API failures.
- Responsive layout for desktop and mobile.

## Current Limits

- The frontend is a single dashboard page only.
- Charts are simple CSS bar charts, not a full charting library.
- There is no upload UI in this stage.
- There is no authentication, user management, filtering UI, or admin system.
- The UI reads existing API fields defensively and falls back to `0`, `--`, or empty states if fields are missing.

## Day23 Extension Ideas

- Add a small upload panel that calls `POST /api/v1/detect`.
- Add filters for recent results by `final_label` and `risk_level`.
- Add daily trend visualization from `daily_detection_trend`.
- Add a details drawer for one recent result.
- Add visual regression or browser smoke tests for the dashboard page.
