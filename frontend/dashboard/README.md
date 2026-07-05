# Dashboard Frontend

Minimal native HTML/CSS/JS dashboard for the local FastAPI app.

## Design Direction

The open-source dashboard is a local workbench, not a marketing page:

- one stylesheet: `styles.css`
- no external fonts, hero page, decorative particles, or motion layer
- first screen shows scan controls and a demo evidence-chain result
- real upload, batch scan, policy selection, report center, and JSON/detail views
  remain wired to the backend
- default copy is honest about CPU-safe `stub` mode and optional HF models

## Files

```text
frontend/dashboard/
  index.html
  errors.html
  styles.css
  app.js
  api-client.js
  detection-detail-drawer.js
  error-gallery.js
  README.md
```

## Run

Start the local service from the project root:

```bash
python scripts/run_local_dashboard.py
```

Open the URL printed by the launcher, usually:

```text
http://127.0.0.1:8000/dashboard-ui/index.html
```

If you run the static files separately, pass the backend URL:

```text
http://127.0.0.1:5500/index.html?apiBase=http://127.0.0.1:8000
```

## APIs Used

- `GET /api/health`
- `GET /api/model-status`
- `GET /api/v1/policy/profiles`
- `POST /api/detect/single?policy_profile=strict_safe_plus`
- `POST /api/v1/detect/batch/jobs`
- `GET /api/v1/detect/batch/jobs/{job_id}`
- `GET /api/v1/detect/batch/jobs/{job_id}/result`
- `GET /dashboard/summary`
- `GET /dashboard/chart-data`
- `GET /api/v1/reports?limit=100`
- `GET /api/v1/reports/queue?limit=20`
- `PATCH /api/v1/reports/{report_id}/review`
- `GET /api/v1/reports/export`
- `GET /api/v1/reports/review-calibration`
- `GET /api/v1/reports/policy-replay`
- `GET /api/v1/reports/scenario-stress-pack`
- `GET /api/v1/reports/training-readiness`
- `POST /api/v1/reports/training-readiness/rebuild`
- `GET /api/v1/reports/training-label-queue`

## Notes

- The demo result in the first screen is front-end fixture data only and is
  labeled `Demo data, not your scan`.
- The dashboard does not change detector algorithms or API response schemas.
- Empty API data and failed API requests have explicit UI states.
