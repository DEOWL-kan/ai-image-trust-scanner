(function () {
  const DETAIL_ENDPOINT_PREFIX = "/history/";
  const REVIEW_ENDPOINT_PREFIX = "/api/v1/reports/";
  const REPORT_ENDPOINT_PREFIX = "/api/v1/reports/";
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

  const ui = {
    zh: {
      title: "检测详情",
      eyebrow: "审计记录 / 检测结果",
      close: "关闭详情",
      finalLabel: "检测结论",
      confidence: "置信度",
      filename: "文件名",
      detectionTime: "检测时间",
      recordId: "记录 ID",
      userSummary: "用户摘要",
      decisionReason: "判断依据",
      recommendation: "复核建议",
      evidenceChain: "证据链",
      technical: "技术解释",
      rawJson: "原始 JSON",
      reviewActions: "复核操作",
      notReviewed: "尚未复核",
      savedAt: "已保存 {time}",
      reviewed: "标记已复核",
      confirmedAi: "确认为 AI",
      confirmedReal: "确认为真实",
      falsePositive: "标记误判为 AI",
      falseNegative: "标记漏判 AI",
      needsFollowUp: "需要跟进",
      ignored: "忽略",
      addNote: "添加复核备注",
      notePlaceholder: "补充复核背景、判断理由或后续处理事项。",
      saveNote: "保存复核备注",
      copyJson: "复制 JSON",
      previewHtml: "查看 HTML 报告",
      downloadHtml: "下载 HTML",
      pdfSoon: "PDF 暂不支持",
      copied: "JSON 已复制。",
      htmlOpened: "HTML 报告已打开。",
      htmlBlocked: "浏览器阻止了报告预览，请检查弹窗设置。",
      htmlDownloaded: "HTML 报告已下载。",
      reviewSaved: "复核状态已保存。",
      reviewFailed: "复核状态保存失败。",
      noEvidence: "暂无可用的详细证据。",
      imageUnavailable: "图片预览不可用",
      fallbackNotice: "没有可用检测记录，正在显示安全兜底信息。",
      missingRecord: "缺少记录 ID，无法保存复核状态。",
      detailLoadFailed: "无法加载报告详情。",
    },
    en: {
      title: "Detection Detail",
      eyebrow: "Audit record / Detection result",
      close: "Close detail",
      finalLabel: "Final Label",
      confidence: "Confidence",
      filename: "Filename",
      detectionTime: "Detection Time",
      recordId: "Record ID",
      userSummary: "User Summary",
      decisionReason: "Decision Reason",
      recommendation: "Recommendation",
      evidenceChain: "Evidence Chain",
      technical: "Technical Explanation",
      rawJson: "Raw JSON",
      reviewActions: "Review Actions",
      notReviewed: "Not reviewed yet",
      savedAt: "Saved {time}",
      reviewed: "Mark as Reviewed",
      confirmedAi: "Confirm AI",
      confirmedReal: "Confirm Real",
      falsePositive: "Mark False Positive",
      falseNegative: "Mark False Negative",
      needsFollowUp: "Needs Follow-up",
      ignored: "Ignore",
      addNote: "Add Review Note",
      notePlaceholder: "Add reviewer context, decision rationale, or follow-up needs.",
      saveNote: "Save Review Note",
      copyJson: "Copy JSON",
      previewHtml: "Preview HTML Report",
      downloadHtml: "Download HTML",
      pdfSoon: "PDF unavailable",
      copied: "JSON copied.",
      htmlOpened: "HTML report opened.",
      htmlBlocked: "The browser blocked the report preview.",
      htmlDownloaded: "HTML report downloaded.",
      reviewSaved: "Review saved.",
      reviewFailed: "Review save failed.",
      noEvidence: "No detailed evidence available for this record.",
      imageUnavailable: "Image preview unavailable",
      fallbackNotice: "No detection record was provided. Showing safe fallback values.",
      missingRecord: "Missing record id; review cannot be saved.",
      detailLoadFailed: "Could not load report detail.",
    },
  };

  function tr(key, params = {}) {
    const lang = document.documentElement.lang?.toLowerCase().startsWith("zh") ? "zh" : "en";
    const value = ui[lang]?.[key] || ui.en[key] || key;
    return Object.entries(params).reduce((text, [name, replacement]) => text.replaceAll(`{${name}}`, replacement), value);
  }

  Object.assign(ui.zh, {
    title: "检测详情",
    eyebrow: "审计记录 / 检测结果",
    close: "关闭详情",
    finalLabel: "检测结论",
    confidence: "置信度",
    filename: "文件名",
    detectionTime: "检测时间",
    recordId: "记录 ID",
    userSummary: "检测摘要",
    reportInfo: "报告信息",
    decisionReason: "判断依据",
    recommendation: "复核建议",
    evidenceChain: "证据链",
    technical: "技术解释",
    rawJson: "原始 JSON",
    reviewActions: "复核操作",
    notReviewed: "尚未复核",
    reviewed: "标记已复核",
    confirmedAi: "确认是 AI",
    confirmedReal: "确认为真实",
    falsePositive: "标记误判",
    falseNegative: "标记漏判",
    needsFollowUp: "需要跟进",
    ignored: "忽略",
    addNote: "复核备注",
    notePlaceholder: "补充复核背景、判断理由或后续处理事项。",
    saveNote: "保存复核备注",
    copyJson: "复制 JSON",
    previewHtml: "查看 HTML 报告",
    downloadHtml: "下载 HTML",
    pdfSoon: "PDF 暂不支持",
    noEvidence: "暂无可用的详细证据。",
    imageUnavailable: "图片预览不可用",
    likelyAi: "可能 AI",
    likelyReal: "可能真实",
    uncertain: "不确定",
    lowRisk: "低",
    mediumRisk: "中",
    highRisk: "高",
    criticalRisk: "高",
    pendingReview: "未复核",
    reviewedStatus: "已复核",
    confirmedAiStatus: "已确认 AI",
    confirmedRealStatus: "已确认真实",
    falsePositiveStatus: "标记误判",
    falseNegativeStatus: "标记漏判",
    needsFollowUpStatus: "需要跟进",
    ignoredStatus: "已忽略",
    enabled: "证据链已启用",
    raw_score: "原始分数",
    feature_summary: "特征摘要",
    consistency_checks: "一致性检查",
    format_evidence: "格式证据",
    resolution_evidence: "分辨率证据",
    available: "可用",
    schemaVersion: "报告结构版本",
    detectorVersion: "检测器版本",
    modelVersion: "模型版本",
  });

  Object.assign(ui.en, {
    likelyAi: "Likely AI",
    likelyReal: "Likely Real",
    uncertain: "Uncertain",
    lowRisk: "Low",
    mediumRisk: "Medium",
    highRisk: "High",
    criticalRisk: "High",
    pendingReview: "Unreviewed",
    reviewedStatus: "Reviewed",
    confirmedAiStatus: "Confirmed AI",
    confirmedRealStatus: "Confirmed Real",
    falsePositiveStatus: "False Positive",
    falseNegativeStatus: "False Negative",
    needsFollowUpStatus: "Needs Follow-up",
    ignoredStatus: "Ignored",
    enabled: "Evidence chain enabled",
    raw_score: "Raw score",
    feature_summary: "Feature summary",
    consistency_checks: "Consistency checks",
    format_evidence: "Format evidence",
    resolution_evidence: "Resolution evidence",
    available: "Available",
    reportInfo: "Report Info",
    schemaVersion: "Report schema version",
    detectorVersion: "Detector version",
    modelVersion: "Model version",
  });

  Object.assign(ui.zh, {
    title: "检测详情",
    eyebrow: "取证卷宗 / 检测记录",
    close: "关闭详情",
    finalLabel: "检测结论",
    riskLevel: "风险等级",
    confidence: "置信度",
    reviewStatus: "复核状态",
    filename: "文件名",
    detectionTime: "检测时间",
    recordId: "report_id",
    userSummary: "证据摘要",
    reportInfo: "报告信息",
    decisionReason: "判断依据",
    recommendation: "复核建议",
    evidenceChain: "证据摘要",
    technical: "技术解释",
    rawJson: "原始 JSON",
    reviewActions: "复核操作",
    notReviewed: "尚未复核",
    savedAt: "已保存 {time}",
    reviewed: "标记已复核",
    confirmedAi: "确认 AI",
    confirmedReal: "确认真实",
    falsePositive: "标记误判",
    falseNegative: "标记漏判",
    needsFollowUp: "需要跟进",
    ignored: "忽略",
    addNote: "复核备注",
    notePlaceholder: "补充复核背景、判断理由或后续处理事项。",
    saveNote: "保存复核备注",
    copyJson: "复制 JSON",
    previewHtml: "查看 HTML 报告",
    downloadHtml: "下载 HTML",
    pdfSoon: "PDF 暂不支持",
    copied: "JSON 已复制。",
    htmlOpened: "HTML 报告已打开。",
    htmlBlocked: "浏览器阻止了报告预览，请检查弹窗设置。",
    htmlDownloaded: "HTML 报告已下载。",
    reviewSaved: "复核状态已保存。",
    reviewFailed: "复核状态保存失败。",
    noEvidence: "暂无可用的详细证据。",
    imageUnavailable: "图像预览不可用",
    fallbackNotice: "没有可用检测记录，正在显示安全兜底信息。",
    missingRecord: "缺少记录 ID，无法保存复核状态。",
    detailLoadFailed: "无法加载报告详情。",
    likelyAi: "可能 AI",
    likelyReal: "可能真实",
    uncertain: "不确定",
    lowRisk: "低",
    mediumRisk: "中",
    highRisk: "高",
    criticalRisk: "高",
    pendingReview: "未复核",
    reviewedStatus: "已复核",
    confirmedAiStatus: "已确认 AI",
    confirmedRealStatus: "已确认真实",
    falsePositiveStatus: "标记误判",
    falseNegativeStatus: "标记漏判",
    needsFollowUpStatus: "需要跟进",
    ignoredStatus: "已忽略",
    enabled: "证据链已启用",
    raw_score: "原始分数",
    feature_summary: "特征摘要",
    consistency_checks: "一致性检查",
    format_evidence: "格式证据",
    resolution_evidence: "分辨率证据",
    available: "可用",
    schemaVersion: "报告结构版本",
    detectorVersion: "检测器版本",
    modelVersion: "模型版本",
  });

  Object.assign(ui.en, {
    riskLevel: "Risk Level",
    reviewStatus: "Review Status",
    recordId: "report_id",
    userSummary: "Evidence Summary",
    evidenceChain: "Evidence Summary",
  });

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
    if (key === "ai") return tr("likelyAi");
    if (key === "real") return tr("likelyReal");
    if (key === "uncertain") return tr("uncertain");
    return key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function displayRiskLabel(value) {
    const key = String(value || "").trim().toLowerCase();
    if (key === "low") return tr("lowRisk");
    if (key === "medium") return tr("mediumRisk");
    if (key === "high") return tr("highRisk");
    if (key === "critical") return tr("criticalRisk");
    return value || "N/A";
  }

  function displayReviewStatus(value) {
    const key = String(value || "pending_review").trim().toLowerCase();
    const map = {
      pending_review: "pendingReview",
      reviewed: "reviewedStatus",
      confirmed_ai: "confirmedAiStatus",
      confirmed_real: "confirmedRealStatus",
      false_positive: "falsePositiveStatus",
      false_negative: "falseNegativeStatus",
      needs_follow_up: "needsFollowUpStatus",
      ignored: "ignoredStatus",
    };
    return tr(map[key] || "pendingReview");
  }

  function friendlyEvidenceTitle(key) {
    const normalized = String(key || "").trim();
    return tr(normalized) !== normalized ? tr(normalized) : normalized.replaceAll("_", " ");
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
      result.report_id,
      result.record_id,
      result.detection_id,
      raw.id,
      raw.report_id,
      raw.record_id,
      raw.detection_id,
      raw.history_file,
      `${firstDefined(result.filename, raw.filename, "record")}-${firstDefined(result.timestamp, raw.timestamp, Date.now())}`,
    );
    const filename = firstDefined(result.filename, result.image_name, raw.filename, raw.original_filename, raw.image_name, raw.file_name, image.filename, "unknown");
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
      review_status: firstDefined(result.review_status, raw.review_status, "pending_review"),
      review_note: firstDefined(result.review_note, raw.review_note, ""),
      reviewed_at: firstDefined(result.reviewed_at, raw.reviewed_at, ""),
      reviewer: firstDefined(result.reviewed_by, result.reviewer, raw.reviewed_by, raw.reviewer, ""),
      raw,
    };
  }

  function evidenceItems(value) {
    if (!value) return [];
    if (typeof value === "string") return [{ title: tr("evidenceChain"), value }];
    if (Array.isArray(value)) {
      return value.map((item, index) => {
        if (item && typeof item === "object") {
          return {
            title: friendlyEvidenceTitle(firstDefined(item.title, item.name, item.key, `${tr("evidenceChain")} ${index + 1}`)),
            value: firstDefined(item.value, item.score, item.status, item.result, ""),
            weight: firstDefined(item.weight, item.contribution, item.confidence, ""),
            explanation: firstDefined(item.explanation, item.reason, item.summary, ""),
          };
        }
        return { title: `${tr("evidenceChain")} ${index + 1}`, value: item };
      });
    }
    if (typeof value === "object") {
      return Object.entries(value).map(([key, item]) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          return {
            title: friendlyEvidenceTitle(firstDefined(item.title, item.name, key)),
            value: firstDefined(item.value, item.score, item.status, item.result, JSON.stringify(item)),
            weight: firstDefined(item.weight, item.contribution, item.confidence, ""),
            explanation: firstDefined(item.explanation, item.reason, item.summary, ""),
          };
        }
        return { title: friendlyEvidenceTitle(key), value: item };
      });
    }
    return [];
  }

  function renderEvidence(value) {
    const items = evidenceItems(value);
    if (!items.length) {
      return `<p class="detail-muted">${escapeHtml(tr("noEvidence"))}</p>`;
    }
    return `
      <div class="detail-evidence-list">
        ${items
          .map(
            (item) => `
              <div class="detail-evidence-item">
                <div>
                  <strong>${escapeHtml(item.title)}</strong>
                  <span>${escapeHtml(textFromValue(item.value, tr("available")))}</span>
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

  function reportDebugPayload(record) {
    const normalized = normalizeDetectionRecord(record);
    return {
      id: normalized.id,
      filename: normalized.filename,
      final_label: normalized.final_label,
    };
  }

  function renderReportEvidence(record) {
    const items = evidenceItems(record.debug_evidence);
    if (!items.length) return `<p>${escapeHtml(tr("noEvidence"))}</p>`;
    return `
      <ul class="evidence">
        ${items
          .map(
            (item) => `
              <li>
                <strong>${escapeHtml(item.title)}</strong>
                <span>${escapeHtml(textFromValue(item.value, tr("available")))}</span>
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
        <div class="cell"><span>Risk Level</span><strong><span class="badge">${escapeHtml(displayRiskLabel(record.risk_level))}</span></strong></div>
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
    <footer>Generated by AI Image Trust Scanner - PDF export is not supported in this MVP</footer>
  </main>
</body>
</html>`;
  }

  function openHtmlPreview(record) {
    const normalized = normalizeDetectionRecord(record);
    if (normalized.id) {
      const opened = window.open(`${REPORT_ENDPOINT_PREFIX}${encodeURIComponent(normalized.id)}/html`, "_blank", "noopener");
      if (opened) return true;
    }
    const html = generateDetectionReportHtml(record);
    const filename = safeReportFilename(normalized);
    console.log("[Day27] html report generated", filename);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, "_blank");
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    return Boolean(opened);
  }

  function downloadHtml(record) {
    const html = generateDetectionReportHtml(record);
    const filename = safeReportFilename(normalizeDetectionRecord(record));
    console.log("[Day27] html report generated", filename);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
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
    shell.className = "day27-detail-shell";
    shell.hidden = true;
    shell.innerHTML = `
      <div class="day27-detail-overlay" data-detail-close></div>
      <aside class="day27-detail-drawer" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="detail-title">
        <div class="day27-detail-content"></div>
      </aside>
    `;
    document.body.append(shell);
    shell.addEventListener("click", onShellClick);
    return shell;
  }

  function renderDrawer(record, options = {}) {
    const shell = detailShell();
    const panel = shell.querySelector(".day27-detail-drawer");
    const drawer = shell.querySelector(".day27-detail-content");
    if (!drawer || !panel) {
      console.warn("[Day27] drawer DOM missing");
      return;
    }
    const normalized = normalizeDetectionRecord(record);
    console.log("[Day27] drawer open", reportDebugPayload(normalized));
    state.record = normalized;
    const confidence = normalizeConfidence(normalized.confidence);
    const confidenceText = formatConfidence(normalized.confidence);
    const image = normalized.image_url
      ? `<img class="detail-image" src="${escapeHtml(normalized.image_url)}" alt="${escapeHtml(normalized.filename)}">`
      : `<div class="detail-image-placeholder">${escapeHtml(tr("imageUnavailable"))}</div>`;
    const schemaVersion = firstDefined(getValue(normalized.raw, "report_schema_version"), getValue(normalized.raw, "data.report_schema_version"), getValue(normalized.raw, "data.result.report_schema_version"), "N/A");
    const detectorVersion = firstDefined(getValue(normalized.raw, "detector_version"), getValue(normalized.raw, "data.detector_version"), getValue(normalized.raw, "data.result.detector_version"), "N/A");
    const modelVersion = firstDefined(getValue(normalized.raw, "model_version"), getValue(normalized.raw, "data.model_version"), getValue(normalized.raw, "data.result.model_version"), "N/A");
    const emptyNotice = !record || (typeof record === "object" && !Object.keys(record).length)
      ? `<section class="detail-section detail-warning"><p>${escapeHtml(tr("fallbackNotice"))}</p></section>`
      : "";
    drawer.innerHTML = `
      <header class="detail-header">
        <div>
          <p class="eyebrow">${escapeHtml(tr("eyebrow"))}</p>
          <h2 id="detail-title">${escapeHtml(tr("title"))}</h2>
        </div>
        <button class="detail-close" type="button" data-detail-close aria-label="${escapeHtml(tr("close"))}">x</button>
      </header>
      ${emptyNotice}
      <section class="detail-verdict dossier-summary">
        <div>
          <span>${escapeHtml(tr("finalLabel"))}</span>
          <strong>${escapeHtml(displayFinalLabel(normalized.final_label))}</strong>
        </div>
        <div>
          <span>${escapeHtml(tr("riskLevel"))}</span>
          <strong><span class="badge ${slug(normalized.risk_level)}">${escapeHtml(displayRiskLabel(normalized.risk_level))}</span></strong>
        </div>
        <div class="detail-confidence compact-confidence">
          <span>${escapeHtml(tr("confidence"))}</span>
          <strong>${escapeHtml(confidenceText)}</strong>
          <i style="--confidence:${confidence === null ? 0 : confidence}"></i>
        </div>
        <div>
          <span>${escapeHtml(tr("reviewStatus"))}</span>
          <strong><span class="badge review-${slug(normalized.review_status)}">${escapeHtml(displayReviewStatus(normalized.review_status))}</span></strong>
        </div>
        <div class="report-id-cell">
          <span>${escapeHtml(tr("recordId"))}</span>
          <strong>${escapeHtml(normalized.id)}</strong>
        </div>
      </section>
      <section class="detail-image-frame">${image}</section>
      <section class="detail-meta-grid">
        <div><span>${escapeHtml(tr("filename"))}</span><strong>${escapeHtml(normalized.filename)}</strong></div>
        <div><span>${escapeHtml(tr("detectionTime"))}</span><strong>${escapeHtml(normalized.created_at || "N/A")}</strong></div>
        <div><span>${escapeHtml(tr("reviewStatus"))}</span><strong>${escapeHtml(displayReviewStatus(normalized.review_status))}</strong></div>
      </section>
      <section class="detail-meta-grid detail-report-info" aria-label="${escapeHtml(tr("reportInfo"))}">
        <div><span>${escapeHtml(tr("schemaVersion"))}</span><strong>${escapeHtml(schemaVersion)}</strong></div>
        <div><span>${escapeHtml(tr("detectorVersion"))}</span><strong>${escapeHtml(detectorVersion)}</strong></div>
        <div><span>${escapeHtml(tr("modelVersion"))}</span><strong>${escapeHtml(modelVersion)}</strong></div>
      </section>
      <section class="detail-section">
        <h3>${escapeHtml(tr("userSummary"))}</h3>
        <p>${escapeHtml(normalized.user_facing_summary)}</p>
      </section>
      <section class="detail-section">
        <h3>${escapeHtml(tr("decisionReason"))}</h3>
        <p>${escapeHtml(normalized.decision_reason)}</p>
      </section>
      <section class="detail-section">
        <h3>${escapeHtml(tr("recommendation"))}</h3>
        <p>${escapeHtml(normalized.recommendation)}</p>
      </section>
      <section class="detail-section">
        <h3>${escapeHtml(tr("evidenceChain"))}</h3>
        ${renderEvidence(normalized.debug_evidence)}
      </section>
      <details class="detail-json detail-technical">
        <summary>${escapeHtml(tr("technical"))}</summary>
        <p>${escapeHtml(normalized.technical_explanation)}</p>
      </details>
      <details class="detail-json">
        <summary>${escapeHtml(tr("rawJson"))}</summary>
        <pre>${escapeHtml(jsonFor(normalized))}</pre>
      </details>
      <section class="detail-section review-actions-section" data-review-actions>
        <h3>${escapeHtml(tr("reviewActions"))}</h3>
        <div class="review-status-line">
          <span class="badge review-${slug(normalized.review_status)}">${escapeHtml(displayReviewStatus(normalized.review_status))}</span>
          <em>${escapeHtml(normalized.reviewed_at ? tr("savedAt", { time: normalized.reviewed_at }) : tr("notReviewed"))}</em>
        </div>
        <div class="review-action-grid" role="group" aria-label="Review status actions">
          <button class="table-action" type="button" data-review-status="reviewed">${escapeHtml(tr("reviewed"))}</button>
          <button class="table-action" type="button" data-review-status="confirmed_ai">${escapeHtml(tr("confirmedAi"))}</button>
          <button class="table-action" type="button" data-review-status="confirmed_real">${escapeHtml(tr("confirmedReal"))}</button>
          <button class="table-action" type="button" data-review-status="false_positive">${escapeHtml(tr("falsePositive"))}</button>
          <button class="table-action" type="button" data-review-status="false_negative">${escapeHtml(tr("falseNegative"))}</button>
          <button class="table-action" type="button" data-review-status="needs_follow_up">${escapeHtml(tr("needsFollowUp"))}</button>
          <button class="table-action" type="button" data-review-status="ignored">${escapeHtml(tr("ignored"))}</button>
        </div>
        <label class="review-note-field">
          <span>${escapeHtml(tr("addNote"))}</span>
          <textarea rows="4" data-review-note placeholder="${escapeHtml(tr("notePlaceholder"))}">${escapeHtml(normalized.review_note || "")}</textarea>
        </label>
        <div class="review-save-row">
          <button class="button button-secondary" type="button" data-detail-action="save-review">${escapeHtml(tr("saveNote"))}</button>
        </div>
      </section>
      <section class="detail-actions" data-report-actions>
        <button class="button button-secondary" type="button" data-detail-action="copy-json">${escapeHtml(tr("copyJson"))}</button>
        <button class="button button-ghost" type="button" data-detail-action="preview-html">${escapeHtml(tr("previewHtml"))}</button>
        <button class="button button-ghost" type="button" data-detail-action="download-html">${escapeHtml(tr("downloadHtml"))}</button>
        <button class="button button-ghost" type="button" disabled>${escapeHtml(tr("pdfSoon"))}</button>
        <p class="detail-feedback" aria-live="polite"></p>
      </section>
    `;
    shell.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => shell.classList.add("is-open"));
    document.body.classList.add("detail-drawer-open");
    shell.querySelector(".detail-close")?.focus({ preventScroll: true });
    shell.querySelector(".detail-image")?.addEventListener("error", (event) => {
      event.currentTarget.replaceWith(Object.assign(document.createElement("div"), { className: "detail-image-placeholder", textContent: tr("imageUnavailable") }));
    });
    if (options.focusReport) {
      window.setTimeout(() => shell.querySelector("[data-report-actions]")?.scrollIntoView({ behavior: "smooth", block: "center" }), 180);
    }
    if (options.focusReview) {
      window.setTimeout(() => shell.querySelector("[data-review-actions]")?.scrollIntoView({ behavior: "smooth", block: "center" }), 180);
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
    shell.classList.remove("is-open");
    shell.querySelector(".day27-detail-drawer")?.setAttribute("aria-hidden", "true");
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
    const reviewButton = event.target.closest("[data-review-status]");
    if (reviewButton && state.record) {
      await saveReview(reviewButton.dataset.reviewStatus);
      return;
    }
    if (!button || !state.record) return;
    try {
      if (button.dataset.detailAction === "copy-json") {
        await copyText(jsonFor(state.record));
        const original = button.textContent;
        button.textContent = tr("copied");
        window.clearTimeout(state.copyTimer);
        state.copyTimer = window.setTimeout(() => {
          button.textContent = original || tr("copyJson");
        }, 1500);
        setFeedback(tr("copied"));
      }
      if (button.dataset.detailAction === "preview-html") {
        const opened = openHtmlPreview(state.record);
        setFeedback(opened ? tr("htmlOpened") : tr("htmlBlocked"), !opened);
      }
      if (button.dataset.detailAction === "download-html") {
        downloadHtml(state.record);
        setFeedback(tr("htmlDownloaded"));
      }
      if (button.dataset.detailAction === "save-review") {
        await saveReview(state.record.review_status || "reviewed");
      }
    } catch (error) {
      setFeedback(error?.message || tr("reviewFailed"), true);
    }
  }

  async function saveReview(status) {
    const recordId = state.record?.id;
    if (!recordId) {
      setFeedback(tr("missingRecord"), true);
      return;
    }
    const note = document.querySelector("[data-review-note]")?.value || "";
    const response = await fetch(`${REVIEW_ENDPOINT_PREFIX}${encodeURIComponent(recordId)}/review`, {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        review_status: status || "reviewed",
        review_note: note,
        reviewed_by: "local_user",
        reviewer: "local_user",
      }),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.detail || `${tr("reviewFailed")} ${response.status}`);
    }
    state.record = normalizeDetectionRecord(payload?.record || { ...state.record, review_status: status, review_note: note });
    setFeedback(tr("reviewSaved"));
    renderDrawer(payload?.record || state.record, { focusReview: true });
    window.dispatchEvent(new CustomEvent("minerva:report-review-updated", { detail: payload?.record || state.record }));
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
      setFeedback(error?.message || tr("detailLoadFailed"), true);
    }
  }

  async function hydrateReportDetail(summary, options) {
    const recordId = firstDefined(summary?.report_id, summary?.id);
    if (!recordId) {
      hydrateHistory(summary, options);
      return;
    }
    try {
      const detail = await fetch(`${REPORT_ENDPOINT_PREFIX}${encodeURIComponent(recordId)}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      }).then((response) => {
        if (!response.ok) throw new Error(`Detail fetch failed: ${response.status}`);
        return response.json();
      });
      renderDrawer({ ...summary, ...detail, raw: detail }, options);
    } catch (error) {
      if (summary?.history_file) {
        hydrateHistory(summary, options);
        return;
      }
      setFeedback(error?.message || tr("detailLoadFailed"), true);
    }
  }

  function open(summary, options = {}) {
    state.lastTrigger = options.trigger || document.activeElement;
    const normalized = normalizeDetectionRecord(summary || {});
    console.log("[Day27] open detail drawer:", normalized.id, normalized.filename);
    renderDrawer(summary || {}, options);
    hydrateReportDetail(summary, options);
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
