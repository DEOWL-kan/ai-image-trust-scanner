from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.services.deployment_sla import evaluate_concurrency_summary
from app.services.deployment_sla import evaluate_deployment_sla


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _summary(pack: str = "mirage", **metrics):
    base_metrics = {
        "sample_size": 40,
        "error_rate": 0.0,
        "active_primary_valid_rate": 1.0,
        "ai_recall": 0.9,
        "real_fp_rate": 0.05,
        "p95_server_latency_ms": 3000,
        "p95_wall_latency_ms": 3200,
    }
    base_metrics.update(metrics)
    return {
        "pack": pack,
        "policy_profile": "strict_safe_plus",
        "endpoint": "http://127.0.0.1:8000/api/detect/single",
        "concurrency": 4,
        "metrics": base_metrics,
    }


def test_deployment_sla_passes_pack_against_thresholds() -> None:
    report = evaluate_concurrency_summary(_summary())

    assert report["status"] == "pass"
    assert all(item["status"] == "pass" for item in report["checks"])


def test_deployment_sla_fails_slow_pack() -> None:
    report = evaluate_concurrency_summary(_summary(pack="defactify", p95_server_latency_ms=2200))

    assert report["status"] == "fail"
    assert any(item["name"] == "p95_server_latency_ms" and item["status"] == "fail" for item in report["checks"])


def test_deployment_sla_fails_missing_low_is_good_metric() -> None:
    summary = _summary()
    del summary["metrics"]["error_rate"]

    report = evaluate_concurrency_summary(summary)

    assert report["status"] == "fail"
    assert any(item["name"] == "error_rate" and item["status"] == "fail" for item in report["checks"])


def test_deployment_sla_fails_invalid_and_missing_required_metrics() -> None:
    summary = _summary(
        error_rate="bad",
        p95_server_latency_ms=float("nan"),
    )
    del summary["metrics"]["real_fp_rate"]

    report = evaluate_concurrency_summary(summary)

    assert report["status"] == "fail"
    failed_names = {item["name"] for item in report["checks"] if item["status"] == "fail"}
    assert {"error_rate", "p95_server_latency_ms", "real_fp_rate"}.issubset(failed_names)


def test_deployment_sla_marks_local_preflight_as_warning_not_production() -> None:
    report = evaluate_deployment_sla(
        concurrency_summaries=[_summary()],
        readiness={"status": "pass"},
        base_url="http://127.0.0.1:8000",
        environment="local_preflight",
        production=False,
    )

    assert report["status"] == "warn"
    assert any(item["name"] == "environment_scope" and item["status"] == "warn" for item in report["checks"])


def test_deployment_sla_rejects_production_loopback_base_url() -> None:
    report = evaluate_deployment_sla(
        concurrency_summaries=[_summary()],
        readiness={"status": "pass"},
        base_url="http://127.0.0.1:8000",
        environment="production",
        production=True,
    )

    assert report["status"] == "fail"
    assert any(item["name"] == "environment_scope" and item["status"] == "fail" for item in report["checks"])


def test_deployment_sla_rejects_production_empty_base_url() -> None:
    report = evaluate_deployment_sla(
        concurrency_summaries=[_summary()],
        readiness={"status": "pass"},
        base_url="",
        environment="production",
        production=True,
    )

    assert report["status"] == "fail"
    assert any(item["name"] == "environment_scope" and item["status"] == "fail" for item in report["checks"])


def test_deployment_sla_rejects_production_invalid_base_url() -> None:
    report = evaluate_deployment_sla(
        concurrency_summaries=[_summary()],
        readiness={"status": "pass"},
        base_url="prod-host",
        environment="production",
        production=True,
    )

    assert report["status"] == "fail"
    assert any(item["name"] == "environment_scope" and item["status"] == "fail" for item in report["checks"])


def test_deployment_sla_can_mark_production_evidence_when_explicit() -> None:
    report = evaluate_deployment_sla(
        concurrency_summaries=[_summary()],
        readiness={"status": "warn"},
        base_url="https://example.invalid",
        environment="prod-us-east",
        production=True,
    )

    assert report["status"] == "pass"
    assert any(item["name"] == "readiness" and item["status"] == "pass" for item in report["checks"])
    assert any(item["name"] == "environment_scope" and item["status"] == "pass" for item in report["checks"])


def test_deployment_sla_cli_exit_codes_and_scope_markdown(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    readiness_path = tmp_path / "readiness.json"
    output_path = tmp_path / "sla.json"
    markdown_path = tmp_path / "sla.md"
    summary_path.write_text(json.dumps(_summary()), encoding="utf-8")
    readiness_path.write_text(json.dumps({"status": "pass"}), encoding="utf-8")

    command = [
        sys.executable,
        "scripts/deployment_sla_check.py",
        "--summary",
        str(summary_path),
        "--readiness",
        str(readiness_path),
        "--base-url",
        "http://127.0.0.1:8000",
        "--environment",
        "local_preflight",
        "--output",
        str(output_path),
        "--markdown",
        str(markdown_path),
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 2

    report = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert report["source_paths"]["summaries"] == [str(summary_path)]
    assert report["source_paths"]["readiness"] == str(readiness_path)
    assert report["threshold_profile"] == "local_preflight_smoke"
    assert "threshold_profile: local_preflight_smoke" in markdown
    assert "This is local/preflight evidence only" in markdown

    result = subprocess.run([*command, "--allow-warnings"], cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0

    failing_summary_path = tmp_path / "slow_summary.json"
    failing_summary_path.write_text(json.dumps(_summary(pack="defactify", p95_server_latency_ms=2200)), encoding="utf-8")
    failing_result = subprocess.run(
        [
            sys.executable,
            "scripts/deployment_sla_check.py",
            "--summary",
            str(failing_summary_path),
            "--base-url",
            "http://127.0.0.1:8000",
            "--environment",
            "local_preflight",
            "--allow-warnings",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert failing_result.returncode == 1
