from __future__ import annotations

import sys
from types import SimpleNamespace

from scripts import run_local_dashboard


def test_with_models_defaults_allow_hugging_face_downloads(monkeypatch) -> None:
    for name in [
        "DETECTOR_RUNTIME_MODE",
        "DETECTOR_WARMUP_ON_STARTUP",
        "DETECTOR_ALLOW_COLD_MODEL_LOAD",
        "HF_LOCAL_FILES_ONLY",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
    ]:
        monkeypatch.delenv(name, raising=False)

    run_local_dashboard._model_mode_defaults(offline=False)

    assert run_local_dashboard.parse_args(["--with-models"]).with_models is True
    assert run_local_dashboard.parse_args(["--with-models"]).offline is False
    assert run_local_dashboard.parse_args(["--with-models", "--offline"]).offline is True
    assert run_local_dashboard._hf_offline_requested(False) is False
    assert run_local_dashboard._hf_offline_requested(True) is True
    assert run_local_dashboard._hf_cache_mode_label() == "online downloads allowed"
    assert run_local_dashboard.os.environ["DETECTOR_RUNTIME_MODE"] == "local_hf"
    assert run_local_dashboard.os.environ["DETECTOR_WARMUP_ON_STARTUP"] == "true"
    assert run_local_dashboard.os.environ["HF_LOCAL_FILES_ONLY"] == "false"


def test_with_models_offline_forces_local_files_only(monkeypatch) -> None:
    monkeypatch.delenv("HF_LOCAL_FILES_ONLY", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    run_local_dashboard._model_mode_defaults(offline=True)

    assert run_local_dashboard.os.environ["DETECTOR_RUNTIME_MODE"] == "local_hf"
    assert run_local_dashboard.os.environ["HF_LOCAL_FILES_ONLY"] == "true"
    assert run_local_dashboard._hf_offline_requested(True) is True
    assert run_local_dashboard._hf_cache_mode_label() == "offline cache only"


def test_hf_offline_env_still_overrides_download_default(monkeypatch) -> None:
    monkeypatch.setenv("HF_LOCAL_FILES_ONLY", "true")
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    assert run_local_dashboard._hf_offline_requested(False) is True

    run_local_dashboard._model_mode_defaults(offline=True)

    assert run_local_dashboard.os.environ["HF_LOCAL_FILES_ONLY"] == "true"


def test_online_with_models_prewarms_before_serving(monkeypatch, capsys) -> None:
    calls: list[str] = []

    def fake_prewarm() -> dict:
        calls.append("prewarm")
        return {
            "loaded": [
                {"detector_id": "smogy", "model_loaded": True},
                {"detector_id": "ateeqq", "model_loaded": True},
            ]
        }

    def fake_run(*args, **kwargs) -> None:
        calls.append("uvicorn")

    monkeypatch.setattr(run_local_dashboard, "_missing_optional_model_modules", lambda: [])
    monkeypatch.setattr(run_local_dashboard, "_prewarm_optional_models", fake_prewarm)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=fake_run))
    monkeypatch.delenv("HF_LOCAL_FILES_ONLY", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    exit_code = run_local_dashboard.main(["--with-models", "--port", "8899"])

    assert exit_code == 0
    assert calls == ["prewarm", "uvicorn"]
    output = capsys.readouterr().out
    assert "Downloading/loading models (Smogy ~348MB, Ateeqq ~372MB)" in output
    assert "Model warmup complete" in output
    assert "Dashboard: http://127.0.0.1:8899/dashboard-ui/index.html" in output


def test_offline_with_models_skips_online_prewarm(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(*args, **kwargs) -> None:
        calls.append("uvicorn")

    monkeypatch.setattr(run_local_dashboard, "_missing_optional_model_modules", lambda: [])
    monkeypatch.setattr(run_local_dashboard, "_prewarm_optional_models", lambda: calls.append("prewarm"))
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=fake_run))
    monkeypatch.delenv("HF_LOCAL_FILES_ONLY", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    exit_code = run_local_dashboard.main(["--with-models", "--offline", "--port", "8899"])

    assert exit_code == 0
    assert calls == ["uvicorn"]


def test_online_with_models_reports_warmup_failure_without_serving(monkeypatch, capsys) -> None:
    calls: list[str] = []

    def fake_prewarm() -> dict:
        raise RuntimeError("smogy download timed out")

    def fake_run(*args, **kwargs) -> None:
        calls.append("uvicorn")

    monkeypatch.setattr(run_local_dashboard, "_missing_optional_model_modules", lambda: [])
    monkeypatch.setattr(run_local_dashboard, "_prewarm_optional_models", fake_prewarm)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=fake_run))
    monkeypatch.delenv("HF_LOCAL_FILES_ONLY", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    exit_code = run_local_dashboard.main(["--with-models", "--port", "8899"])

    assert exit_code == 3
    assert calls == []
    error = capsys.readouterr().err
    assert "Optional model warmup failed before the dashboard started." in error
    assert "smogy download timed out" in error
