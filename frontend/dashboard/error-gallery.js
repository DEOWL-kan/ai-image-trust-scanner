const ERROR_ENDPOINTS = {
  summary: "/api/v1/errors/summary",
  list: "/api/v1/errors",
  detail: (id) => `/api/v1/errors/${encodeURIComponent(id)}`,
  review: (id) => `/api/v1/errors/${encodeURIComponent(id)}/review`,
};

const state = {
  type: "all",
  scenario: "",
  format: "",
  resolutionBucket: "",
  sourceFolder: "",
  sort: "confidence_desc",
  limit: 24,
  offset: 0,
  total: 0,
  currentItem: null,
};

const els = {
  refresh: document.querySelector("#errors-refresh-button"),
  serviceStatus: document.querySelector("#error-service-status"),
  serviceStatusText: document.querySelector("#error-service-status-text"),
  grid: document.querySelector("#error-gallery-grid"),
  count: document.querySelector("#gallery-count"),
  prev: document.querySelector("#prev-page-button"),
  next: document.querySelector("#next-page-button"),
  typeTabs: document.querySelector("#error-type-tabs"),
  scenario: document.querySelector("#filter-scenario"),
  format: document.querySelector("#filter-format"),
  resolution: document.querySelector("#filter-resolution"),
  sourceFolder: document.querySelector("#filter-source-folder"),
  sort: document.querySelector("#filter-sort"),
  drawer: document.querySelector("#detail-drawer"),
  drawerBody: document.querySelector("#drawer-body"),
  drawerTitle: document.querySelector("#drawer-title"),
  drawerClose: document.querySelector("#drawer-close-button"),
  drawerBackdrop: document.querySelector("#drawer-backdrop"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getNested(source, path, fallback = undefined) {
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

function formatInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.round(number)).toLocaleString() : "--";
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return `${Math.round(Math.max(0, Math.min(1, number)) * 100)}%`;
}

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3).replace(/0+$/, "").replace(/\.$/, "") : "--";
}

function labelText(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function badgeClass(value) {
  return String(value || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function setServiceStatus(status, label) {
  els.serviceStatus.dataset.status = status;
  els.serviceStatusText.textContent = label;
}

async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    throw new Error(`网络请求失败：${error.message || "无法连接 API"}`);
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText || "API error"}`);
      }
      throw new Error("API 返回了非 JSON 数据。");
    }
  }

  if (!response.ok) {
    const detail = getNested(payload, "detail", getNested(payload, "error.message", response.statusText));
    throw new Error(`${response.status} ${detail || "API error"}`);
  }
  return payload || {};
}

function setSummaryValue(key, value) {
  const node = document.querySelector(`[data-error-summary-key="${key}"]`);
  if (node) {
    node.textContent = value;
  }
}

function resetSummary() {
  ["totalSamples", "fp", "fn", "uncertain", "errorRate", "reviewed"].forEach((key) => {
    setSummaryValue(key, "--");
  });
}

function fillSelect(select, groups, allLabel = "All") {
  const entries = Object.entries(groups || {});
  select.innerHTML = `<option value="">${escapeHtml(allLabel)}</option>${entries
    .map(([key, stats]) => {
      const total = stats && typeof stats === "object" ? stats.total : null;
      const label = total ? `${key} (${formatInteger(total)})` : key;
      return `<option value="${escapeHtml(key)}">${escapeHtml(label)}</option>`;
    })
    .join("")}`;
}

function renderSummary(summary) {
  setSummaryValue("totalSamples", formatInteger(summary.total_samples));
  setSummaryValue("fp", formatInteger(summary.fp_count));
  setSummaryValue("fn", formatInteger(summary.fn_count));
  setSummaryValue("uncertain", formatInteger(summary.uncertain_count));
  setSummaryValue("errorRate", formatPercent(summary.error_rate));
  setSummaryValue("reviewed", formatInteger(summary.reviewed_count));
  fillSelect(els.scenario, summary.by_scenario);
  fillSelect(els.format, summary.by_format);
  fillSelect(els.resolution, summary.by_resolution_bucket);
  fillSelect(els.sourceFolder, summary.by_source_folder);
}

function queryString() {
  const params = new URLSearchParams();
  params.set("type", state.type);
  params.set("limit", String(state.limit));
  params.set("offset", String(state.offset));
  params.set("sort", state.sort);
  if (state.scenario) params.set("scenario", state.scenario);
  if (state.format) params.set("format", state.format);
  if (state.resolutionBucket) params.set("resolution_bucket", state.resolutionBucket);
  if (state.sourceFolder) params.set("source_folder", state.sourceFolder);
  return params.toString();
}

function imageMarkup(item, className = "gallery-thumb") {
  if (!item.image_url) {
    return `<div class="${className} image-missing">No preview</div>`;
  }
  return `
    <img
      class="${className}"
      src="${escapeHtml(item.image_url)}"
      alt="${escapeHtml(item.filename)}"
      loading="lazy"
      onerror="this.replaceWith(Object.assign(document.createElement('div'), {className: '${className} image-missing', textContent: 'Image unavailable'}));"
    />
  `;
}

function renderLoading() {
  els.count.textContent = "正在加载样本...";
  els.grid.innerHTML = `<div class="loading-state gallery-empty">正在加载样本...</div>`;
  els.prev.disabled = true;
  els.next.disabled = true;
}

function renderError(message) {
  els.count.textContent = "加载失败";
  els.grid.innerHTML = `
    <div class="error-state gallery-empty">
      错误图库数据加载失败，请检查 /api/v1/errors 接口。<br />
      <span>${escapeHtml(message)}</span>
    </div>
  `;
  els.prev.disabled = true;
  els.next.disabled = true;
}

function renderEmpty() {
  els.count.textContent = "0 samples";
  els.grid.innerHTML = `<div class="empty-state gallery-empty">当前筛选条件下没有样本。</div>`;
  els.prev.disabled = true;
  els.next.disabled = true;
}

function renderGallery(payload) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  state.total = Number(payload.total || 0);
  const start = state.total ? state.offset + 1 : 0;
  const end = Math.min(state.offset + state.limit, state.total);
  els.count.textContent = `${formatInteger(start)}-${formatInteger(end)} of ${formatInteger(state.total)} samples`;
  els.prev.disabled = state.offset <= 0;
  els.next.disabled = state.offset + state.limit >= state.total;

  if (!items.length) {
    renderEmpty();
    return;
  }

  els.grid.innerHTML = items
    .map((item) => {
      const reviewed = getNested(item, "review.reviewed", false);
      return `
        <button class="error-card" type="button" data-id="${escapeHtml(item.id)}">
          <div class="thumb-shell">
            ${imageMarkup(item)}
            <span class="error-badge ${badgeClass(item.error_type)}">${escapeHtml(item.error_type)}</span>
          </div>
          <div class="error-card-body">
            <div class="label-flow">
              <span>${escapeHtml(labelText(item.true_label))}</span>
              <strong>→</strong>
              <span>${escapeHtml(labelText(item.final_label || item.predicted_label))}</span>
            </div>
            <div class="metric-strip">
              <span>Confidence ${escapeHtml(formatPercent(item.confidence))}</span>
              <span>Score ${escapeHtml(formatNumber(item.score))}</span>
            </div>
            <div class="meta-strip">
              <span>${escapeHtml(item.scenario || "unknown")}</span>
              <span>${escapeHtml(item.format || item.ext || "unknown")} / ${escapeHtml(item.resolution_bucket || "unknown")}</span>
            </div>
            <div class="filename-line" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</div>
            ${reviewed ? `<span class="review-chip">Reviewed</span>` : ""}
          </div>
        </button>
      `;
    })
    .join("");
}

function stringifyBlock(value) {
  if (value === null || value === undefined || value === "") {
    return "None";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function renderDrawer(item) {
  state.currentItem = item;
  els.drawerTitle.textContent = item.filename || "Sample";
  const review = item.review || {};
  const manualTag = review.manual_tag || "";
  els.drawerBody.innerHTML = `
    <div class="drawer-image-shell">
      ${imageMarkup(item, "drawer-image")}
    </div>
    <div class="detail-meta-grid">
      <div><span>Filename</span><strong title="${escapeHtml(item.filename)}">${escapeHtml(item.filename || "unknown")}</strong></div>
      <div><span>Error type</span><strong>${escapeHtml(item.error_type || "unknown")}</strong></div>
      <div><span>True label</span><strong>${escapeHtml(labelText(item.true_label))}</strong></div>
      <div><span>Final label</span><strong>${escapeHtml(labelText(item.final_label || item.predicted_label))}</strong></div>
      <div><span>Confidence</span><strong>${escapeHtml(formatPercent(item.confidence))}</strong></div>
      <div><span>Score</span><strong>${escapeHtml(formatNumber(item.score))}</strong></div>
      <div><span>Scenario</span><strong>${escapeHtml(item.scenario || "unknown")}</strong></div>
      <div><span>Format</span><strong>${escapeHtml(item.format || item.ext || "unknown")}</strong></div>
    </div>
    <div class="path-block" title="${escapeHtml(item.file_path || "")}">${escapeHtml(item.file_path || "unknown path")}</div>

    <section class="detail-section">
      <h3>Decision Reason</h3>
      <pre>${escapeHtml(stringifyBlock(item.decision_reason))}</pre>
    </section>
    <section class="detail-section">
      <h3>Recommendation</h3>
      <pre>${escapeHtml(stringifyBlock(item.recommendation))}</pre>
    </section>
    <section class="detail-section">
      <h3>Technical Explanation</h3>
      <pre>${escapeHtml(stringifyBlock(item.technical_explanation))}</pre>
    </section>
    <section class="detail-section">
      <h3>Debug Evidence</h3>
      <pre>${escapeHtml(stringifyBlock(item.debug_evidence))}</pre>
    </section>

    <form class="review-form" id="review-form">
      <div class="review-row">
        <label class="checkbox-label">
          <input id="reviewed-input" type="checkbox" ${review.reviewed ? "checked" : ""} />
          <span>Reviewed</span>
        </label>
        <span class="review-status">${review.updated_at ? `Saved ${escapeHtml(review.updated_at)}` : "Not reviewed"}</span>
      </div>
      <label>
        <span>Manual tag</span>
        <select id="manual-tag-input">
          <option value="">No tag</option>
          ${["format_bias", "resolution_flip", "no_exif_jpeg", "low_texture", "high_compression", "realistic_ai", "unknown"]
            .map((tag) => `<option value="${tag}" ${manualTag === tag ? "selected" : ""}>${tag}</option>`)
            .join("")}
        </select>
      </label>
      <label>
        <span>Reviewer note</span>
        <textarea id="reviewer-note-input" rows="4">${escapeHtml(review.reviewer_note || "")}</textarea>
      </label>
      <button class="button button-primary button-full" id="save-review-button" type="submit">保存审查</button>
      <div class="form-message" id="review-form-message"></div>
    </form>
  `;
  document.querySelector("#review-form").addEventListener("submit", saveReview);
}

async function loadSummary() {
  try {
    const summary = await fetchJson(ERROR_ENDPOINTS.summary);
    renderSummary(summary);
    setServiceStatus("online", "在线");
    return true;
  } catch (error) {
    resetSummary();
    setServiceStatus("offline", "API 错误");
    return false;
  }
}

async function loadGallery() {
  renderLoading();
  try {
    const payload = await fetchJson(`${ERROR_ENDPOINTS.list}?${queryString()}`);
    renderGallery(payload);
    setServiceStatus("online", "在线");
  } catch (error) {
    renderError(error.message || "unknown error");
    setServiceStatus("offline", "API 错误");
  }
}

async function refreshAll() {
  els.refresh.disabled = true;
  els.refresh.textContent = "刷新中";
  await Promise.allSettled([loadSummary(), loadGallery()]);
  els.refresh.disabled = false;
  els.refresh.textContent = "刷新";
}

async function openDrawer(id) {
  els.drawer.setAttribute("aria-hidden", "false");
  els.drawerBody.innerHTML = `<div class="loading-state compact">正在加载样本详情...</div>`;
  try {
    const item = await fetchJson(ERROR_ENDPOINTS.detail(id));
    renderDrawer(item);
  } catch (error) {
    els.drawerBody.innerHTML = `<div class="error-state compact">样本详情加载失败：${escapeHtml(error.message)}</div>`;
  }
}

function closeDrawer() {
  els.drawer.setAttribute("aria-hidden", "true");
  state.currentItem = null;
}

async function saveReview(event) {
  event.preventDefault();
  if (!state.currentItem) {
    return;
  }
  const button = document.querySelector("#save-review-button");
  const message = document.querySelector("#review-form-message");
  button.disabled = true;
  button.textContent = "保存中";
  message.dataset.status = "loading";
  message.textContent = "正在保存...";
  const payload = {
    reviewed: document.querySelector("#reviewed-input").checked,
    manual_tag: document.querySelector("#manual-tag-input").value || null,
    reviewer_note: document.querySelector("#reviewer-note-input").value,
    reviewer: "local",
  };
  try {
    const result = await fetchJson(ERROR_ENDPOINTS.review(state.currentItem.id), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.currentItem.review = result.review;
    message.dataset.status = "success";
    message.textContent = "保存成功。";
    await Promise.allSettled([loadSummary(), loadGallery()]);
  } catch (error) {
    message.dataset.status = "error";
    message.textContent = `保存失败：${error.message || "unknown error"}`;
  } finally {
    button.disabled = false;
    button.textContent = "保存审查";
  }
}

els.typeTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-type]");
  if (!button) {
    return;
  }
  state.type = button.dataset.type;
  state.offset = 0;
  document.querySelectorAll(".type-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
  loadGallery();
});

[
  [els.scenario, "scenario"],
  [els.format, "format"],
  [els.resolution, "resolutionBucket"],
  [els.sourceFolder, "sourceFolder"],
  [els.sort, "sort"],
].forEach(([select, key]) => {
  select.addEventListener("change", () => {
    state[key] = select.value;
    state.offset = 0;
    loadGallery();
  });
});

els.grid.addEventListener("click", (event) => {
  const card = event.target.closest(".error-card");
  if (card) {
    openDrawer(card.dataset.id);
  }
});

els.prev.addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadGallery();
});

els.next.addEventListener("click", () => {
  state.offset += state.limit;
  loadGallery();
});

els.refresh.addEventListener("click", refreshAll);
els.drawerClose.addEventListener("click", closeDrawer);
els.drawerBackdrop.addEventListener("click", closeDrawer);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeDrawer();
  }
});

window.addEventListener("DOMContentLoaded", refreshAll);
