from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.deployment_sla import evaluate_deployment_sla  # noqa: E402


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check_message(pack_report: dict[str, Any], name: str, default: str = "missing") -> str:
    for item in pack_report.get("checks", []):
        if item.get("name") == name:
            return str(item.get("message") or default)
    return default


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Deployment SLA Check",
        "",
        f"- status: {report.get('status')}",
        f"- environment: {report.get('environment')}",
        f"- base_url: {report.get('base_url') or 'not recorded'}",
        f"- production: {report.get('production')}",
        f"- threshold_profile: {report.get('threshold_profile')}",
        f"- passed: {(report.get('summary') or {}).get('passed')}",
        f"- warnings: {(report.get('summary') or {}).get('warnings')}",
        f"- failed: {(report.get('summary') or {}).get('failed')}",
        "",
    ]
    source_paths = report.get("source_paths") if isinstance(report.get("source_paths"), dict) else {}
    summary_paths = source_paths.get("summaries") if isinstance(source_paths.get("summaries"), list) else []
    readiness_path = str(source_paths.get("readiness") or "")
    if summary_paths or readiness_path:
        lines.extend(["## Sources", ""])
        lines.extend(f"- summary: {path}" for path in summary_paths)
        if readiness_path:
            lines.append(f"- readiness: {readiness_path}")
        lines.append("")
    lines.extend(["## Checks", ""])
    for item in report.get("checks", []):
        lines.append(f"- {item.get('status')}: {item.get('name')} - {item.get('message')}")

    lines.extend(["", "## Packs", ""])
    for pack_report in report.get("pack_reports", []):
        lines.extend(
            [
                f"### {pack_report.get('pack')}",
                "",
                f"- status: {pack_report.get('status')}",
                f"- policy_profile: {pack_report.get('policy_profile')}",
                f"- concurrency: {pack_report.get('concurrency')}",
                f"- sample_size: {pack_report.get('sample_size')}",
                f"- error_rate: {_check_message(pack_report, 'error_rate')}",
                f"- active_primary_valid_rate: {_check_message(pack_report, 'active_primary_valid_rate')}",
                f"- ai_recall: {_check_message(pack_report, 'ai_recall')}",
                f"- real_fp_rate: {_check_message(pack_report, 'real_fp_rate')}",
                f"- p95_server_latency_ms: {_check_message(pack_report, 'p95_server_latency_ms')}",
                "",
            ]
        )
        for item in pack_report.get("checks", []):
            threshold = item.get("threshold")
            suffix = f" (threshold: {threshold})" if threshold is not None else ""
            lines.append(f"- {item.get('status')}: {item.get('name')} - {item.get('message')}{suffix}")
        lines.append("")

    if not report.get("production"):
        lines.extend(
            [
                "## Scope",
                "",
                "This is local/preflight evidence only. It must be repeated against the final production host before public launch.",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Minerva deployment SLA gates from readiness and API smoke outputs.")
    parser.add_argument("--summary", action="append", default=[], help="Path to api_concurrency_summary.json. Repeat for multiple packs.")
    parser.add_argument("--readiness", default="", help="Optional product readiness JSON report.")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--environment", default="local_preflight")
    parser.add_argument("--production", action="store_true", help="Mark this evidence as production-host evidence.")
    parser.add_argument("--max-p95-server-latency-ms", type=float, default=None, help="Override per-pack p95 server latency threshold.")
    parser.add_argument("--max-p95-wall-latency-ms", type=float, default=None)
    parser.add_argument("--min-ai-recall", type=float, default=None)
    parser.add_argument("--max-real-fp-rate", type=float, default=None)
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown", default="")
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    overrides = {
        "max_p95_server_latency_ms": args.max_p95_server_latency_ms,
        "max_p95_wall_latency_ms": args.max_p95_wall_latency_ms,
        "min_ai_recall": args.min_ai_recall,
        "max_real_fp_rate": args.max_real_fp_rate,
    }
    summaries = [_load_json(path) for path in args.summary]
    readiness = _load_json(args.readiness) if args.readiness else None
    report = evaluate_deployment_sla(
        concurrency_summaries=summaries,
        readiness=readiness,
        base_url=args.base_url,
        environment=args.environment,
        production=args.production,
        overrides=overrides,
    )
    report["source_paths"] = {
        "summaries": [str(Path(path)) for path in args.summary],
        "readiness": str(Path(args.readiness)) if args.readiness else "",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_markdown(report), encoding="utf-8")
    if report["status"] == "fail":
        return 1
    if report["status"] == "warn" and not args.allow_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
