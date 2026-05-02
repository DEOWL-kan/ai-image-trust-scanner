# Day18 API Adapter Contract Report

## Day18 Goal

Day18 adds a thin API adapter above the existing detector and Day17 product output. The goal is to convert internal detection results into a stable, frontend-ready JSON contract without changing detector weights, adding pretrained models, or forcing uncertain cases into binary labels.

## Why An API Adapter Is Needed

Day17 made the result easier to read at the product layer, but its fields still reflect internal naming and shape choices such as `likely_ai`, string decision reasons, and free-form technical explanation text. Frontend code needs a smaller and more stable contract:

- fixed top-level success and error envelopes
- stable enums for labels, risk, and recommendation actions
- always-present fields, using `null`, `[]`, or `{}` when values are unavailable
- debug evidence that can be hidden without changing response shape

The adapter isolates frontend/API expectations from future internal detector changes.

## Success Response

Success responses are produced by `build_frontend_response(raw_result, image_meta=None, request_id=None, include_debug=True)` in `src/api_adapter.py`.

Top-level fields:

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | string | Currently `1.0.0`. |
| `status` | string | Always `success`. |
| `request_id` | string | Caller-provided or generated UUID. |
| `data.image` | object | Frontend-safe image metadata. |
| `data.result` | object | Adapted detection result. |
| `meta` | object | Processing timestamp and adapter metadata. |

Result fields:

| Field | Type | Notes |
| --- | --- | --- |
| `final_label` | enum | `ai_generated`, `real_photo`, or `uncertain`. |
| `risk_level` | enum | `low`, `medium`, or `high`. |
| `confidence` | number | Normalized to `0..1`; this is decision confidence, not model probability. |
| `decision_reason` | array | Objects with `code`, `message`, and `severity`. |
| `recommendation` | object | `action` enum plus a display-safe message. |
| `user_facing_summary` | string | Short user-facing explanation. |
| `technical_explanation` | object | Score, threshold, decision layer, and main signal names. |
| `debug_evidence` | object | Structured internal evidence, controlled by `include_debug`. |

## Error Response

Error responses are produced by `build_error_response(code, message, details=None, request_id=None)`.

Supported error codes:

| Code | Usage |
| --- | --- |
| `INVALID_IMAGE` | Input cannot be opened or parsed as an image. |
| `DETECTION_FAILED` | The detector pipeline failed after receiving an image. |
| `UNSUPPORTED_FORMAT` | The file format is not supported. |
| `INTERNAL_ERROR` | Fallback for unexpected adapter/API errors. |

The error envelope always contains `schema_version`, `status`, `request_id`, `error`, `data`, and `meta`. `data` is always `null`.

## Frontend Usage

Frontend clients should use:

- `final_label` for the primary badge or result state
- `risk_level` for visual priority
- `confidence` for calibrated display such as a percentage or meter
- `decision_reason[].message` for short explanation rows
- `recommendation.action` for product flow decisions
- `user_facing_summary` for non-technical copy
- `technical_explanation` for expandable technical details

Frontend clients should not parse internal `debug_evidence` for primary UI behavior.

## Debug Evidence

`debug_evidence` is intentionally always present. When `include_debug=True`, it contains raw score and grouped evidence. When `include_debug=False`, `enabled=false`, `raw_score=null`, and detail objects are empty. This allows public clients to hide internals without breaking typed frontend code or deleting the audit-friendly field.

## JSON Schema Files

- `schemas/detection_response.schema.json`
- `schemas/detection_error_response.schema.json`

The schemas validate required fields, enum values, basic types, and confidence range.

## Example Files

- `examples/day18_success_ai_generated.json`
- `examples/day18_success_real_photo.json`
- `examples/day18_success_uncertain.json`
- `examples/day18_error_invalid_image.json`

## Day18 Validation

Validation commands:

```bash
python -m pytest -q
python scripts/run_day18_contract_check.py
```

Latest local result:

- `python -m pytest -q`: 65 passed.
- `python scripts/run_day18_contract_check.py`: all four generated sample responses passed field completeness checks.

The contract check writes generated responses to `reports/day18/` and prints field completeness results.

## Day19 Suggestions

- Add a small HTTP layer only after the JSON contract is stable.
- Add OpenAPI documentation generated from the Day18 schema.
- Add UI snapshot examples that consume the contract without reading debug internals.
- Keep monitoring whether frontend copy should be localized separately from technical fields.
