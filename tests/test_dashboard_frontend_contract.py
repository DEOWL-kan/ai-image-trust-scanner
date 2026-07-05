from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _extract_js_function(source: str, name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", source)
    assert match is not None, f"Missing JS function {name}"
    paren_depth = 1
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    param_end = -1
    for index in range(match.end(), len(source)):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
            if paren_depth == 0:
                param_end = index
                break
    assert param_end != -1, f"Missing JS function parameter close for {name}"
    brace_start = source.find("{", param_end)
    assert brace_start != -1, f"Missing JS function body for {name}"

    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    for index in range(brace_start, len(source)):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"Unterminated JS function {name}")


def test_dashboard_exposes_p2_readiness_panel_and_small_summary_endpoints() -> None:
    html = (PROJECT_ROOT / "frontend" / "dashboard" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")

    assert "calibration-readiness-grid" in html
    assert "training-label-queue-list" in html
    assert "review-calibration?limit=1" in app_js
    assert "scenario-stress-pack?limit=1" in app_js
    assert "training-readiness?limit=1" in app_js
    assert "training-label-queue?limit=8" in app_js
    assert "training-readiness/rebuild" in app_js
    assert "renderCalibrationReadiness" in app_js
    assert "renderTrainingLabelQueue" in app_js
    assert "training-label-quick-review" in app_js


def test_dashboard_single_detection_waits_for_warmup_and_retries_once() -> None:
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")

    assert "waitForScanReady" in app_js
    assert "warmup_ready" in app_js
    assert "postSingleDetectionWithRetry" in app_js
    assert "isRetryableSingleDetectionError" in app_js
    assert "buildSingleDetectionFormData(file)" in app_js
    assert "postSingleDetectionWithRetry(singleUrl, fileForDetection)" in app_js
    assert "retryRequestOptions" in app_js
    assert "timeoutMs: 120000" in app_js
    assert "lastProbeError" in app_js
    assert "backendReconnectWaiting" in app_js
    assert "retryingConnection" in app_js
    assert "timeoutMs: 300000" in app_js


def test_dashboard_health_probe_sends_api_key_headers() -> None:
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")

    assert 'headers: { Accept: "application/json", ...authHeaders() }' in app_js


def test_dashboard_single_detection_retry_behavior_executes_actual_js(tmp_path: Path) -> None:
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")
    functions = "\n\n".join(
        _extract_js_function(app_js, name)
        for name in [
            "buildSingleDetectionFormData",
            "isRetryableSingleDetectionError",
            "postSingleDetectionWithRetry",
        ]
    )
    harness = tmp_path / "single_detection_retry_contract.js"
    harness.write_text(
        textwrap.dedent(
            f"""
            const assert = require("assert");

            const fetchCalls = [];
            const formDataInstances = [];
            const waitCalls = [];
            const renderMessages = [];
            const sleepCalls = [];
            let fetchPlan = [];

            class FormData {{
              constructor() {{
                this.entries = [];
                formDataInstances.push(this);
              }}
              append(key, value) {{
                this.entries.push([key, value]);
              }}
            }}

            function statusCopy(key) {{
              return key;
            }}

            function renderLoadingResult(message) {{
              renderMessages.push(message);
            }}

            async function sleep(ms) {{
              sleepCalls.push(ms);
            }}

            async function waitForScanReady(options) {{
              waitCalls.push(options);
              return {{ warmup_ready: true }};
            }}

            async function fetchJson(url, options) {{
              fetchCalls.push({{ url, options }});
              const step = fetchPlan.shift();
              if (!step) throw new Error("Unexpected fetchJson call");
              if (step.error) throw step.error;
              return step.value;
            }}

            function makeError(status, message, payload = null) {{
              const error = new Error(message);
              error.status = status;
              error.payload = payload;
              return error;
            }}

            {functions}

            async function main() {{
              assert.strictEqual(isRetryableSingleDetectionError(makeError(0, "connection failed")), true);
              assert.strictEqual(isRetryableSingleDetectionError(makeError(503, "warming")), true);
              assert.strictEqual(isRetryableSingleDetectionError(makeError(500, "warmup not complete")), true);
              assert.strictEqual(isRetryableSingleDetectionError(makeError(500, "permanent detector failure")), false);
              assert.strictEqual(isRetryableSingleDetectionError(makeError(422, "invalid form")), false);

              const file = {{ name: "first.png" }};
              fetchPlan = [
                {{ error: makeError(503, "backend warmup temporarily unavailable") }},
                {{ value: {{ ok: true }} }},
              ];
              const payload = await postSingleDetectionWithRetry("http://127.0.0.1:8000/api/detect/single", file);
              assert.deepStrictEqual(payload, {{ ok: true }});
              assert.strictEqual(fetchCalls.length, 2);
              assert.strictEqual(fetchCalls[0].options.timeoutMs, 300000);
              assert.strictEqual(fetchCalls[1].options.timeoutMs, 120000);
              assert.strictEqual(fetchCalls[0].options.method, "POST");
              assert.strictEqual(fetchCalls[1].options.method, "POST");
              assert.notStrictEqual(fetchCalls[0].options.body, fetchCalls[1].options.body);
              assert.deepStrictEqual(fetchCalls[0].options.body.entries, [["file", file]]);
              assert.deepStrictEqual(fetchCalls[1].options.body.entries, [["file", file]]);
              assert.strictEqual(formDataInstances.length, 2);
              assert.deepStrictEqual(waitCalls, [{{ timeoutMs: 45000, intervalMs: 1500 }}]);
              assert.deepStrictEqual(sleepCalls, [1200]);
              assert.deepStrictEqual(renderMessages, ["retryingConnection"]);

              fetchCalls.length = 0;
              formDataInstances.length = 0;
              waitCalls.length = 0;
              renderMessages.length = 0;
              sleepCalls.length = 0;
              fetchPlan = [{{ error: makeError(422, "invalid multipart body") }}];
              await assert.rejects(
                () => postSingleDetectionWithRetry("http://127.0.0.1:8000/api/detect/single", file),
                /invalid multipart body/
              );
              assert.strictEqual(fetchCalls.length, 1);
              assert.strictEqual(fetchCalls[0].options.timeoutMs, 300000);
              assert.strictEqual(formDataInstances.length, 1);
              assert.deepStrictEqual(waitCalls, []);
              assert.deepStrictEqual(sleepCalls, []);
              assert.deepStrictEqual(renderMessages, []);

              fetchCalls.length = 0;
              formDataInstances.length = 0;
              waitCalls.length = 0;
              renderMessages.length = 0;
              sleepCalls.length = 0;
              fetchPlan = [
                {{ error: makeError(503, "backend warmup temporarily unavailable") }},
                {{ error: makeError(503, "backend still unavailable") }},
              ];
              await assert.rejects(
                () => postSingleDetectionWithRetry("http://127.0.0.1:8000/api/detect/single", file),
                /backend still unavailable/
              );
              assert.strictEqual(fetchCalls.length, 2);
              assert.strictEqual(fetchCalls[0].options.timeoutMs, 300000);
              assert.strictEqual(fetchCalls[1].options.timeoutMs, 120000);
              assert.strictEqual(formDataInstances.length, 2);
              assert.deepStrictEqual(waitCalls, [{{ timeoutMs: 45000, intervalMs: 1500 }}]);
              assert.deepStrictEqual(sleepCalls, [1200]);
              assert.deepStrictEqual(renderMessages, ["retryingConnection"]);
            }}

            main().catch((error) => {{
              console.error(error);
              process.exit(1);
            }});
            """
        ),
        encoding="utf-8",
    )

    subprocess.run(["node", str(harness)], cwd=PROJECT_ROOT, check=True)


def test_dashboard_wait_for_scan_ready_continues_after_probe_failure(tmp_path: Path) -> None:
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")
    harness = tmp_path / "wait_for_scan_ready_contract.js"
    harness.write_text(
        textwrap.dedent(
            f"""
            const assert = require("assert");

            const healthCalls = [];
            const systemStatusCalls = [];
            const renderMessages = [];
            const sleepCalls = [];
            const state = {{
              lang: "en",
              systemHealth: null,
              modelStatus: {{ loaded: true }},
            }};
            let healthPlan = [
              {{ error: Object.assign(new Error("connection refused"), {{ status: 0 }}) }},
              {{ value: {{ warmup_ready: false, phase: "loading" }} }},
              {{ value: {{ warmup_ready: true, phase: "ready" }} }},
            ];

            async function ensureApiBaseReachable(options) {{
              healthCalls.push(options);
              const step = healthPlan.shift();
              if (!step) throw new Error("Unexpected health probe");
              if (step.error) throw step.error;
              return step.value;
            }}

            function renderSystemStatus(health, loading, modelStatus) {{
              systemStatusCalls.push({{ health, loading, modelStatus }});
            }}

            function statusCopy(key) {{
              return key;
            }}

            function renderLoadingResult(message) {{
              renderMessages.push(message);
            }}

            async function sleep(ms) {{
              sleepCalls.push(ms);
            }}

            {_extract_js_function(app_js, "waitForScanReady")}

            async function main() {{
              const result = await waitForScanReady({{ timeoutMs: 1000, intervalMs: 25 }});
              assert.deepStrictEqual(result, {{ warmup_ready: true, phase: "ready" }});
              assert.deepStrictEqual(healthCalls, [
                {{ timeoutMs: 5000, force: true }},
                {{ timeoutMs: 5000, force: true }},
                {{ timeoutMs: 5000, force: true }},
              ]);
              assert.strictEqual(systemStatusCalls.length, 2);
              assert.deepStrictEqual(systemStatusCalls[0], {{
                health: {{ warmup_ready: false, phase: "loading" }},
                loading: false,
                modelStatus: state.modelStatus,
              }});
              assert.deepStrictEqual(systemStatusCalls[1], {{
                health: {{ warmup_ready: true, phase: "ready" }},
                loading: false,
                modelStatus: state.modelStatus,
              }});
              assert.deepStrictEqual(renderMessages, ["backendReconnectWaiting", "warmupWaiting"]);
              assert.deepStrictEqual(sleepCalls, [25, 25]);
              assert.deepStrictEqual(state.systemHealth, {{ warmup_ready: true, phase: "ready" }});
            }}

            main().catch((error) => {{
              console.error(error);
              process.exit(1);
            }});
            """
        ),
        encoding="utf-8",
    )

    subprocess.run(["node", str(harness)], cwd=PROJECT_ROOT, check=True)


def test_dashboard_run_single_detection_waits_before_post_and_snapshots_file(tmp_path: Path) -> None:
    app_js = (PROJECT_ROOT / "frontend" / "dashboard" / "app.js").read_text(encoding="utf-8")
    harness = tmp_path / "run_single_detection_contract.js"
    harness.write_text(
        textwrap.dedent(
            f"""
            const assert = require("assert");

            const initialFile = {{ name: "first-selected.png" }};
            const order = [];
            const classNames = new Set();
            let postArgs = null;
            let errorRender = null;
            let dashboardRefreshOptions = null;
            const elements = {{ singleUploadCard: {{}} }};
            const state = {{
              selectedSingleFile: initialFile,
              singleLoading: false,
              singleStatus: "idle",
              currentResult: {{ stale: true }},
              prefersReducedMotion: true,
              policyProfile: "strict safe+/profile",
            }};
            const document = {{
              body: {{
                classList: {{
                  add(name) {{
                    order.push(`class:add:${{name}}`);
                    classNames.add(name);
                  }},
                  remove(name) {{
                    order.push(`class:remove:${{name}}`);
                    classNames.delete(name);
                  }},
                }},
              }},
              querySelector() {{
                return {{ scrollIntoView() {{ order.push("scroll"); }} }};
              }},
            }};
            const API_ENDPOINTS = {{
              get detectSingle() {{
                return "http://127.0.0.1:8000/api/detect/single";
              }},
            }};

            function setDemoTab(value) {{ order.push(`tab:${{value}}`); }}
            function renderErrorResult(message, payload) {{ errorRender = {{ message, payload }}; }}
            function flashUploadError() {{ order.push("flash"); }}
            function statusCopy(key) {{ return key; }}
            function setUploadButtons() {{ order.push(`buttons:${{state.singleLoading}}:${{state.singleStatus}}`); }}
            function renderLoadingResult(message) {{ order.push(`loading:${{message}}`); }}
            let releaseWarmup = null;
            const warmupPromise = new Promise((resolve) => {{
              releaseWarmup = resolve;
            }});
            async function waitForScanReady() {{
              order.push("wait");
              state.selectedSingleFile = {{ name: "changed-before-post.png" }};
              return warmupPromise;
            }}
            async function postSingleDetectionWithRetry(url, file) {{
              order.push("post");
              postArgs = {{ url, file }};
              return {{ verdict: "ok" }};
            }}
            function renderSingleResult(payload) {{
              order.push(`render:${{payload.verdict}}`);
            }}
            async function loadDashboardData(options) {{
              order.push("refresh");
              dashboardRefreshOptions = options;
            }}
            function t(key) {{ return key; }}

            {_extract_js_function(app_js, "runSingleDetection")}

            async function main() {{
              const runPromise = runSingleDetection();
              await Promise.resolve();
              assert.deepStrictEqual(order, [
                "class:add:is-scanning",
                "buttons:true:detecting",
                "loading:detectingBody",
                "wait",
              ]);
              assert.strictEqual(postArgs, null);
              assert.strictEqual(state.singleLoading, true);
              assert.strictEqual(state.singleStatus, "detecting");

              releaseWarmup();
              await runPromise;
              assert.deepStrictEqual(order, [
                "class:add:is-scanning",
                "buttons:true:detecting",
                "loading:detectingBody",
                "wait",
                "post",
                "render:ok",
                "refresh",
                "class:remove:is-scanning",
                "buttons:false:success",
              ]);
              assert.strictEqual(postArgs.file, initialFile);
              assert.strictEqual(
                postArgs.url,
                "http://127.0.0.1:8000/api/detect/single?policy_profile=strict%20safe%2B%2Fprofile"
              );
              assert.strictEqual(state.selectedSingleFile.name, "changed-before-post.png");
              assert.strictEqual(state.singleStatus, "success");
              assert.strictEqual(state.singleLoading, false);
              assert.strictEqual(state.currentResult, null);
              assert.deepStrictEqual(dashboardRefreshOptions, {{ silent: true }});
              assert.strictEqual(classNames.has("is-scanning"), false);
              assert.strictEqual(errorRender, null);
            }}

            main().catch((error) => {{
              console.error(error);
              process.exit(1);
            }});
            """
        ),
        encoding="utf-8",
    )

    subprocess.run(["node", str(harness)], cwd=PROJECT_ROOT, check=True)
