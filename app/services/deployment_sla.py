from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class SlaThresholds:
    max_error_rate: float = 0.0
    min_active_primary_valid_rate: float = 0.95
    max_p95_server_latency_ms: float = 4500.0
    max_p95_wall_latency_ms: float | None = None
    min_ai_recall: float | None = None
    max_real_fp_rate: float | None = None


THRESHOLD_PROFILE = "local_preflight_smoke"

PACK_THRESHOLDS: dict[str, SlaThresholds] = {
    "defactify": SlaThresholds(
        max_error_rate=0.0,
        min_active_primary_valid_rate=0.95,
        max_p95_server_latency_ms=1600.0,
        min_ai_recall=0.50,
        max_real_fp_rate=0.10,
    ),
    "mirage": SlaThresholds(
        max_error_rate=0.0,
        min_active_primary_valid_rate=0.95,
        max_p95_server_latency_ms=4500.0,
        min_ai_recall=0.80,
        max_real_fp_rate=0.10,
    ),
}


def _metric(metrics: dict[str, Any], key: str) -> tuple[float, bool]:
    if key not in metrics:
        return 0.0, False
    try:
        number = float(metrics[key])
    except (TypeError, ValueError):
        return 0.0, False
    if not math.isfinite(number):
        return 0.0, False
    return number, True


def _metric_gate(
    checks: list[dict[str, Any]],
    *,
    name: str,
    metrics: dict[str, Any],
    threshold: float,
    direction: str,
    format_as_percent: bool = False,
) -> float:
    value, present = _metric(metrics, name)
    if not present:
        checks.append(
            _check(
                name,
                "fail",
                f"{name} is missing or not numeric.",
                value=metrics.get(name),
                threshold=threshold,
            )
        )
        return value
    passed = value <= threshold if direction == "max" else value >= threshold
    display = f"{value:.2%}" if format_as_percent else f"{value:.1f}"
    checks.append(
        _check(
            name,
            "pass" if passed else "fail",
            f"{name}={display}",
            value=value,
            threshold=threshold,
        )
    )
    return value


def _is_loopback_base_url(base_url: str) -> bool:
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except Exception:
        return False
    return host in {"127.0.0.1", "localhost", "::1"} or host.startswith("127.")


def _has_valid_http_base_url(base_url: str) -> bool:
    try:
        parsed = urlparse(base_url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _check(name: str, status: str, message: str, *, value: Any = None, threshold: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "value": value,
        "threshold": threshold,
    }


def thresholds_for_pack(pack: str, overrides: dict[str, Any] | None = None) -> SlaThresholds:
    base = PACK_THRESHOLDS.get(str(pack or "").lower(), SlaThresholds())
    values = {
        "max_error_rate": base.max_error_rate,
        "min_active_primary_valid_rate": base.min_active_primary_valid_rate,
        "max_p95_server_latency_ms": base.max_p95_server_latency_ms,
        "max_p95_wall_latency_ms": base.max_p95_wall_latency_ms,
        "min_ai_recall": base.min_ai_recall,
        "max_real_fp_rate": base.max_real_fp_rate,
    }
    for key, value in (overrides or {}).items():
        if key in values and value is not None:
            values[key] = value
    return SlaThresholds(**values)


def evaluate_concurrency_summary(summary: dict[str, Any], *, thresholds: SlaThresholds | None = None) -> dict[str, Any]:
    pack = str(summary.get("pack") or "unknown")
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    limits = thresholds or thresholds_for_pack(pack)
    checks: list[dict[str, Any]] = []

    sample_raw, sample_present = _metric(metrics, "sample_size")
    sample_size = int(sample_raw) if sample_present else 0
    checks.append(
        _check(
            "sample_size",
            "pass" if sample_present and sample_size > 0 else "fail",
            f"{sample_size} samples evaluated." if sample_present else "sample_size is missing or not numeric.",
            value=sample_size if sample_present else metrics.get("sample_size"),
            threshold="> 0",
        )
    )

    _metric_gate(
        checks,
        name="error_rate",
        metrics=metrics,
        threshold=limits.max_error_rate,
        direction="max",
        format_as_percent=True,
    )

    _metric_gate(
        checks,
        name="active_primary_valid_rate",
        metrics=metrics,
        threshold=limits.min_active_primary_valid_rate,
        direction="min",
        format_as_percent=True,
    )

    _metric_gate(
        checks,
        name="p95_server_latency_ms",
        metrics=metrics,
        threshold=limits.max_p95_server_latency_ms,
        direction="max",
    )

    if limits.max_p95_wall_latency_ms is not None:
        _metric_gate(
            checks,
            name="p95_wall_latency_ms",
            metrics=metrics,
            threshold=limits.max_p95_wall_latency_ms,
            direction="max",
        )

    if limits.min_ai_recall is not None:
        _metric_gate(
            checks,
            name="ai_recall",
            metrics=metrics,
            threshold=limits.min_ai_recall,
            direction="min",
            format_as_percent=True,
        )

    if limits.max_real_fp_rate is not None:
        _metric_gate(
            checks,
            name="real_fp_rate",
            metrics=metrics,
            threshold=limits.max_real_fp_rate,
            direction="max",
            format_as_percent=True,
        )

    failed = sum(1 for item in checks if item["status"] == "fail")
    return {
        "pack": pack,
        "policy_profile": summary.get("policy_profile") or "",
        "endpoint": summary.get("endpoint") or "",
        "concurrency": summary.get("concurrency") or 0,
        "sample_size": sample_size,
        "status": "fail" if failed else "pass",
        "threshold_profile": THRESHOLD_PROFILE,
        "checks": checks,
        "metrics": metrics,
        "thresholds": {
            "max_error_rate": limits.max_error_rate,
            "min_active_primary_valid_rate": limits.min_active_primary_valid_rate,
            "max_p95_server_latency_ms": limits.max_p95_server_latency_ms,
            "max_p95_wall_latency_ms": limits.max_p95_wall_latency_ms,
            "min_ai_recall": limits.min_ai_recall,
            "max_real_fp_rate": limits.max_real_fp_rate,
        },
    }


def evaluate_deployment_sla(
    *,
    concurrency_summaries: list[dict[str, Any]],
    readiness: dict[str, Any] | None = None,
    base_url: str = "",
    environment: str = "local_preflight",
    production: bool = False,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack_reports = [
        evaluate_concurrency_summary(summary, thresholds=thresholds_for_pack(str(summary.get("pack") or ""), overrides))
        for summary in concurrency_summaries
    ]
    checks: list[dict[str, Any]] = []
    if not pack_reports:
        checks.append(_check("concurrency_summaries", "fail", "No API concurrency summary files were provided."))
    for report in pack_reports:
        checks.append(
            _check(
                f"{report['pack']}_sla",
                report["status"],
                f"{report['pack']} SLA checks {report['status']}.",
                value=report["sample_size"],
            )
        )

    readiness_status = (readiness or {}).get("status")
    if readiness is not None:
        checks.append(
            _check(
                "readiness",
                "pass" if readiness_status in {"pass", "warn"} else "fail",
                f"readiness status is {readiness_status}.",
                value=readiness_status,
            )
        )

    if production and not str(base_url or "").strip():
        checks.append(
            _check(
                "environment_scope",
                "fail",
                "Production SLA evidence requires a non-empty production base_url.",
                value=base_url,
            )
        )
    elif production and not _has_valid_http_base_url(base_url):
        checks.append(
            _check(
                "environment_scope",
                "fail",
                "Production SLA evidence requires a valid http(s) base_url with a hostname.",
                value=base_url,
            )
        )
    elif production and _is_loopback_base_url(base_url):
        checks.append(
            _check(
                "environment_scope",
                "fail",
                "Production SLA evidence cannot use localhost or loopback base_url.",
                value=base_url,
            )
        )
    elif production:
        checks.append(_check("environment_scope", "pass", "Marked as production-host SLA evidence."))
    else:
        checks.append(
            _check(
                "environment_scope",
                "warn",
                "Local/preflight evidence only; repeat against the final production host before launch.",
                value=environment,
            )
        )

    failed = sum(1 for item in checks if item["status"] == "fail")
    warnings = sum(1 for item in checks if item["status"] == "warn")
    status = "fail" if failed else "warn" if warnings else "pass"
    return {
        "schema_version": "deployment_sla_check_v1",
        "status": status,
        "environment": environment,
        "base_url": base_url,
        "production": production,
        "threshold_profile": THRESHOLD_PROFILE,
        "summary": {
            "passed": sum(1 for item in checks if item["status"] == "pass"),
            "warnings": warnings,
            "failed": failed,
        },
        "checks": checks,
        "pack_reports": pack_reports,
        "readiness": readiness,
    }
