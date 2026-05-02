# Day17 Selective Evaluation

## Day17 Goal
Day17 upgrades detector outputs into a front-end/API-ready product schema and evaluates key risk subsets. It does not re-tune the detector or claim commercial-grade accuracy.

## Core Detection Policy
No core detection weights, AI/Real score formulas, baseline thresholds, or pretrained model dependencies were modified for this report.

## Product Schema Fields
- `final_label`: product label mapped to `likely_ai`, `likely_real`, or `uncertain`.
- `risk_level`: product risk bucket, limited to `high`, `medium`, or `low`.
- `confidence`: rule-based decision confidence, not a model probability.
- `decision_reason`: short user-facing reasons for the decision.
- `recommendation`: next action guidance.
- `user_facing_summary`: short explanation for ordinary users.
- `technical_explanation`: developer/reviewer explanation.
- `debug_evidence`: stable debug dictionary for API and front-end panels.

## Selective Evaluation Results

| subset | total | labels | risks | avg_confidence | uncertain_ratio |
| --- | --- | --- | --- | --- | --- |
| all_samples | 660 | {'likely_ai': 221, 'uncertain': 344, 'likely_real': 95} | {'high': 221, 'medium': 439} | 0.6331 | 0.521212 |
| uncertain_samples | 344 | {'uncertain': 344} | {'medium': 344} | 0.4818 | 1.0 |
| likely_ai_samples | 221 | {'likely_ai': 221} | {'high': 221} | 0.8753 | 0.0 |
| likely_real_samples | 95 | {'likely_real': 95} | {'medium': 95} | 0.6172 | 0.0 |
| medium_risk_samples | 439 | {'uncertain': 344, 'likely_real': 95} | {'medium': 439} | 0.5111 | 0.783599 |
| high_risk_samples | 221 | {'likely_ai': 221} | {'high': 221} | 0.8753 | 0.0 |
| possible_format_risk_samples | 657 | {'likely_ai': 220, 'uncertain': 342, 'likely_real': 95} | {'high': 220, 'medium': 437} | 0.6332 | 0.520548 |
| resolution_sensitive_samples | 298 | {'uncertain': 203, 'likely_real': 95} | {'medium': 298} | 0.5184 | 0.681208 |

## Frontend/API Readiness
The product output layer is ready to connect to a front-end or API as a stable schema. The confidence field is explicitly a rule-based decision confidence, and debug evidence keeps raw Day16.1 fields available without changing existing reports.

## Existing Issues
- Accuracy is still limited by the current heuristic detector and overlapping score space.
- Missing EXIF, JPEG compression, and resolution sensitivity can lower interpretability.
- `uncertain` should be treated as a product state, not a failure.

## Day18 Suggestions
- Add API response examples and front-end debug panel rendering.
- Add a small product copy QA pass for Chinese/English messages.
- Track user-facing false-positive/false-negative examples without changing the core scoring formula.

## Output Files
- product_outputs: `D:\ai image\ai-image-trust-scanner\reports\day17_product_outputs.json`
- selective_evaluation_json: `D:\ai image\ai-image-trust-scanner\reports\day17_selective_evaluation.json`
- selective_evaluation_md: `D:\ai image\ai-image-trust-scanner\reports\day17_selective_evaluation.md`
