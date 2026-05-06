(function () {
  const DETAIL_ENDPOINT_PREFIX = "/history/";
  const FALLBACK_TECHNICAL =
    "This result was produced by the current decision layer using available image-level signals, score distribution, and uncertainty rules.";

  const state = {
    record: null,
    lastTrigger: null,
    copyTimer: 0,
    reportTimer: 0,
  };

  const labels = {
    ai: "AI Generated",
    real: "Likely Real",
    uncertain: "Uncertain",
  };

  function firstDefined(...values) {
    return values.find((value) => value !== undefined && value !== null && value !== "");
  }

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

  function textFromValue(value, fallback = "N/A") {
    if (Array.isArray(value)) {
      return value.map((item) => textFromValue(item, "")).filter(Boolean).join("; ") || fallback;
    }
    if (value && typeof value === "object") {
      return firstDefined(value.message, value.action, value.summary, value.explanation, value.code, JSON.stringify(value), fallback);
    }
    return String(firstDefined(value, fallback));
  }

  function normalizeLabelKey(value) {
    const label = String(value || "").trim().toLowerCase();
    if (["ai", "ai_generated", "likely_ai", "generated", "synthetic", "artificial"].includes(label)) return "ai";
    if (["real", "real_photo", "likely_real", "authentic", "photo", "camera"].includes(label)) return "real";
    if (["uncertain", "unsure", "unknown", "review"].includes(label)) return "uncertain";
    return label || "uncertain";
  }

  function displayFinalLabel(value) {
    const key = normalizeLabelKey(value);
    return labels[key] || key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function normalizeConfidence(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    const normalized = number > 1 && number <= 100 ? number / 100 : number;
    return Math.max(0, Math.min(1, normalized));
  }

  function formatConfidence(value) {
    const normalized = normalizeConfidence(value);
    return normalized === null ? "N/A" : `${Math.round(normalized * 100)}%`;
  }

  function fallbackRisk(label, confidence) {
    const key = normalizeLabelKey(label);
    const normalized = normalizeConfidence(confidence);
    if (key === "ai") return normalized !== null && normalized >= 0.8 ? "HIGH" : "MEDIUM";
    if (key === "real") return "LOW";
    return "MEDIUM";
  }

  function normalizeRisk(value, label, confidence) {
    const risk = String(value || "").trim().toUpperCase();
    if (["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(risk)) return risk;
    return fallbackRisk(label, confidence);
  }

  function normalizeDetectionRecord(record) {
    const raw = record && typeof record === "object" ? record : {};
    const result = getValue(raw, "data.result", getValue(raw, "response.data.result", raw));
    const image = getValue(raw, "data.image", getValue(raw, "response.data.image", {}));
    const id = firstDefined(
      result.id,
      result.record_id,
      result.detection_id,
      raw.id,
      raw.record_id,
      raw.detection_id,
      raw.history_file,
      `${firstDefined(result.filename, raw.filename, "record")}-${firstDefined(result.timestamp, raw.timestamp, Date.now())}`,
    );
    const filename = firstDefined(result.filename, raw.filename, raw.original_filename, raw.image_name, raw.file_name, image.filename, "unknown");
    const createdAt = firstDefined(result.created_at, result.timestamp, result.detected_at, raw.created_at, raw.timestamp, raw.detected_at);
    const finalLabel = firstDefined(result.final_label, result.label, result.decision, result.result, raw.final_label, raw.label, raw.decision, raw.result);
    const confidence = firstDefined(result.confidence, result.confidence_score, result.score, raw.confidence, raw.confidence_score, raw.score);
    const riskLevel = normalizeRisk(firstDefined(result.risk_level, result.risk, result.severity, raw.risk_level, raw.risk, raw.severity), finalLabel, confidence);
    const summary = firstDefined(result.user_facing_summary, result.summary, raw.user_facing_summary, raw.summary);
    const reason = firstDefined(result.decision_reason, result.reason, raw.decision_reason, raw.reason);
    const recommendation = firstDefined(result.recommendation, result.next_step, raw.recommendation, raw.next_step);
    const technical = firstDefined(result.technical_explanation, result.explanation, raw.technical_explanation, raw.explanation, FALLBACK_TECHNICAL);
    return {
      id: String(id),
      filename: String(filename || "unknown"),
      created_at: createdAt || "",
      image_url: firstDefined(result.image_url, result.preview_url, result.thumbnail_url, result.file_url, raw.image_url, raw.preview_url, raw.thumbnail_url, raw.file_url),
      final_label: finalLabel || "uncertain",
      risk_level: riskLevel,
      confidence,
      decision_reason: textFromValue(reason, "No decision reason was stored for this record."),
      recommendation: textFromValue(recommendation, "Review this result alongside the original source context before taking action."),
      user_facing_summary: textFromValue(summary, "No user-facing summary was stored for this record."),
      technical_explanation: textFromValue(technical, FALLBACK_TECHNICAL),
      debug_evidence: firstDefined(result.debug_evidence, result.evidence, result.signals, result.debug, raw.debug_evidence, raw.evidence, raw.signals, raw.debug),
      raw,
    };
  }

  function evidenceItems(value) {
    if (!value) return [];
    if (typeof value === "string") return [{ title: "Evidence", value }];
    if (Array.isArray(value)) {
      return value.map((item, index) => {
        if (item && typeof item === "object") {
          return {
            title: firstDefined(item.title, item.name, item.key, `Evidence ${index + 1}`),
            value: firstDefined(item.value, item.score, item.status, item.result, ""),
            weight: firstDefined(item.weight, item.contribution, item.confidence, ""),
            explanation: firstDefined(item.explanation, item.reason, item.summary, ""),
          };
        }
        return { title: `Evidence ${index + 1}`, value: item };
      });
    }
    if (typeof value === "object") {
      return Object.entries(value).map(([key, item]) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          return {
            title: firstDefined(item.title, item.name, key),
            value: firstDefined(item.value, item.score, item.status, item.result, JSON.stringify(item)),
            weight: firstDefined(item.weight, item.contribution, item.confidence, ""),
            explanation: firstDefined(item.explanation, item.reason, item.summary, ""),
          };
        }
        return { title: key, value: item };
      });
    }
    return [];
  }

  function renderEvidence(value) {
    const items = evidenceItems(value);
    if (!items.length) {
      return `<p class="detail-muted">No detailed evidence available for this record.</p>`;
    }
    return `
      <div class="detail-evidence-list">
        ${items
          .map(
            (item) => `
              <div class="detail-evidence-item">
                <div>
                  <strong>${escapeHtml(item.title)}</strong>
                  <span>${escapeHtml(textFromValue(item.value, "Available"))}</span>
                </div>
                ${item.weight ? `<em>${escapeHtml(textFromValue(item.weight, ""))}</em>` : ""}
                ${item.explanation ? `<p>${escapeHtml(textFromValue(item.explanation, ""))}</p>` : ""}
              </div>
            `,
          )
          .join("")}
      </div>
    `;
  }

  function jsonFor(record) {
    return JSON.stringify(record?.raw || record || {}, null, 2);
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // Fall through to the textarea fallback.
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.append(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    textarea.remove();
    if (!ok) throw new Error("Clipboard copy failed");
    return true;
  }

  function safeReportFilename(record) {
    return `detection-report-${slug(record?.id || Date.now()) || Date.now()}.html`;
  }

  function renderReportEvidence(record) {
    const items = evidenceItems(record.debug_evidence);
    if (!items.length) return `<p>No detailed evidence available for this record.</p>`;
    return `
      <ul class="evidence">
        ${items
          .map(
            (item) => `
              <li>
                <strong>${escapeHtml(item.title)}</strong>
                <span>${escapeHtml(textFromValue(item.value, "Available"))}</span>
                ${item.weight ? `<em>${escapeHtml(textFromValue(item.weight, ""))}</em>` : ""}
                ${item.explanation ? `<p>${escapeHtml(textFromValue(item.explanation, ""))}</p>` : ""}
              </li>
            `,
          )
          .join("")}
      </ul>
    `;
  }

  function generateDetectionReportHtml(input) {
    const record = normalizeDetectionRecord(input);
    const confidence = formatConfidence(record.confidence);
    const label = displayFinalLabel(record.final_label);
    const json = jsonFor(record);
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Image Trust Scanner - Detection Report</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f7fb; color: #102033; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.55; }
    main { width: min(980px, calc(100% - 40px)); margin: 34px auto; }
    header, section, footer { border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; padding: 22px; margin-bottom: 16px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06); }
    h1, h2, p { margin-top: 0; } h1 { font-size: 28px; margin-bottom: 6px; } h2 { font-size: 15px; letter-spacing: .04em; text-transform: uppercase; color: #475569; }
    .meta, .verdict { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .cell { border-top: 1px solid #e6edf5; padding-top: 10px; } .cell span { display: block; color: #64748b; font-size: 11px; font-weight: 800; text-transform: uppercase; } .cell strong { display: block; margin-top: 4px; overflow-wrap: anywhere; }
    .badge { display: inline-flex; border: 1px solid #bfd5ef; border-radius: 999px; background: #e8f0ff; color: #1d4ed8; padding: 3px 10px; font-size: 12px; font-weight: 800; }
    .image { display: grid; min-height: 220px; place-items: center; border: 1px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; color: #64748b; }
    .image img { max-width: 100%; max-height: 420px; object-fit: contain; border-radius: 8px; }
    .evidence { list-style: none; padding: 0; margin: 0; } .evidence li { border-left: 2px solid #d8a24a; padding: 0 0 12px 14px; margin-bottom: 12px; } .evidence span, .evidence em { display: block; color: #475569; font-style: normal; overflow-wrap: anywhere; }
    pre { overflow: auto; max-height: 520px; border-radius: 10px; background: #f1f5f9; padding: 14px; color: #0f172a; font-size: 12px; }
    footer { color: #64748b; font-size: 12px; text-align: center; }
    @media print { body { background: #fff; } main { width: 100%; margin: 0; } header, section, footer { box-shadow: none; page-break-inside: avoid; } }
    @media (max-width: 680px) { main { width: calc(100% - 24px); } .meta, .verdict { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Detection Report</h1>
      <p>Generated locally by AI Image Trust Scanner</p>
      <div class="meta">
        <div class="cell"><span>Record ID</span><strong>${escapeHtml(record.id)}</strong></div>
        <div class="cell"><span>Filename</span><strong>${escapeHtml(record.filename)}</strong></div>
        <div class="cell"><span>Detection Time</span><strong>${escapeHtml(record.created_at || "N/A")}</strong></div>
      </div>
    </header>
    <section>
      <h2>Conclusion</h2>
      <div class="verdict">
        <div class="cell"><span>Final Label</span><strong>${escapeHtml(label)}</strong></div>
        <div class="cell"><span>Risk Level</span><strong><span class="badge">${escapeHtml(record.risk_level)}</span></strong></div>
        <div class="cell"><span>Confidence</span><strong>${escapeHtml(confidence)}</strong></div>
      </div>
    </section>
    <section><h2>Image</h2><div class="image">${record.image_url ? `<img src="${escapeHtml(record.image_url)}" alt="${escapeHtml(record.filename)}">` : "Image preview unavailable"}</div></section>
    <section><h2>User Summary</h2><p>${escapeHtml(record.user_facing_summary)}</p></section>
    <section><h2>Decision Reason</h2><p>${escapeHtml(record.decision_reason)}</p></section>
    <section><h2>Recommendation</h2><p>${escapeHtml(record.recommendation)}</p></section>
    <section><h2>Evidence Chain</h2>${renderReportEvidence(record)}</section>
    <section><h2>Technical Explanation</h2><p>${escapeHtml(record.technical_explanation)}</p></section>
    <section><h2>Raw JSON</h2><pre>${escapeHtml(json)}</pre></section>
    <footer>Generated by AI Image Trust Scanner · PDF export coming soon</footer>
  </main>
</body>
</html>`;
  }

  function openHtmlPreview(record) {
    const blob = new Blob([generateDetectionReportHtml(record)], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    return Boolean(opened);
  }

  function downloadHtml(record) {
    const blob = new Blob([generateDetectionReportHtml(record)], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = safeReportFilename(normalizeDetectionRecord(record));
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function detailShell() {
    let shell = document.querySelector("#detection-detail-shell");
    if (shell) return shell;
    shell = document.createElement("div");
    shell.id = "detection-detail-shell";
    shell.className = "detail-shell";
    shell.hidden = true;
    shell.innerHTML = `
      <div class="detail-backdrop" data-detail-close></div>
      <aside class="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <div class="detail-content"></div>
      </aside>
    `;
    document.body.append(shell);
    shell.addEventListener("click", onShellClick);
    return shell;
  }

  function renderDrawer(record, options = {}) {
    const shell = detailShell();
    const drawer = shell.querySelector(".detail-content");
    const normalized = normalizeDetectionRecord(record);
    state.record = normalized;
    const confidence = normalizeConfidence(normalized.confidence);
    const confidenceText = formatConfidence(normalized.confidence);
    const image = normalized.image_url
      ? `<img class="detail-image" src="${escapeHtml(normalized.image_url)}" alt="${escapeHtml(normalized.filename)}">`
      : `<div class="detail-image-placeholder">Image preview unavailable</div>`;
    drawer.innerHTML = `
      <header class="detail-header">
        <div>
          <p class="eyebrow">Audit record / Detection result</p>
          <h2 id="detail-title">Detection Detail</h2>
        </div>
        <button class="detail-close" type="button" data-detail-close aria-label="Close detail">×</button>
      </header>
      <section class="detail-verdict">
        <div>
          <span>Final Label</span>
          <strong>${escapeHtml(displayFinalLabel(normalized.final_label))}</strong>
        </div>
        <span class="badge ${slug(normalized.risk_level)}">${escapeHtml(normalized.risk_level)}</span>
      </section>
      <div class="detail-confidence">
        <span>Confidence</span>
        <strong>${escapeHtml(confidenceText)}</strong>
        <i style="--confidence:${confidence === null ? 0 : confidence}"></i>
      </div>
      <section class="detail-image-frame">${image}</section>
      <section class="detail-meta-grid">
        <div><span>Filename</span><strong>${escapeHtml(normalized.filename)}</strong></div>
        <div><span>Detection Time</span><strong>${escapeHtml(normalized.created_at || "N/A")}</strong></div>
        <div><span>Record ID</span><strong>${escapeHtml(normalized.id)}</strong></div>
      </section>
      <section class="detail-section">
        <h3>User Summary</h3>
        <p>${escapeHtml(normalized.user_facing_summary)}</p>
      </section>
      <section class="detail-section">
        <h3>Decision Reason</h3>
        <p>${escapeHtml(normalized.decision_reason)}</p>
      </section>
      <section class="detail-section">
        <h3>Recommendation</h3>
        <p>${escapeHtml(normalized.recommendation)}</p>
      </section>
      <section class="detail-section">
        <h3>Evidence Chain</h3>
        ${renderEvidence(normalized.debug_evidence)}
      </section>
      <section class="detail-section">
        <h3>Technical Explanation</h3>
        <p>${escapeHtml(normalized.technical_explanation)}</p>
      </section>
      <details class="detail-json">
        <summary>Raw JSON</summary>
        <pre>${escapeHtml(jsonFor(normalized))}</pre>
      </details>
      <section class="detail-actions" data-report-actions>
        <button class="button button-secondary" type="button" data-detail-action="copy-json">Copy JSON</button>
        <button class="button button-ghost" type="button" data-detail-action="preview-html">Preview HTML Report</button>
        <button class="button button-ghost" type="button" data-detail-action="download-html">Download HTML</button>
        <button class="button button-ghost" type="button" disabled>PDF Coming Soon</button>
        <p class="detail-feedback" aria-live="polite"></p>
      </section>
    `;
    shell.hidden = false;
    requestAnimationFrame(() => shell.classList.add("open"));
    document.body.classList.add("detail-drawer-open");
    shell.querySelector(".detail-close")?.focus({ preventScroll: true });
    shell.querySelector(".detail-image")?.addEventListener("error", (event) => {
      event.currentTarget.replaceWith(Object.assign(document.createElement("div"), { className: "detail-image-placeholder", textContent: "Image preview unavailable" }));
    });
    if (options.focusReport) {
      window.setTimeout(() => shell.querySelector("[data-report-actions]")?.scrollIntoView({ behavior: "smooth", block: "center" }), 180);
    }
  }

  function setFeedback(message, isError = false) {
    const node = document.querySelector(".detail-feedback");
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("error", isError);
    window.clearTimeout(state.reportTimer);
    state.reportTimer = window.setTimeout(() => {
      node.textContent = "";
      node.classList.remove("error");
    }, 2600);
  }

  function closeDrawer() {
    const shell = document.querySelector("#detection-detail-shell");
    if (!shell || shell.hidden) return;
    shell.classList.remove("open");
    document.body.classList.remove("detail-drawer-open");
    window.setTimeout(() => {
      shell.hidden = true;
      state.lastTrigger?.focus?.({ preventScroll: true });
    }, 220);
  }

  async function onShellClick(event) {
    const close = event.target.closest("[data-detail-close]");
    if (close) {
      closeDrawer();
      return;
    }
    const button = event.target.closest("[data-detail-action]");
    if (!button || !state.record) return;
    try {
      if (button.dataset.detailAction === "copy-json") {
        await copyText(jsonFor(state.record));
        const original = button.textContent;
        button.textContent = "Copied";
        window.clearTimeout(state.copyTimer);
        state.copyTimer = window.setTimeout(() => {
          button.textContent = original || "Copy JSON";
        }, 1500);
        setFeedback("JSON copied.");
      }
      if (button.dataset.detailAction === "preview-html") {
        const opened = openHtmlPreview(state.record);
        setFeedback(opened ? "HTML report opened." : "Preview was blocked. Use Download HTML instead.", !opened);
      }
      if (button.dataset.detailAction === "download-html") {
        downloadHtml(state.record);
        setFeedback("HTML report downloaded.");
      }
    } catch (error) {
      setFeedback(error?.message || "Report action failed.", true);
    }
  }

  function extractRecordFromHistory(summary, history) {
    const response = history?.response && typeof history.response === "object" ? history.response : {};
    const requestedId = String(firstDefined(summary?.id, ""));
    if (history?.history_type === "batch" || response.mode === "batch") {
      const results = Array.isArray(response.results) ? response.results : [];
      const stem = String(summary?.history_file || "").replace(/\.json$/i, "");
      const matched = results.find((item, index) => {
        const result = item?.result || {};
        const candidateId = String(firstDefined(result.id, result.request_id, `${stem}_${index}`));
        const inputName = item?.input?.filename;
        return candidateId === requestedId || String(result.filename || inputName || "") === String(summary?.filename || "");
      });
      if (matched?.result) {
        return { ...matched.result, filename: firstDefined(matched.result.filename, matched.input?.filename, summary?.filename), raw: matched };
      }
      return summary;
    }
    const data = response.data;
    if (data?.result) {
      return { ...data.result, filename: firstDefined(data.result.filename, data.image?.filename, summary?.filename), raw: history };
    }
    return data && typeof data === "object" ? { ...data, raw: history } : { ...summary, raw: history };
  }

  async function hydrateHistory(summary, options) {
    if (!summary?.history_file) return;
    try {
      const history = await fetch(`${DETAIL_ENDPOINT_PREFIX}${encodeURIComponent(summary.history_file)}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      }).then((response) => {
        if (!response.ok) throw new Error(`Detail fetch failed: ${response.status}`);
        return response.json();
      });
      const detailed = extractRecordFromHistory(summary, history);
      renderDrawer({ ...summary, ...detailed, raw: detailed.raw || history }, options);
    } catch (error) {
      setFeedback(error?.message || "Could not load full history detail.", true);
    }
  }

  function open(summary, options = {}) {
    state.lastTrigger = options.trigger || document.activeElement;
    renderDrawer(summary || {}, options);
    hydrateHistory(summary, options);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });

  window.DetectionDetails = {
    open,
    close: closeDrawer,
    normalizeDetectionRecord,
    generateDetectionReportHtml,
    copyJson: (record) => copyText(JSON.stringify(record?.raw || record || {}, null, 2)),
    previewHtml: openHtmlPreview,
    downloadHtml,
  };
})();
