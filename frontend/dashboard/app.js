const API_ENDPOINTS = {
  summary: "/dashboard/summary",
  recentResults: "/dashboard/recent-results?limit=20",
  chartData: "/dashboard/chart-data",
  detectSingle: "/api/v1/detect",
  detectBatchCandidates: ["/detect/batch", "/api/v1/detect/batch"],
};

const state = {
  dashboardLoading: false,
  singleLoading: false,
  batchLoading: false,
  selectedSingleFile: null,
  selectedBatchFiles: [],
};

const elements = {
  refreshButton: document.querySelector("#refresh-button"),
  serviceStatus: document.querySelector("#service-status"),
  serviceStatusText: document.querySelector("#service-status-text"),
  chartUpdatedAt: document.querySelector("#chart-updated-at"),
  recentCount: document.querySelector("#recent-count"),
  recentBody: document.querySelector("#recent-results-body"),
  recentEmptyState: document.querySelector("#recent-empty-state"),
  labelChart: document.querySelector("#label-chart"),
  riskChart: document.querySelector("#risk-chart"),
  confidenceChart: document.querySelector("#confidence-chart"),
  singleInput: document.querySelector("#single-file-input"),
  batchInput: document.querySelector("#batch-file-input"),
  singleFileLabel: document.querySelector("#single-file-label"),
  batchFileLabel: document.querySelector("#batch-file-label"),
  batchFileMeta: document.querySelector("#batch-file-meta"),
  singleButton: document.querySelector("#single-detect-button"),
  batchButton: document.querySelector("#batch-detect-button"),
  uploadResult: document.querySelector("#upload-result"),
};

function getValue(source, path, fallback = undefined) {
  const value = String(path)
    .split(".")
    .reduce((current, key) => {
      if (current && typeof current === "object" && key in current) {
        return current[key];
      }
      return undefined;
    }, source);
  return value === undefined || value === null || value === "" ? fallback : value;
}

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatInteger(value) {
  return Math.max(0, Math.round(toNumber(value))).toLocaleString();
}

function formatConfidence(value) {
  const number = toNumber(value, NaN);
  if (!Number.isFinite(number)) {
    return "--";
  }
  const normalized = number > 1 && number <= 100 ? number / 100 : number;
  return `${Math.round(Math.max(0, Math.min(1, normalized)) * 100)}%`;
}

function formatTimestamp(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function slug(value) {
  return String(value || "unknown")
    .trim()
    .toLowerCase()
    .replaceAll("_", "-")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function displayLabel(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function normalizeFinalLabel(value) {
  const label = String(value || "").trim().toLowerCase();
  if (["ai", "ai_generated", "likely_ai", "generated"].includes(label)) {
    return "ai";
  }
  if (["real", "real_photo", "likely_real", "authentic"].includes(label)) {
    return "real";
  }
  return "uncertain";
}

function resultSummaryText(item) {
  const reason = firstDefined(
    item.user_facing_summary,
    item.summary,
    item.decision_reason,
    item.recommendation,
    "--",
  );
  if (Array.isArray(reason)) {
    return reason.join("; ");
  }
  if (reason && typeof reason === "object") {
    return firstDefined(reason.message, reason.action, JSON.stringify(reason), "--");
  }
  return String(reason);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail = getValue(payload, "error.message", getValue(payload, "detail", response.statusText));
    const error = new Error(`${response.status} ${detail || response.statusText}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function setServiceStatus(status, label) {
  elements.serviceStatus.dataset.status = status;
  elements.serviceStatusText.textContent = label;
}

function setSummaryValue(key, value) {
  const node = document.querySelector(`[data-summary-key="${key}"]`);
  if (node) {
    node.textContent = value;
  }
}

function setUploadButtons() {
  elements.singleButton.disabled = state.singleLoading || !state.selectedSingleFile;
  elements.batchButton.disabled = state.batchLoading || state.selectedBatchFiles.length === 0;
  elements.singleButton.textContent = state.singleLoading ? "Analyzing..." : "Detect Image";
  elements.batchButton.textContent = state.batchLoading ? "Analyzing..." : "Batch Detect";
}

function renderSummary(payload) {
  const summary = getValue(payload, "summary", getValue(payload, "data.summary", {}));
  const labels = summary.final_label_distribution || summary.label_distribution || {};
  const risks = summary.risk_level_distribution || summary.risk_distribution || {};
  const quality = summary.decision_quality || {};

  setSummaryValue(
    "totalScans",
    formatInteger(firstDefined(summary.total_detections, summary.total_scans, summary.total, 0)),
  );
  setSummaryValue("aiDetected", formatInteger(firstDefined(labels.ai_generated, labels.ai, 0)));
  setSummaryValue("realDetected", formatInteger(firstDefined(labels.real, labels.real_photo, 0)));
  setSummaryValue("uncertain", formatInteger(firstDefined(labels.uncertain, 0)));
  setSummaryValue("highRisk", formatInteger(firstDefined(risks.high, risks.critical, 0)));
  setSummaryValue(
    "averageConfidence",
    formatConfidence(firstDefined(quality.average_confidence, summary.average_confidence, 0)),
  );
}

function renderChart(container, points, emptyMessage, errorMessage) {
  const safePoints = Array.isArray(points) ? points : [];
  if (errorMessage) {
    container.innerHTML = `<div class="error-state compact">${escapeHtml(errorMessage)}</div>`;
    return;
  }

  const max = Math.max(...safePoints.map((point) => toNumber(point.value)), 0);
  const total = safePoints.reduce((sum, point) => sum + toNumber(point.value), 0);
  if (!safePoints.length || total === 0) {
    container.innerHTML = `<div class="empty-state compact">${escapeHtml(emptyMessage)}</div>`;
    return;
  }

  container.innerHTML = safePoints
    .map((point) => {
      const value = Math.max(0, toNumber(point.value));
      const width = max > 0 ? Math.max(5, (value / max) * 100) : 0;
      const label = firstDefined(point.label, point.name, "Unknown");
      const className = slug(label);
      return `
        <div class="bar-row">
          <span class="bar-label">${escapeHtml(label)}</span>
          <span class="bar-track" aria-hidden="true">
            <span class="bar-fill ${className}" style="width: ${width}%"></span>
          </span>
          <span class="bar-value">${formatInteger(value)}</span>
        </div>
      `;
    })
    .join("");
}

function renderCharts(payload) {
  const charts = getValue(payload, "charts", getValue(payload, "chart_data", {}));
  elements.chartUpdatedAt.textContent = payload?.generated_at
    ? `Updated ${formatTimestamp(payload.generated_at)}`
    : "--";
  renderChart(elements.labelChart, charts.label_distribution || charts.label_pie, "No label data yet.");
  renderChart(elements.riskChart, charts.risk_distribution || charts.risk_bar, "No risk data yet.");
  renderChart(
    elements.confidenceChart,
    charts.confidence_distribution || charts.confidence_bar,
    "No confidence data yet.",
  );
}

function renderChartsError() {
  elements.chartUpdatedAt.textContent = "API error";
  renderChart(elements.labelChart, [], "", "Failed to load chart data.");
  renderChart(elements.riskChart, [], "", "Failed to load chart data.");
  renderChart(elements.confidenceChart, [], "", "Failed to load chart data.");
}

function renderRecentResults(payload) {
  const results = Array.isArray(payload?.results)
    ? payload.results
    : Array.isArray(payload?.recent_results)
      ? payload.recent_results
      : [];

  elements.recentCount.textContent = `${formatInteger(firstDefined(payload?.count, results.length))} results`;
  elements.recentBody.innerHTML = "";
  elements.recentEmptyState.hidden = results.length > 0;
  elements.recentEmptyState.textContent = "No recent detection results yet.";

  if (!results.length) {
    return;
  }

  elements.recentBody.innerHTML = results
    .map((item) => {
      const label = firstDefined(item.final_label, item.label, "uncertain");
      const risk = firstDefined(item.risk_level, item.risk, "unknown");
      const filename = firstDefined(item.filename, "unknown");
      const summary = resultSummaryText(item);
      return `
        <tr>
          <td>${escapeHtml(formatTimestamp(item.timestamp || item.created_at || item.processed_at))}</td>
          <td class="filename-cell" title="${escapeHtml(filename)}">${escapeHtml(filename)}</td>
          <td><span class="badge ${slug(label)}">${escapeHtml(displayLabel(label))}</span></td>
          <td><span class="badge ${slug(risk)}">${escapeHtml(risk)}</span></td>
          <td>${escapeHtml(formatConfidence(item.confidence))}</td>
          <td class="summary-cell" title="${escapeHtml(summary)}">
            <span class="summary-clamp">${escapeHtml(summary)}</span>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderRecentResultsError() {
  elements.recentCount.textContent = "API error";
  elements.recentBody.innerHTML = "";
  elements.recentEmptyState.hidden = false;
  elements.recentEmptyState.textContent = "Failed to load recent results.";
}

function renderUploadResult(kind, payload) {
  if (kind === "loading") {
    elements.uploadResult.innerHTML = `<div class="loading-state compact">${escapeHtml(payload.message)}</div>`;
    return;
  }
  if (kind === "error") {
    elements.uploadResult.innerHTML = `<div class="error-state compact">${escapeHtml(payload.message)}</div>`;
    return;
  }
  if (kind === "single") {
    const data = getValue(payload, "data", payload);
    const label = firstDefined(data.final_label, "uncertain");
    const risk = firstDefined(data.risk_level, "unknown");
    const filename = firstDefined(data.filename, state.selectedSingleFile?.name, "uploaded image");
    const summary = resultSummaryText(data);
    elements.uploadResult.innerHTML = `
      <article class="result-card">
        <div class="result-header">
          <div>
            <h3>Single detection complete</h3>
            <p title="${escapeHtml(filename)}">${escapeHtml(filename)}</p>
          </div>
          <span class="badge ${slug(label)}">${escapeHtml(displayLabel(label))}</span>
        </div>
        <div class="result-metrics">
          <div class="result-metric"><span>Label</span><strong>${escapeHtml(displayLabel(label))}</strong></div>
          <div class="result-metric"><span>Risk</span><strong>${escapeHtml(risk)}</strong></div>
          <div class="result-metric"><span>Confidence</span><strong>${escapeHtml(formatConfidence(data.confidence))}</strong></div>
          <div class="result-metric"><span>Status</span><strong>Saved</strong></div>
        </div>
        <div class="result-row">
          <span class="result-filename" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
          <span class="badge ${slug(label)}">${escapeHtml(displayLabel(label))}</span>
          <span class="badge ${slug(risk)}">${escapeHtml(risk)}</span>
          <span>${escapeHtml(formatConfidence(data.confidence))}</span>
        </div>
        <div class="result-row">
          <span class="summary-cell" title="${escapeHtml(summary)}">${escapeHtml(summary)}</span>
        </div>
      </article>
    `;
    return;
  }

  if (kind === "batch") {
    const results = Array.isArray(payload?.results) ? payload.results : [];
    const successfulResults = results
      .filter((item) => item && item.status === "success")
      .map((item) => ({ input: item.input || {}, result: item.result || {} }));
    const counts = successfulResults.reduce(
      (acc, item) => {
        acc[normalizeFinalLabel(item.result.final_label)] += 1;
        return acc;
      },
      { ai: 0, real: 0, uncertain: 0 },
    );
    const failed = toNumber(firstDefined(payload.failed, results.filter((item) => item.status === "failed").length));
    elements.uploadResult.innerHTML = `
      <article class="result-card">
        <div class="result-header">
          <div>
            <h3>Batch detection complete</h3>
            <p>${formatInteger(firstDefined(payload.succeeded, successfulResults.length))} succeeded, ${formatInteger(failed)} failed</p>
          </div>
          <span class="mini-badge">${escapeHtml(firstDefined(payload.batch_id, "batch"))}</span>
        </div>
        <div class="result-metrics">
          <div class="result-metric"><span>Total</span><strong>${formatInteger(payload.total)}</strong></div>
          <div class="result-metric"><span>AI</span><strong>${formatInteger(counts.ai)}</strong></div>
          <div class="result-metric"><span>Real</span><strong>${formatInteger(counts.real)}</strong></div>
          <div class="result-metric"><span>Uncertain</span><strong>${formatInteger(counts.uncertain)}</strong></div>
        </div>
        <div class="result-list">
          ${results
            .map((item) => {
              const result = item.result || {};
              const input = item.input || {};
              const filename = firstDefined(result.filename, input.filename, "unknown");
              if (item.status !== "success") {
                const message = getValue(item, "error.message", "Detection failed.");
                return `
                  <div class="result-row">
                    <span class="result-filename" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
                    <span class="badge failed">failed</span>
                    <span class="summary-cell">${escapeHtml(message)}</span>
                  </div>
                `;
              }
              const label = firstDefined(result.final_label, "uncertain");
              const risk = firstDefined(result.risk_level, "unknown");
              return `
                <div class="result-row">
                  <span class="result-filename" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
                  <span class="badge ${slug(label)}">${escapeHtml(displayLabel(label))}</span>
                  <span class="badge ${slug(risk)}">${escapeHtml(risk)}</span>
                  <span>${escapeHtml(formatConfidence(result.confidence))}</span>
                </div>
              `;
            })
            .join("")}
        </div>
      </article>
    `;
  }
}

async function loadDashboardData({ silent = false } = {}) {
  if (state.dashboardLoading) {
    return;
  }

  state.dashboardLoading = true;
  elements.refreshButton.disabled = true;
  elements.refreshButton.textContent = silent ? "Syncing" : "Refreshing";
  setServiceStatus("loading", "Checking");

  const [summaryResult, recentResult, chartResult] = await Promise.allSettled([
    fetchJson(API_ENDPOINTS.summary),
    fetchJson(API_ENDPOINTS.recentResults),
    fetchJson(API_ENDPOINTS.chartData),
  ]);

  if (summaryResult.status === "fulfilled") {
    setServiceStatus("online", "Online");
    renderSummary(summaryResult.value);
  } else {
    setServiceStatus("offline", "API Error");
    renderSummary({});
  }

  if (recentResult.status === "fulfilled") {
    renderRecentResults(recentResult.value);
  } else {
    renderRecentResultsError();
  }

  if (chartResult.status === "fulfilled") {
    renderCharts(chartResult.value);
  } else {
    renderChartsError();
  }

  state.dashboardLoading = false;
  elements.refreshButton.disabled = false;
  elements.refreshButton.textContent = "Refresh";
}

async function detectSingleImage() {
  if (!state.selectedSingleFile || state.singleLoading) {
    return;
  }
  state.singleLoading = true;
  setUploadButtons();
  renderUploadResult("loading", { message: "Analyzing image..." });

  const formData = new FormData();
  formData.append("file", state.selectedSingleFile);

  try {
    const payload = await fetchJson(API_ENDPOINTS.detectSingle, {
      method: "POST",
      body: formData,
    });
    renderUploadResult("single", payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    renderUploadResult("error", {
      message: `Single detection failed: ${error.message || "Unknown error"}`,
    });
  } finally {
    state.singleLoading = false;
    setUploadButtons();
  }
}

async function postBatchDetection(formData) {
  let lastError = null;
  for (const endpoint of API_ENDPOINTS.detectBatchCandidates) {
    try {
      return await fetchJson(endpoint, {
        method: "POST",
        body: formData,
      });
    } catch (error) {
      lastError = error;
      if (![404, 405].includes(error.status)) {
        throw error;
      }
    }
  }
  throw lastError || new Error("No batch detection endpoint is available.");
}

async function detectBatchImages() {
  if (!state.selectedBatchFiles.length || state.batchLoading) {
    return;
  }
  state.batchLoading = true;
  setUploadButtons();
  renderUploadResult("loading", { message: `Analyzing ${state.selectedBatchFiles.length} images...` });

  const formData = new FormData();
  state.selectedBatchFiles.forEach((file) => {
    formData.append("files", file);
  });

  try {
    const payload = await postBatchDetection(formData);
    renderUploadResult("batch", payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    renderUploadResult("error", {
      message: `Batch detection failed: ${error.message || "Unknown error"}`,
    });
  } finally {
    state.batchLoading = false;
    setUploadButtons();
  }
}

elements.singleInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0] || null;
  state.selectedSingleFile = file;
  elements.singleFileLabel.textContent = file ? file.name : "Choose an image";
  setUploadButtons();
});

elements.batchInput.addEventListener("change", (event) => {
  state.selectedBatchFiles = Array.from(event.target.files || []);
  const count = state.selectedBatchFiles.length;
  elements.batchFileLabel.textContent = count ? `${count} images selected` : "Choose multiple images";
  elements.batchFileMeta.textContent = count
    ? state.selectedBatchFiles.map((file) => file.name).slice(0, 2).join(", ") + (count > 2 ? "..." : "")
    : "No images selected";
  setUploadButtons();
});

elements.singleButton.addEventListener("click", detectSingleImage);
elements.batchButton.addEventListener("click", detectBatchImages);
elements.refreshButton.addEventListener("click", () => loadDashboardData());

setUploadButtons();
window.addEventListener("DOMContentLoaded", () => loadDashboardData());
