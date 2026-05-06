# Day21 Frontend-ready Dashboard Data API

## Day29 Update: Persistent Reports API

Day29 keeps the dashboard summary endpoints compatible, but Report Center now reads persistent records from SQLite instead of relying on temporary/mock frontend data. The store is initialized automatically at startup and lives at:

```text
data/app/reports.sqlite3
```

Legacy Day20 history JSON files under `outputs/api_history/` are preserved. If SQLite is empty, the lightweight bootstrap imports compatible legacy history records without deleting the JSON files. A repeatable manual migration script is also available:

```powershell
python scripts\migrate_reports_to_sqlite.py
```

Reports endpoints:

- `GET /api/v1/reports`
- `GET /api/v1/reports/{report_id}`
- `PATCH /api/v1/reports/{report_id}/review`
- `GET /api/v1/reports/{report_id}/html`
- `GET /api/v1/reports/export`

`GET /api/v1/reports` supports `q`, `risk_level`, `final_label`, `review_status`, `source_type`, `date_from`, `date_to`, `sort_by`, `sort_order`, `limit`, and `offset`. The legacy `/api/v1/reports/search` route remains available for the existing dashboard code path.

Each report contains `report_schema_version`, `detector_version`, and `model_version`. Current values are `v1`, `detector.day29`, and `lightweight-baseline.no-pretrained`.

Supported review states are `unreviewed`, `pending_review`, `reviewed`, `confirmed_ai`, `confirmed_real`, `false_positive`, `false_negative`, `needs_recheck`, and `ignored`; `needs_follow_up` is accepted for Day28 UI compatibility. Review updates write to SQLite and survive page refreshes and backend restarts.

Day29 does not add pretrained models, does not train a model, does not add PDF export, and does not redesign the dashboard UI.

## Goal

Day21 adds dashboard data endpoints on top of the Day20 JSON history export.

The Dashboard API is a frontend data layer. It does not improve detector accuracy, does not change score weights, does not add a database, and does not connect pretrained or open-source models. It summarizes existing detection history so a later React, Vue, Flutter, Electron, or other frontend can render cards, charts, and recent-result lists directly.

History source:

```text
outputs/api_history/
```

Schema version:

```text
dashboard_v1
```

Dashboard labels normalize historical API values into:

- `ai_generated`
- `real`
- `uncertain`

Risk levels normalize into:

- `low`
- `medium`
- `high`
- `unknown`

## GET /dashboard/summary

Returns compact dashboard summary data for cards, charts, alerts, recent results, and recent batch jobs.

Query parameters:

- `limit_recent`: integer, default `10`, min `1`, max `100`
- `include_debug`: boolean, default `false`

Example:

```bash
curl "http://127.0.0.1:8000/dashboard/summary"
```

Debug example:

```bash
curl "http://127.0.0.1:8000/dashboard/summary?limit_recent=20&include_debug=true"
```

Response shape:

```json
{
  "status": "ok",
  "generated_at": "2026-05-02T23:59:00+08:00",
  "summary": {
    "total_detections": 0,
    "single_detection_count": 0,
    "batch_detection_count": 0,
    "total_images_processed": 0,
    "final_label_distribution": {
      "ai_generated": 0,
      "real": 0,
      "uncertain": 0
    },
    "risk_level_distribution": {
      "low": 0,
      "medium": 0,
      "high": 0,
      "unknown": 0
    },
    "confidence_distribution": {
      "high_confidence": 0,
      "medium_confidence": 0,
      "low_confidence": 0
    },
    "decision_quality": {
      "uncertain_rate": 0.0,
      "high_risk_rate": 0.0,
      "average_confidence": 0.0
    }
  },
  "recent_results": [],
  "recent_batches": [],
  "chart_data": {
    "label_pie": [],
    "risk_bar": [],
    "confidence_bar": [],
    "daily_trend": []
  },
  "alerts": [],
  "debug": {
    "schema_version": "dashboard_v1"
  }
}
```

Notes:

- `total_detections` counts detection history tasks: single requests plus batch jobs.
- `total_images_processed` counts successful image-level result records loaded from history.
- Ratios are `0.0` to `1.0`.
- `recent_results` is compact and intentionally excludes `debug_evidence`.
- With `include_debug=true`, `debug` includes `history_source`, `result_files_loaded`, `skipped_files`, `warnings`, and `schema_version`.

## GET /dashboard/recent-results

Returns a frontend-ready recent result list for tables or cards.

Query parameters:

- `limit`: integer, default `20`, min `1`, max `100`
- `final_label`: optional, one of `ai_generated`, `real`, `uncertain`
- `risk_level`: optional, one of `low`, `medium`, `high`, `unknown`

Examples:

```bash
curl "http://127.0.0.1:8000/dashboard/recent-results?limit=20"
curl "http://127.0.0.1:8000/dashboard/recent-results?final_label=uncertain"
curl "http://127.0.0.1:8000/dashboard/recent-results?risk_level=high"
```

Response shape:

```json
{
  "status": "ok",
  "count": 1,
  "results": [
    {
      "id": "single_20260502_235900_abcd12",
      "timestamp": "2026-05-02T23:59:00+08:00",
      "filename": "sample.jpg",
      "final_label": "uncertain",
      "risk_level": "medium",
      "confidence": 0.52,
      "user_facing_summary": "Needs review.",
      "recommendation": "Review manually.",
      "history_type": "single",
      "history_file": "single_20260502_235900_abcd12.json",
      "batch_id": null
    }
  ]
}
```

## GET /dashboard/chart-data

Returns only chart-friendly arrays for ECharts, Recharts, Chart.js, or similar libraries.

Example:

```bash
curl "http://127.0.0.1:8000/dashboard/chart-data"
```

Response shape:

```json
{
  "status": "ok",
  "generated_at": "2026-05-02T23:59:00+08:00",
  "charts": {
    "label_distribution": [
      {"label": "AI Generated", "value": 0},
      {"label": "Real", "value": 0},
      {"label": "Uncertain", "value": 0}
    ],
    "risk_distribution": [
      {"label": "Low", "value": 0},
      {"label": "Medium", "value": 0},
      {"label": "High", "value": 0},
      {"label": "Unknown", "value": 0}
    ],
    "confidence_distribution": [
      {"label": "High Confidence", "value": 0},
      {"label": "Medium Confidence", "value": 0},
      {"label": "Low Confidence", "value": 0}
    ],
    "daily_detection_trend": [
      {"date": "2026-05-02", "count": 0}
    ]
  }
}
```

## Error Isolation

The Dashboard API reads history files defensively.

- Empty history returns `status: "ok"`.
- Missing fields fall back to safe defaults.
- Damaged JSON files are skipped.
- Skipped files are reported in debug mode, but one bad file does not break the whole API.

## Future Extensions

The current implementation is intentionally file-based and frontend-ready. Later stages can replace the JSON history directory with a real database, user accounts, async task queues, richer audit trails, and frontend dashboard pages without changing the dashboard response field names.
