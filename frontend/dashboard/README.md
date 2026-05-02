# Dashboard Frontend v1

Minimal native HTML/CSS/JS dashboard for the Day21 dashboard APIs.

## Files

```text
frontend/dashboard/
  index.html
  styles.css
  app.js
  README.md
```

## Run

Start the FastAPI service from the project root:

```bash
uvicorn app.main:app --reload
```

If port `8000` is already occupied, use:

```bash
uvicorn app.main:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8000/dashboard-ui
```

When using the alternate port:

```text
http://127.0.0.1:8001/dashboard-ui
```

## APIs Used

- `GET /dashboard/summary`
- `GET /dashboard/recent-results?limit=20`
- `GET /dashboard/chart-data`

## Notes

- No frontend framework is required.
- Charts are rendered with lightweight CSS bars.
- Empty API data and failed API requests have separate UI states.
- Single upload uses `POST /api/v1/detect` with FormData field `file`.
- Batch upload uses `POST /detect/batch` first, then falls back to `POST /api/v1/detect/batch`, with FormData field `files`.
- The frontend does not change detector algorithms or API response schemas.
