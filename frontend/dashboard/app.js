const DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
const API_BASE_STORAGE_KEY = "minerva_api_base_url";
const API_KEY_STORAGE_KEY = "minerva_api_key";

function normalizeApiBaseUrl(value) {
  const text = String(value || "").trim().replace(/\/+$/, "");
  if (!text || !/^https?:\/\//i.test(text)) {
    return "";
  }
  return text;
}

function apiBaseFromQuery() {
  try {
    const params = new URLSearchParams(window.location.search || "");
    return normalizeApiBaseUrl(params.get("apiBase") || params.get("api_base"));
  } catch {
    return "";
  }
}

function apiBaseFromStorage() {
  try {
    return normalizeApiBaseUrl(window.localStorage?.getItem(API_BASE_STORAGE_KEY));
  } catch {
    return "";
  }
}

function apiKeyFromQuery() {
  try {
    const params = new URLSearchParams(window.location.search || "");
    return String(params.get("apiKey") || params.get("api_key") || "").trim();
  } catch {
    return "";
  }
}

function apiKeyFromStorage() {
  try {
    return String(window.localStorage?.getItem(API_KEY_STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

function sameOriginApiBase() {
  const protocol = window.location.protocol;
  if (!/^https?:$/i.test(protocol)) {
    return "";
  }
  const path = window.location.pathname || "";
  const backendServedDashboard = path.startsWith("/dashboard-ui") || path.startsWith("/dashboard-assets");
  const backendLikePort = ["8000", "8001", "8002"].includes(window.location.port || "");
  return backendServedDashboard || backendLikePort ? normalizeApiBaseUrl(window.location.origin) : "";
}

function uniqueApiBases(values) {
  const seen = new Set();
  return values
    .map(normalizeApiBaseUrl)
    .filter(Boolean)
    .filter((value) => {
      if (seen.has(value)) return false;
      seen.add(value);
      return true;
    });
}

function apiBaseCandidates() {
  return uniqueApiBases([
    window.MINERVA_API_BASE_URL,
    apiBaseFromQuery(),
    apiBaseFromStorage(),
    sameOriginApiBase(),
    DEFAULT_LOCAL_API_BASE_URL,
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
  ]);
}

let API_BASE_URL = apiBaseCandidates()[0] || DEFAULT_LOCAL_API_BASE_URL;
let API_KEY = String(window.MINERVA_API_KEY || apiKeyFromQuery() || apiKeyFromStorage() || "").trim();
let apiBaseProbePromise = null;

if (apiKeyFromQuery()) {
  try {
    window.localStorage?.setItem(API_KEY_STORAGE_KEY, API_KEY);
  } catch {
    // Ignore storage failures.
  }
}

function setApiBaseUrl(value, { persist = false } = {}) {
  const normalized = normalizeApiBaseUrl(value);
  if (!normalized) {
    return API_BASE_URL;
  }
  API_BASE_URL = normalized;
  window.MINERVA_CURRENT_API_BASE_URL = normalized;
  if (persist) {
    try {
      window.localStorage?.setItem(API_BASE_STORAGE_KEY, normalized);
    } catch {
      // Ignore storage failures in private browsing / file contexts.
    }
  }
  return API_BASE_URL;
}

async function probeApiBase(baseUrl, timeoutMs = 2500) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}/api/health`, {
      cache: "no-store",
      headers: { Accept: "application/json", ...authHeaders() },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Health check returned ${response.status}`);
    }
    return await response.json();
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function ensureApiBaseReachable({ timeoutMs = 2500, force = false } = {}) {
  if (apiBaseProbePromise && !force) {
    return apiBaseProbePromise;
  }
  apiBaseProbePromise = (async () => {
    let lastError = null;
    const candidates = apiBaseCandidates();
    for (const candidate of candidates) {
      try {
        const payload = await probeApiBase(candidate, timeoutMs);
        setApiBaseUrl(candidate, { persist: Boolean(apiBaseFromQuery() || window.MINERVA_API_BASE_URL) });
        return payload;
      } catch (error) {
        lastError = error;
      }
    }
    const error = new Error(
      `Backend is not connected. Tried ${candidates.join(", ")}. Start FastAPI with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000.`
    );
    error.status = 0;
    error.cause = lastError;
    throw error;
  })();
  try {
    return await apiBaseProbePromise;
  } finally {
    apiBaseProbePromise = null;
  }
}

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function setApiKey(value, { persist = false } = {}) {
  API_KEY = String(value || "").trim();
  if (persist) {
    try {
      if (API_KEY) window.localStorage?.setItem(API_KEY_STORAGE_KEY, API_KEY);
      else window.localStorage?.removeItem(API_KEY_STORAGE_KEY);
    } catch {
      // Ignore storage failures.
    }
  }
  return API_KEY;
}

function authHeaders() {
  return API_KEY ? { "X-API-Key": API_KEY } : {};
}

function apiUrlWithAuth(path) {
  const url = new URL(apiUrl(path), window.location.href);
  if (API_KEY) {
    url.searchParams.set("api_key", API_KEY);
  }
  return url.toString();
}

const API_ENDPOINTS = {
  get health() { return apiUrl("/api/health"); },
  get summary() { return apiUrl("/dashboard/summary"); },
  get recentResults() { return apiUrl("/api/v1/reports?limit=100"); },
  get reportQueue() { return apiUrl("/api/v1/reports/queue?limit=20"); },
  reportReview: (id) => apiUrl(`/api/v1/reports/${encodeURIComponent(id)}/review`),
  reportHtml: (id) => apiUrlWithAuth(`/api/v1/reports/${encodeURIComponent(id)}/html`),
  get reportExport() { return apiUrl("/api/v1/reports/export"); },
  get reviewCalibration() { return apiUrl("/api/v1/reports/review-calibration?limit=1"); },
  get policyReplay() { return apiUrl("/api/v1/reports/policy-replay?profiles=strict_safe_plus,high_recall_review"); },
  get scenarioStressPack() { return apiUrl("/api/v1/reports/scenario-stress-pack?limit=1"); },
  get trainingReadiness() { return apiUrl("/api/v1/reports/training-readiness?limit=1"); },
  get trainingReadinessRebuild() { return apiUrl("/api/v1/reports/training-readiness/rebuild"); },
  get trainingLabelQueue() { return apiUrl("/api/v1/reports/training-label-queue?limit=8"); },
  get chartData() { return apiUrl("/dashboard/chart-data"); },
  get modelStatus() { return apiUrl("/api/model-status"); },
  get policyProfiles() { return apiUrl("/api/v1/policy/profiles"); },
  get detectSingle() { return apiUrl("/api/detect/single"); },
  get batchJobSubmit() { return apiUrl("/api/v1/detect/batch/jobs"); },
  batchJobStatus: (id) => apiUrl(`/api/v1/detect/batch/jobs/${encodeURIComponent(id)}`),
  batchJobResult: (id) => apiUrl(`/api/v1/detect/batch/jobs/${encodeURIComponent(id)}/result`),
  get detectBatchCandidates() { return [apiUrl("/detect/batch"), apiUrl("/api/v1/detect/batch")]; },
};

window.MinervaApi = {
  apiUrl,
  apiUrlWithAuth,
  ensureApiBaseReachable,
  getBaseUrl: () => API_BASE_URL,
  setApiBaseUrl,
  getApiKey: () => API_KEY,
  setApiKey,
  authHeaders,
  apiBaseCandidates,
};

const translations = {
  zh: {
    intro: {
      text: "AI 内容可信检测平台",
    },
    header: {
      subtitleZh: "全领域 AI 内容可信检测平台",
      subtitleEn: "AI Content Trust & Forensics Console",
    },
    nav: {
      apiDocs: "API 文档",
      reportCenter: "报告中心",
      product: "产品",
      useCases: "应用场景",
      trustConsole: "可信控制台",
      api: "API",
      reports: "报告",
      architecture: "架构",
      tryDemo: "开始检测",
      errorGallery: "错误图库",
      refresh: "刷新",
      refreshing: "刷新中",
      syncing: "同步中",
      checking: "检查中",
      online: "Online",
      apiError: "API 异常",
    },
    hero: {
      eyebrow: "Minerva Trust Console",
      title: "Make the world for real",
      titleZh: "让 AI 时代的内容重新可信",
      lead: "Detect AI-generated image risk with evidence chains, confidence scoring, and human-review recommendations.",
      note: "用证据链、风险等级、置信度和复核建议，帮助平台、媒体和企业判断内容可信风险。",
      previewTitle: "Trust Score Preview",
      previewRisk: "中风险",
      previewConfidence: "高置信",
      previewAction: "复核",
      startScan: "开始可信检测",
      exploreConsole: "查看控制台",
    },
    workspace: {
      eyebrow: "检测工作台",
      title: "图像可信风险评估",
      description: "上传单张图片或小批量图片，查看结论、风险、置信度、证据和复核建议。",
    },
    single: {
      title: "上传图片",
      description: "通过当前检测器分析一张图片。",
      choose: "选择图片",
      formats: "支持 JPG / JPEG / PNG / WEBP",
      detect: "检测图片",
      analyzing: "分析中...",
      analyzingImage: "正在分析图片...",
      release: "松开以上传图片",
      remove: "移除图片",
      invalidType: "请上传 JPG、JPEG、PNG 或 WEBP 图片。",
      scanning: "正在分析来源信号、模型特征与取证痕迹...",
    },
    batch: {
      title: "上传批量图片",
      description: "使用批量接口分析多张图片。",
      choose: "选择多张图片",
      empty: "尚未选择图片",
      selected: "{count} 张图片已选择",
      detect: "批量检测",
      analyzing: "分析中...",
      analyzingImages: "正在分析 {count} 张图片...",
      complete: "批量检测完成",
      succeeded: "{succeeded} 成功，{failed} 失败",
      release: "松开以上传批量图片",
      clear: "清空全部",
      more: "+{count}",
      invalidType: "已忽略不支持的文件，请只上传图片。",
    },
    result: {
      emptyTitle: "可信评估已就绪",
      emptyBody: "上传图片以生成可信风险评估。",
      loading: "Minerva 正在生成证据链...",
      failed: "检测失败",
      singleComplete: "单图检测完成",
      batchComplete: "批量检测完成",
      topVerdict: "Top Verdict",
      verdict: "结论",
      riskLevel: "风险等级",
      confidence: "置信度",
      evidenceLayers: "证据层",
      status: "状态",
      saved: "已保存",
      evidenceSummary: "证据摘要",
      metadata: "Metadata / EXIF / XMP",
      modelSignal: "AI Model Signal",
      forensicSignal: "Forensic Signal",
      consistencySignal: "Consistency Signal",
      recommendation: "复核建议",
      technical: "技术说明",
      reason: "决策原因",
      exportActions: "导出操作",
      exportJson: "导出 JSON",
      copyJson: "复制 JSON",
      exportPdf: "导出 PDF",
      exportHtml: "导出 HTML",
      comingSoon: "Day27/Day28 Coming soon",
      notAvailable: "当前 MVP 暂无可用证据",
      copied: "已复制",
      copyFailed: "复制失败",
      downloadReady: "JSON 已下载",
      evidenceChain: "Evidence Chain",
      sourceProvenance: "Source Provenance",
      metadataLayer: "Metadata & AI Labeling",
      aiModelLayer: "AI Model Signal",
      forensicLayer: "Traditional Forensics",
      available: "Available",
      partial: "Partial",
      notAvailableStatus: "Not available in MVP",
    },
    labels: {
      ai_generated: "AI 生成",
      ai: "AI 生成",
      real: "真实",
      uncertain: "不确定",
      low: "低",
      medium: "中",
      high: "高",
      unknown: "未知",
      failed: "失败",
    },
    metrics: {
      total: "总检测数",
      totalHint: "检测任务",
      totalBadge: "实时汇总",
      ai: "AI 检出",
      aiHint: "AI 生成",
      aiBadge: "模型信号",
      real: "真实检出",
      realHint: "可能真实",
      realBadge: "低风险正常",
      uncertain: "不确定",
      uncertainHint: "需要复核",
      uncertainBadge: "复核队列",
      highRisk: "高风险",
      highRiskHint: "风险标记",
      highRiskBadge: "优先处理",
      avgConfidence: "平均置信度",
      avgConfidenceHint: "已加载结果",
      avgConfidenceBadge: "质量脉搏",
    },
    validated: {
      eyebrow: "核验能力 · 隔离 test 集",
      title: "实测性能",
      description: "下列每一个数字都来自从未参与调参或训练的 held-out test 集，可在仓库 reports/ 下复现。",
      zeroLeakage: "泄漏受控测试划分",
      tile: {
        accLabel: "准确率（已定案）",
        accHint: "对比优化前 90.4%",
        fpLabel: "真图误判率",
        fpHint: "从 14.5% 降到 6.4%（−8.1pt）",
        recallLabel: "AI 召回",
        recallHint: "起点 12.8%，数量级跃升",
        loraLabel: "LoRA 微调召回提升",
        loraHint: "SDXL +31pt，Flux 真图 FP 减半",
      },
      scenarioTitle: "诚实的场景天花板",
      scenario: {
        c2pa: "C2PA 溯源",
        c2paHint: "有签名的原图 — Tier0 快通道",
        modern: "现代生成图（干净）",
        modernHint: "SDXL / Flux / SD3 / PixArt / DALL·E3 / MJ",
        dirty: "社媒压缩 / 截图",
        dirtyHint: "已承认的弱项 — 下一轮训练重点",
      },
      meta: {
        method: "方法学：content-sha256 hash-mutex 切分、按 (数据集, 生成器, 标签) 分层；阈值只在 validation 集调；test 集仅做 before/after 回放，全程零泄漏。",
        brief: "查看完整评审简报 →",
      },
    },
    charts: {
      eyebrow: "信号",
      title: "信号与证据分布",
      description: "以产品视图展示模型标签、风险等级与置信度分布。",
      labelTitle: "标签分布",
      labelHint: "AI / Real / Uncertain",
      riskTitle: "风险分布",
      riskHint: "Low / Medium / High",
      confidenceTitle: "置信度分布",
      confidenceHint: "High / Medium / Low",
      noLabel: "暂无标签数据。",
      noRisk: "暂无风险数据。",
      noConfidence: "暂无置信度数据。",
      apiError: "图表数据加载失败。",
      updated: "更新于 {time}",
    },
  recent: {
    eyebrow: "审计日志",
    title: "最近检测结果",
    description: "API 保存的最新检测记录。",
      time: "时间",
      file: "文件",
      verdict: "结论",
      risk: "风险",
      confidence: "置信度",
      summary: "摘要",
      action: "操作",
      empty: "暂无最近检测结果。",
      loadFailed: "最近结果加载失败。",
      results: "{count} 条结果",
      viewJson: "查看详情",
      copyResult: "复制结果",
      reportSoon: "报告",
      filterAll: "全部",
      filterAi: "AI 生成",
      filterUncertain: "不确定",
      filterHigh: "高风险",
    },
    story: {
      eyebrow: "产品叙事",
      title: "为什么选择 Minerva",
      evidenceTitle: "Evidence-first detection",
      evidenceBody: "不只判断真假，而是形成证据链。",
      apiTitle: "SaaS & API path",
      apiBody: "支持网页检测、批量检测和开发者接口。",
      complianceTitle: "Compliance-aware",
      complianceBody: "面向生成合成内容标识、来源凭证和企业审计场景。",
      reviewTitle: "Human review friendly",
      reviewBody: "输出复核建议，避免把模型结果作为唯一处置依据。",
    },
    architecture: {
      eyebrow: "混合检测架构",
      title: "四层证据链",
      description: "Minerva 综合来源凭证、元数据、模型信号与传统取证特征，输出可审计结论。",
      output: "输出",
    },
    workflow: {
      eyebrow: "Trust & Safety 工作流",
      title: "Built for Trust & Safety Workflows",
      description: "面向风险复核、证据报告、API 集成和人工反馈闭环的产品预览。",
      policyTitle: "Policy-aware Risk Review",
      policyBody: "支持风险分级、复核队列和阈值策略，服务内容治理场景。",
      reportTitle: "Evidence-based Reports",
      reportBody: "围绕元数据、模型信号、取证特征和文件级证据形成报告上下文。",
      apiTitle: "API-first Integration",
      apiBody: "保留单图检测、批量检测、JSON 输出，并为 Webhook 预留架构空间。",
      reviewTitle: "Human Review Loop",
      reviewBody: "面向误判反馈、复核备注和样本闭环，避免模型结果成为唯一依据。",
    },
    apiPreview: {
      eyebrow: "SaaS / API 基础设施",
      title: "From Local MVP to SaaS / API Infrastructure",
      description: "当前本地 Demo 保持真实检测链路，同时为 API、报告和企业私有化部署打基础。",
      webTitle: "Web SaaS",
      webBody: "上传、批量检测、历史记录、Dashboard 和审计日志工作流。",
      webAction: "SaaS Preview Soon",
      apiTitle: "Developer API",
      apiBody: "/api/detect/single、/api/v1/detect/batch/jobs 和结构化 JSON 可信输出。",
      apiAction: "View API Docs Soon",
      enterpriseTitle: "Enterprise / Private Deployment",
      enterpriseBody: "审计日志、私有阈值、数据最小化和人工复核工作流控制。",
      enterpriseAction: "Enterprise Preview Soon",
    },
    footer: {
      disclaimerEn: "Not a forensic or legal final judgment.",
      disclaimerZh: "检测结果仅作为风险评估和人工复核辅助，不替代司法鉴定、法律意见或平台最终处置。",
    },
  },
  en: {
    intro: {
      text: "AI Content Trust Scanner",
    },
    header: {
      subtitleZh: "All-domain AI content trust platform",
      subtitleEn: "AI Content Trust & Forensics Console",
    },
    nav: {
      apiDocs: "API Docs",
      reportCenter: "Report Center",
      product: "Product",
      useCases: "Use Cases",
      trustConsole: "Trust Console",
      api: "API",
      reports: "Reports",
      architecture: "Architecture",
      tryDemo: "Try Demo",
      errorGallery: "Error Gallery",
      refresh: "Refresh",
      refreshing: "Refreshing",
      syncing: "Syncing",
      checking: "Checking",
      online: "Online",
      apiError: "API Error",
    },
    hero: {
      eyebrow: "Minerva Trust Console",
      title: "Make the world for real",
      titleZh: "Make AI-era content trustworthy again.",
      lead: "Detect AI-generated image risk with evidence chains, confidence scoring, and human-review recommendations.",
      note: "Help platforms, media teams, and enterprises assess content trust risk with risk levels and review guidance.",
      previewTitle: "Trust Score Preview",
      previewRisk: "Medium",
      previewConfidence: "High",
      previewAction: "Review",
      startScan: "Start Trust Scan",
      exploreConsole: "Explore Console",
    },
    workspace: {
      eyebrow: "Detection Workspace",
      title: "Image Trust Assessment",
      description: "Upload one image or a small batch, then inspect verdict, risk, confidence, evidence and review guidance.",
    },
    single: {
      title: "Upload Image",
      description: "Run one image through the current detector.",
      choose: "Choose an image",
      formats: "JPG, JPEG, PNG, or WEBP",
      detect: "Detect Image",
      analyzing: "Analyzing...",
      analyzingImage: "Analyzing image...",
      release: "Release to analyze image",
      remove: "Remove image",
      invalidType: "Please upload JPG, JPEG, PNG, or WEBP images.",
      scanning: "Analyzing provenance signals, model features, and forensic traces...",
    },
    batch: {
      title: "Upload Batch",
      description: "Analyze multiple images with the batch endpoint.",
      choose: "Choose multiple images",
      empty: "No images selected",
      selected: "{count} images selected",
      detect: "Batch Detect",
      analyzing: "Analyzing...",
      analyzingImages: "Analyzing {count} images...",
      complete: "Batch detection complete",
      succeeded: "{succeeded} succeeded, {failed} failed",
      release: "Release to upload batch",
      clear: "Clear all",
      more: "+{count}",
      invalidType: "Unsupported files were ignored. Please upload images only.",
    },
    result: {
      emptyTitle: "Trust assessment ready",
      emptyBody: "Upload an image to generate a trust assessment.",
      loading: "Minerva is building the evidence chain...",
      failed: "Detection failed",
      singleComplete: "Single detection complete",
      batchComplete: "Batch detection complete",
      topVerdict: "Top Verdict",
      verdict: "Verdict",
      riskLevel: "Risk Level",
      confidence: "Confidence",
      evidenceLayers: "Evidence Layers",
      status: "Status",
      saved: "Saved",
      evidenceSummary: "Evidence Summary",
      metadata: "Metadata / EXIF / XMP",
      modelSignal: "AI Model Signal",
      forensicSignal: "Forensic Signal",
      consistencySignal: "Consistency Signal",
      recommendation: "Recommendation",
      technical: "Technical Explanation",
      reason: "Decision Reason",
      exportActions: "Export Actions",
      exportJson: "Export JSON",
      copyJson: "Copy JSON",
      exportPdf: "Export PDF",
      exportHtml: "Export HTML",
      comingSoon: "Day27/Day28 Coming soon",
      notAvailable: "Not available in current MVP",
      copied: "Copied",
      copyFailed: "Copy failed",
      downloadReady: "JSON downloaded",
      evidenceChain: "Evidence Chain",
      sourceProvenance: "Source Provenance",
      metadataLayer: "Metadata & AI Labeling",
      aiModelLayer: "AI Model Signal",
      forensicLayer: "Traditional Forensics",
      available: "Available",
      partial: "Partial",
      notAvailableStatus: "Not available in MVP",
    },
    labels: {
      ai_generated: "AI Generated",
      ai: "AI Generated",
      real: "Real",
      uncertain: "Uncertain",
      low: "Low",
      medium: "Medium",
      high: "High",
      unknown: "Unknown",
      failed: "Failed",
    },
    metrics: {
      total: "Total Scans",
      totalHint: "Detection jobs",
      totalBadge: "Live summary",
      ai: "AI Detected",
      aiHint: "AI generated",
      aiBadge: "Model signal",
      real: "Real Detected",
      realHint: "Likely authentic",
      realBadge: "Low risk is normal",
      uncertain: "Uncertain",
      uncertainHint: "Needs review",
      uncertainBadge: "Review queue",
      highRisk: "High Risk",
      highRiskHint: "Risk flagged",
      highRiskBadge: "Priority",
      avgConfidence: "Average Confidence",
      avgConfidenceHint: "Loaded results",
      avgConfidenceBadge: "Quality pulse",
    },
    validated: {
      eyebrow: "Verified Capability · Isolated Test Set",
      title: "Validated Performance",
      description: "Every number below comes from a held-out test split that was never used to tune any threshold or train any model. Reproducible from the `reports/` directory.",
      zeroLeakage: "Leakage-controlled split",
      tile: {
        accLabel: "Accuracy (decided)",
        accHint: "vs 90.4% pre-tuning",
        fpLabel: "Real-image false positive",
        fpHint: "down from 14.5% (−8.1pt)",
        recallLabel: "AI recall",
        recallHint: "up from 12.8% at project start",
        loraLabel: "LoRA fine-tune lift",
        loraHint: "SDXL recall +31pt, Flux FP halved",
      },
      scenarioTitle: "Honest Scenario Ceilings",
      scenario: {
        c2pa: "C2PA Provenance",
        c2paHint: "Original with signed manifest — Tier0 fast path",
        modern: "Modern AI generators (clean)",
        modernHint: "SDXL / Flux / SD3 / PixArt / DALL·E3 / MJ",
        dirty: "Social-media compressed / screenshot",
        dirtyHint: "Acknowledged weak spot — next training target",
      },
      meta: {
        method: "Methodology: content-sha256 hash-mutex split, stratified by (dataset, generator, label); thresholds tuned on validation only; replay-based before/after on the isolated test set.",
        brief: "Read full competition brief →",
      },
    },
    charts: {
      eyebrow: "Signals",
      title: "Signals & Evidence Distribution",
      description: "Compact product view of model labels, risk levels, and confidence bands.",
      labelTitle: "Label Distribution",
      labelHint: "AI / Real / Uncertain",
      riskTitle: "Risk Distribution",
      riskHint: "Low / Medium / High",
      confidenceTitle: "Confidence Distribution",
      confidenceHint: "High / Medium / Low",
      noLabel: "No label data yet.",
      noRisk: "No risk data yet.",
      noConfidence: "No confidence data yet.",
      apiError: "Failed to load chart data.",
      updated: "Updated {time}",
    },
  recent: {
    eyebrow: "Audit Log",
    title: "Recent Results",
    description: "Latest detection records saved by the API.",
      time: "Time",
      file: "File",
      verdict: "Verdict",
      risk: "Risk",
      confidence: "Confidence",
      summary: "Summary",
      action: "Action",
      empty: "No recent detection results yet.",
      loadFailed: "Failed to load recent results.",
      results: "{count} results",
      viewJson: "Detail",
      copyResult: "Copy Result",
      reportSoon: "Report",
      filterAll: "All",
      filterAi: "AI Generated",
    filterUncertain: "Uncertain",
    filterHigh: "High Risk",
  },
  reportCenter: {
    eyebrow: "Report Center",
    title: "Report Center",
    description: "Search, review, and export detection audit records.",
    filteredStatus: "{count} filtered",
    empty: "No report records found.",
    loadFailed: "Failed to load report records.",
    queueFailed: "Review queue failed to load.",
    queueEmpty: "No records waiting for review.",
    summary: {
      total: "Total",
      filtered: "Filtered",
      pending: "Pending Review",
      highRisk: "High Risk",
      uncertain: "Uncertain",
    },
    filters: {
      search: "Search",
      searchPlaceholder: "Filename, record ID, label, reason...",
      risk: "Risk",
      label: "Label",
      review: "Review",
      date: "Date Range",
      confidence: "Confidence",
      sort: "Sort",
    },
    options: {
      all: "All",
    },
    risk: {
      high: "High",
      medium: "Medium",
      low: "Low",
      unknown: "Unknown",
      unknownUnset: "Unknown / Unset",
    },
    verdict: {
      ai: "AI generated",
      real: "Real",
      uncertain: "Uncertain",
      unknown: "Unknown",
    },
    review: {
      unreviewed: "Unreviewed",
      pending_review: "Pending Review",
      reviewed: "Reviewed",
      confirmed_ai: "Confirmed AI",
      confirmed_real: "Confirmed Real",
      false_positive: "False Positive",
      false_negative: "False Negative",
      needs_recheck: "Needs Recheck",
      needs_follow_up: "Needs Follow-up",
      ignored: "Ignored",
    },
    date: {
      all: "All",
      today: "Today",
      last_7_days: "Last 7 days",
      last_30_days: "Last 30 days",
    },
    confidence: {
      all: "All",
      gte_0_8: ">= 0.8",
      mid: "0.5 - 0.8",
      lt_0_5: "< 0.5",
    },
    sort: {
      newest: "Newest first",
      oldest: "Oldest first",
      risk_priority: "Risk priority",
      confidence_desc: "Confidence high to low",
      confidence_asc: "Confidence low to high",
    },
    table: {
      time: "Time",
      fileRecord: "File / Record",
      verdict: "Verdict",
      risk: "Risk",
      confidence: "Confidence",
      review: "Review",
      summary: "Summary",
      action: "Action",
    },
    actions: {
      reset: "Reset Filters",
      exportJson: "Export JSON",
      exportCsv: "Export CSV",
      viewDetail: "View Detail",
      report: "Report",
      review: "Review",
    },
    queue: {
      title: "Risk Review Queue",
      subtitle: "High risk, uncertain, and pending review",
    },
  },
  story: {
      eyebrow: "Product Story",
      title: "Why Minerva",
      evidenceTitle: "Evidence-first detection",
      evidenceBody: "Not just a binary truth label, but an evidence chain.",
      apiTitle: "SaaS & API path",
      apiBody: "Supports web detection, batch detection and developer APIs.",
      complianceTitle: "Compliance-aware",
      complianceBody: "Designed for synthetic content labeling, provenance credentials and enterprise audit scenarios.",
      reviewTitle: "Human review friendly",
      reviewBody: "Outputs review guidance so model results are not treated as the only enforcement basis.",
    },
    architecture: {
      eyebrow: "Hybrid Detection Architecture",
      title: "Four-Layer Evidence Chain",
      description: "Minerva combines provenance, metadata, model signals and forensic traces before producing an auditable verdict.",
      output: "Output",
    },
    workflow: {
      eyebrow: "Trust & Safety Workflows",
      title: "Built for Trust & Safety Workflows",
      description: "A product preview for risk review, evidence reporting, API integration, and human feedback loops.",
      policyTitle: "Policy-aware Risk Review",
      policyBody: "Risk levels, review queues, and threshold strategy for content operations.",
      reportTitle: "Evidence-based Reports",
      reportBody: "Metadata, model signals, forensic features, and file-level evidence context.",
      apiTitle: "API-first Integration",
      apiBody: "Single image detection, batch detection, JSON output, and webhook-ready architecture.",
      reviewTitle: "Human Review Loop",
      reviewBody: "Misclassification feedback, reviewer notes, and sample-level improvement loops.",
    },
    apiPreview: {
      eyebrow: "SaaS / API Infrastructure",
      title: "From Local MVP to SaaS / API Infrastructure",
      description: "The current demo keeps the local workflow real while making room for API, reporting, and enterprise deployment paths.",
      webTitle: "Web SaaS",
      webBody: "Upload, batch detection, history, dashboard, and audit log workflow.",
      webAction: "SaaS Preview Soon",
      apiTitle: "Developer API",
      apiBody: "/api/detect/single, /api/v1/detect/batch/jobs, and structured JSON trust output.",
      apiAction: "View API Docs Soon",
      enterpriseTitle: "Enterprise / Private Deployment",
      enterpriseBody: "Audit logs, private thresholds, data minimization, and review workflow controls.",
      enterpriseAction: "Enterprise Preview Soon",
    },
    footer: {
      disclaimerEn: "Not a forensic or legal final judgment.",
      disclaimerZh: "Detection results are risk-assessment and human-review support only; they do not replace forensic appraisal, legal advice or final platform action.",
    },
  },
};

function mergeTranslations(target, source) {
  Object.entries(source).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      target[key] = target[key] || {};
      mergeTranslations(target[key], value);
    } else {
      target[key] = value;
    }
  });
}

mergeTranslations(translations.zh, {
  intro: {
    text: "AI 内容可信检测平台",
  },
  nav: {
    product: "产品",
    useCases: "应用场景",
    trustConsole: "可信控制台",
    api: "API",
    reports: "报告",
    architecture: "架构",
    tryDemo: "开始检测",
    errorGallery: "错误图库",
    refresh: "刷新",
    refreshing: "刷新中",
    syncing: "同步中",
    checking: "检查中",
    online: "Online",
    apiError: "API 异常",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "让 AI 时代的内容重新可信",
    lead: "Minerva 将图像检测、元数据、来源凭证和取证特征转化为可复核的可信证据链。",
    startScan: "开始可信检测",
    exploreConsole: "查看控制台",
    previewTitle: "实时可信预览",
    previewRisk: "中风险",
    previewQueue: "复核队列",
    previewApi: "本地 API 路径",
  },
  workflowStep: {
    upload: "上传",
    analyze: "分析",
    evidence: "证据",
    review: "复核",
  },
  workspace: {
    eyebrow: "可信检测工作流",
    title: "Minerva 图像可信风险评估",
    description: "提交图片内容，应用检测信号，形成证据链，并将结果路由到人工复核。",
    liveEyebrow: "本地实时检测 Demo",
    liveTitle: "图像可信风险评估",
    liveBody: "当前本地 MVP 保持真实上传、批量检测、Dashboard 刷新、JSON 导出和审计历史全部连通。",
    capabilityOne: "单图与批量检测",
    capabilityTwo: "风险、置信度与证据上下文",
    capabilityThree: "面向人工复核的处置建议",
  },
  single: {
    title: "单图检测",
    description: "通过当前检测器分析一张图片。",
    choose: "选择或拖拽图片",
    formats: "支持 JPG / JPEG / PNG / WEBP",
    detect: "检测图片",
    analyzing: "分析中...",
    analyzingImage: "正在分析图片...",
    release: "松开以扫描图片",
    remove: "移除图片",
    invalidType: "请上传 JPG、JPEG、PNG 或 WEBP 图片。",
    scanning: "正在分析来源信号、模型特征与取证痕迹...",
  },
  batch: {
    title: "批量检测",
    description: "使用批量接口分析多张图片。",
    choose: "选择或拖拽多张图片",
    empty: "尚未选择图片",
    selected: "{count} 张图片已选择",
    detect: "批量检测",
    analyzing: "分析中...",
    analyzingImages: "正在分析 {count} 张图片...",
    complete: "批量检测完成",
    succeeded: "{succeeded} 成功，{failed} 失败",
    release: "松开以上传批量图片",
    clear: "清空全部",
    more: "+{count}",
    invalidType: "已忽略不支持的文件，请只上传图片。",
  },
  result: {
    emptyTitle: "Live Trust Verdict",
    emptyBody: "上传图片后生成可信风险评估。",
    loading: "Minerva 正在构建证据链...",
    failed: "检测失败",
    singleComplete: "单图检测完成",
    batchComplete: "批量检测完成",
    topVerdict: "核心结论",
    verdict: "结论",
    riskLevel: "风险等级",
    confidence: "置信度",
    evidenceLayers: "证据层",
    status: "状态",
    saved: "已保存",
    evidenceSummary: "证据摘要",
    recommendation: "复核建议",
    technical: "技术解释",
    reason: "决策原因",
    exportActions: "导出操作",
    exportJson: "导出 JSON",
    copyJson: "复制 JSON",
    exportPdf: "导出 PDF",
    exportHtml: "导出 HTML",
    comingSoon: "Day27/Day28 Coming soon",
    notAvailable: "当前 MVP 暂无可用证据",
    copied: "已复制",
    copyFailed: "复制失败",
    downloadReady: "JSON 已下载",
    evidenceChain: "证据链",
    sourceProvenance: "来源凭证",
    metadataLayer: "元数据与 AI 标识",
    aiModelLayer: "AI 模型信号",
    forensicLayer: "传统取证特征",
    available: "可用",
    partial: "部分可用",
    notAvailableStatus: "当前 MVP 暂无",
  },
  labels: {
    ai_generated: "AI 生成",
    ai: "AI 生成",
    real: "真实",
    uncertain: "不确定",
    low: "低",
    medium: "中",
    high: "高",
    unknown: "未知",
    failed: "失败",
  },
  metrics: {
    total: "总检测数",
    totalHint: "检测任务",
    ai: "AI 检出",
    aiHint: "AI 生成",
    real: "真实检出",
    realHint: "可能真实",
    uncertain: "不确定",
    uncertainHint: "需要复核",
    highRisk: "高风险",
    highRiskHint: "风险标记",
    avgConfidence: "平均置信度",
    avgConfidenceHint: "已加载结果",
  },
  charts: {
    eyebrow: "信号智能",
    title: "信号与证据分布",
    description: "以产品视图展示模型标签、风险等级与置信度分布。",
    labelTitle: "标签分布",
    labelHint: "AI / 真实 / 不确定",
    riskTitle: "风险分布",
    riskHint: "低 / 中 / 高",
    confidenceTitle: "置信度分布",
    confidenceHint: "高 / 中 / 低",
    noLabel: "暂无标签数据。",
    noRisk: "暂无风险数据。",
    noConfidence: "暂无置信度数据。",
    apiError: "图表数据加载失败。",
    updated: "更新于 {time}",
  },
  recent: {
    eyebrow: "审计日志预览",
    title: "最近检测结果",
    description: "每次检测都会形成可复核的结构化记录，包含置信度、风险等级与证据上下文。",
    time: "时间",
    file: "文件",
    verdict: "结论",
    risk: "风险",
    confidence: "置信度",
    summary: "摘要",
    action: "操作",
    empty: "暂无最近检测结果。",
    loadFailed: "最近结果加载失败。",
    results: "{count} 条结果",
      viewJson: "查看详情",
      copyResult: "复制结果",
      reportSoon: "报告",
    filterAll: "全部",
    filterAi: "AI 生成",
    filterUncertain: "不确定",
    filterHigh: "高风险",
  },
  reportCenter: {
    eyebrow: "报告中心",
    title: "报告中心",
    description: "搜索、复核并导出检测审计记录。",
    filteredStatus: "已筛选 {count} 条",
    empty: "没有找到符合条件的报告记录。",
    loadFailed: "报告记录加载失败。",
    queueFailed: "风险复核队列加载失败。",
    queueEmpty: "暂无需要复核的记录。",
    summary: {
      total: "总记录",
      filtered: "筛选结果",
      pending: "待复核",
      highRisk: "高风险",
      uncertain: "不确定",
    },
    filters: {
      search: "搜索",
      searchPlaceholder: "搜索文件名、记录 ID、结论或原因……",
      risk: "风险等级",
      label: "检测结论",
      review: "复核状态",
      date: "时间范围",
      confidence: "置信度",
      sort: "排序",
    },
    options: {
      all: "全部",
    },
    risk: {
      high: "高",
      medium: "中",
      low: "低",
      unknown: "未知",
      unknownUnset: "未知 / 未设置",
    },
    verdict: {
      ai: "AI 生成",
      real: "真实",
      uncertain: "不确定",
      unknown: "未知",
    },
    review: {
      unreviewed: "未复核",
      pending_review: "待复核",
      reviewed: "已复核",
      confirmed_ai: "确认为 AI",
      confirmed_real: "确认为真实",
      false_positive: "误判为 AI",
      false_negative: "漏判 AI",
      needs_recheck: "需重检",
      needs_follow_up: "需要跟进",
      ignored: "已忽略",
    },
    date: {
      all: "全部",
      today: "今天",
      last_7_days: "最近 7 天",
      last_30_days: "最近 30 天",
    },
    confidence: {
      all: "全部",
      gte_0_8: ">= 0.8",
      mid: "0.5 - 0.8",
      lt_0_5: "< 0.5",
    },
    sort: {
      newest: "最新优先",
      oldest: "最早优先",
      risk_priority: "风险优先",
      confidence_desc: "置信度从高到低",
      confidence_asc: "置信度从低到高",
    },
    table: {
      time: "时间",
      fileRecord: "文件 / 记录",
      verdict: "结论",
      risk: "风险",
      confidence: "置信度",
      review: "复核",
      summary: "摘要",
      action: "操作",
    },
    actions: {
      reset: "重置筛选",
      exportJson: "导出 JSON",
      exportCsv: "导出 CSV",
      viewDetail: "查看详情",
      report: "报告",
      review: "复核",
    },
    queue: {
      title: "风险复核队列",
      subtitle: "高风险、不确定与待复核记录",
    },
  },
  story: {
    eyebrow: "产品叙事",
    title: "Why Minerva",
    evidenceTitle: "Evidence-first detection",
    evidenceBody: "不只判断真假，而是形成可复核的证据链。",
    apiTitle: "SaaS & API path",
    apiBody: "支持网页检测、批量检测和开发者接口。",
    complianceTitle: "Compliance-aware",
    complianceBody: "面向生成合成内容标识、来源凭证和企业审计场景。",
    reviewTitle: "Human review friendly",
    reviewBody: "输出复核建议，避免把模型结果作为唯一处置依据。",
  },
  workflow: {
    eyebrow: "Trust & Safety 工作流",
    title: "面向运营复核设计",
    description: "面向风险复核、证据报告、API 集成和人工反馈闭环的产品预览。",
    submitTitle: "提交图片内容",
    submitBody: "支持上传、批量导入和结构化 JSON 检测结果。",
    policyTitle: "规则 / 阈值预览",
    policyBody: "支持风险分级、复核队列和阈值策略，服务内容治理场景。",
    reportTitle: "报告中心预览",
    reportBody: "围绕元数据、模型信号、取证特征和文件级证据形成报告上下文。",
    reviewTitle: "人工复核闭环",
    reviewBody: "面向误判反馈、复核备注和样本闭环，避免模型结果成为唯一依据。",
  },
  architecture: {
    eyebrow: "混合检测架构",
    title: "四层证据链",
    description: "Minerva 综合来源凭证、元数据、模型信号与传统取证特征，输出可审计结论。",
    output: "输出",
  },
  apiPreview: {
    eyebrow: "SaaS / API 基础设施",
    title: "From Local MVP to SaaS / API Infrastructure",
    description: "当前本地 Demo 保持真实检测链路，同时为 API、报告和企业私有化部署打基础。",
    webTitle: "Web SaaS",
    webBody: "上传、批量检测、历史记录、Dashboard 和审计日志工作流。",
    webAction: "SaaS Preview Soon",
    apiTitle: "Developer API",
    apiBody: "/api/detect/single、/api/v1/detect/batch/jobs 和结构化 JSON 可信输出。",
    apiAction: "View API Docs Soon",
    enterpriseTitle: "Enterprise / Private Deployment",
    enterpriseBody: "审计日志、私有阈值、数据最小化和人工复核工作流控制。",
    enterpriseAction: "Enterprise Preview Soon",
  },
  footer: {
    disclaimerEn: "Not a forensic or legal final judgment.",
    disclaimerZh: "检测结果仅作为风险评估和人工复核辅助，不替代司法鉴定、法律意见或平台最终处置。",
  },
});

mergeTranslations(translations.zh, {
  reportCenter: {
    trainingQueue: {
      title: "训练标注队列",
      subtitle: "有本地文件、可直接补齐训练标签的报告",
      empty: "暂无可直接进入训练标注的本地文件。",
      failed: "训练标注队列加载失败。",
      needAi: "缺 AI 标签",
      needReal: "缺真实标签",
      needEither: "需确认 AI 或真实",
      gap: "还缺 {ai} 个 AI / {real} 个真实",
      suggested: "建议状态",
      markAi: "确认 AI",
      markReal: "确认真实",
      saved: "已保存",
      saveFailed: "保存失败",
      rebuilding: "重建中",
      rebuild: "重建",
      rebuildDone: "已重建",
    },
  },
});

mergeTranslations(translations.en, {
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "Minerva turns image detection, metadata, provenance signals, and forensic traces into reviewable trust evidence.",
    previewTitle: "Live trust preview",
    previewQueue: "Review queue",
    previewApi: "Local API path",
    exploreConsole: "View Console",
  },
  workflowStep: {
    upload: "Upload",
    analyze: "Analyze",
    evidence: "Evidence",
    review: "Review",
  },
  workspace: {
    eyebrow: "Trust Scan Workflow",
    title: "Minerva Trust Scan",
    description: "Upload image content, apply detection signals, build evidence, and route the result for review.",
    liveEyebrow: "Live Detection Demo",
    liveTitle: "Image trust risk assessment",
    liveBody: "The local MVP keeps real upload, batch detection, dashboard refresh, JSON export, and audit history connected to the backend.",
    capabilityOne: "Single image and batch scan",
    capabilityTwo: "Risk, confidence, evidence context",
    capabilityThree: "Human review recommendation",
  },
  recent: {
    eyebrow: "Audit Log Preview",
    description: "Every scan is stored as a reviewable result with confidence, risk, and evidence context.",
  },
  workflow: {
    title: "Designed for operational review",
    submitTitle: "Submit image content",
    submitBody: "Upload, batch import, and structured JSON scan results.",
    policyTitle: "Rules / Thresholds Preview",
    reportTitle: "Reports Preview",
  },
  architecture: {
    title: "Four Evidence Layers",
  },
});

mergeTranslations(translations.zh, {
  demo: {
    eyebrow: "实时可信检测演示",
    title: "实时可信检测演示",
    description: "上传图片内容，应用检测信号，形成证据链，并查看 Simple 或 JSON 结果视图。",
    uploadTab: "上传",
    batchTab: "批量",
    sampleTab: "样例",
    sampleTitle: "样例预览",
    sampleBody: "这些本地占位项用于说明复核场景，不会改变后端数据。",
    sampleCreator: "创作者上传",
    sampleMedia: "媒体归档",
    sampleAd: "营销素材",
    sampleNote: "样例仅用于界面预览。请上传文件以运行真实检测。",
    resultsEyebrow: "模型输出",
    resultsTitle: "Results",
    simpleView: "Simple",
    jsonView: "JSON",
    emptyJson: "暂无检测结果。上传图片后可查看结构化 JSON。",
  },
  workspace: {
    liveEyebrow: "本地实时检测 Demo",
    liveTitle: "图像可信风险评估",
    liveBody: "当前本地 MVP 保持真实上传、批量检测、Dashboard 刷新、JSON 导出和审计历史全部连通。",
    capabilityOne: "单图与批量检测",
    capabilityTwo: "风险、置信度与证据上下文",
    capabilityThree: "面向人工复核的处置建议",
  },
  result: {
    emptyTitle: "Live Trust Verdict",
    emptyBody: "上传图片后生成可信风险评估。",
    topVerdict: "Verdict",
  },
  recent: {
    description: "每次检测都会形成可复核的结构化记录，包含风险等级、置信度、摘要和可导出的 JSON。",
  },
  workflow: {
    title: "面向运营复核的可信检测工作流",
    description: "面向策略复核、证据报告、API 集成和人工反馈闭环的产品预览。",
    submitTitle: "Submit",
    submitBody: "上传、批量导入和结构化 JSON 检测结果。",
    detectTitle: "Detect",
    detectBody: "应用元数据、模型、一致性与取证信号。",
    routeTitle: "Route",
    routeBody: "将高风险或不确定样本路由到人工复核。",
    exportTitle: "Export",
    exportBody: "当前支持 JSON 导出，报告工作流将在后续完善。",
  },
  architecture: {
    description: "Minerva 不把模型分数作为唯一结论，而是将来源凭证、元数据、模型信号和传统取证特征组合为可审计证据链。",
  },
});

mergeTranslations(translations.en, {
  demo: {
    eyebrow: "Live Trust Detection Demo",
    title: "Live Trust Detection Demo",
    description: "Upload image content, apply detection signals, build evidence, and inspect a Simple or JSON result view.",
    uploadTab: "Upload",
    batchTab: "Batch",
    sampleTab: "Sample",
    sampleTitle: "Sample preview",
    sampleBody: "Use these local placeholders to explain review scenarios without changing backend data.",
    sampleCreator: "Creator upload",
    sampleMedia: "Media archive",
    sampleAd: "Campaign asset",
    sampleNote: "Samples are interface placeholders only. Upload a file to run the real detector.",
    resultsEyebrow: "Model output",
    resultsTitle: "Results",
    simpleView: "Simple",
    jsonView: "JSON",
    emptyJson: "No result yet. Upload an image to inspect structured JSON.",
  },
  result: {
    emptyTitle: "Live Trust Verdict",
  },
  recent: {
    description: "Every scan becomes a reviewable record with risk level, confidence, summary, and exportable JSON.",
  },
  workflow: {
    title: "Built for Trust & Safety Operations",
    description: "A product preview for policy review, evidence reporting, API integration, and feedback loops.",
    submitTitle: "Submit",
    submitBody: "Upload, batch import, and structured JSON scan results.",
    detectTitle: "Detect",
    detectBody: "Apply metadata, model, consistency, and forensic signals.",
    routeTitle: "Route",
    routeBody: "Route high-risk or uncertain samples to human review.",
    exportTitle: "Export",
    exportBody: "Export JSON now, with report workflows planned next.",
  },
  architecture: {
    description: "Minerva does not treat a model score as the final answer. It combines provenance, metadata, model signals, and forensic traces into an auditable evidence chain.",
  },
});

mergeTranslations(translations.en, {
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "From image signals to verifiable review. Minerva converts model output, metadata, provenance hints, and forensic traces into structured trust evidence.",
    previewTitle: "Trust telemetry",
  },
  roadmap: {
    eyebrow: "Multimodal Trust Roadmap",
    title: "Multimodal Trust Roadmap",
    description: "Minerva starts image-first, then extends the same evidence-chain product language across video, text, audio, and multimodal reports.",
    image: "Image",
    video: "Video",
    text: "Text",
    audio: "Audio",
    report: "Multimodal Report",
  },
});

mergeTranslations(translations.zh, {
  hero: {
    title: "Make the world for real",
    titleZh: "让 AI 时代的内容重新可信",
  },
  roadmap: {
    eyebrow: "全领域 AI 内容检测路线",
    title: "全领域 AI 内容检测路线",
    description: "Minerva 从图像优先的 MVP 出发，将同一套证据链产品语言扩展到视频、文本、语音和多模态报告。",
    image: "图像",
    video: "视频",
    text: "文本",
    audio: "语音",
    report: "多模态报告",
  },
  footer: {
    disclaimerZh: "检测结果仅作为风险评估和人工复核辅助，不替代司法鉴定、法律意见或平台最终处置。",
  },
});

mergeTranslations(translations.en, {
  nav: {
    useCases: "Scenarios",
    reports: "Report",
    tryDemo: "Launch Demo",
    online: "Live System",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "From image signals to verifiable review. Minerva converts model output, metadata, provenance hints, and forensic traces into structured trust evidence.",
    previewTitle: "Trust telemetry",
  },
  demo: {
    eyebrow: "Forensic Console",
    title: "Live AI Content Detection Demo",
    description: "Submit image content, inspect model signals, and review the structured trust output in Simple or JSON form.",
  },
  workspace: {
    liveEyebrow: "Forensic workspace",
    liveTitle: "Image signal intake",
    liveBody: "A local MVP with real upload, batch detection, dashboard refresh, JSON export, and audit history connected to the backend.",
  },
  recent: {
    title: "Audit Log",
    description: "Every scan becomes a reviewable record with risk level, confidence, summary, and exportable JSON.",
  },
  footer: {
    disclaimerEn: "Not a final legal judgment. A structured trust signal for review.",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    useCases: "应用场景",
    reports: "报告",
    tryDemo: "启动检测",
    online: "Live System",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "让 AI 时代的内容重新可信",
    lead: "从图像信号到可复核结论。Minerva 将模型输出、元数据、来源线索和取证痕迹转化为结构化可信证据。",
    previewTitle: "可信度预览",
  },
  demo: {
    eyebrow: "取证控制台",
    title: "实时 AI 内容检测演示",
    description: "提交图像内容，检查模型信号，并以 Simple 或 JSON 形式复核结构化可信输出。",
  },
  workspace: {
    liveEyebrow: "取证工作区",
    liveTitle: "图像信号接入",
    liveBody: "本地 MVP 保持真实上传、批量检测、Dashboard 刷新、JSON 导出和审计历史全部连接到后端。",
  },
  recent: {
    title: "审计日志",
    description: "每次检测都会形成可复核的结构化记录，包含风险等级、置信度、摘要和可导出的 JSON。",
  },
  footer: {
    disclaimerZh: "检测结果仅作为结构化风险信号和人工复核辅助，不替代司法鉴定、法律意见或平台最终处置。",
  },
});

mergeTranslations(translations.en, {
  nav: {
    useCases: "Use Cases",
    reports: "Reports",
    tryDemo: "Start Scan",
    online: "Live System",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "From image signals to reviewable evidence. Minerva turns model outputs, metadata, provenance traces, and forensic signals into structured trust intelligence.",
    previewTitle: "Trust preview",
  },
  philosophy: {
    eyebrow: "Dusk Intelligence",
    title: "The owl of Minerva begins its flight only at dusk",
    body: "When generative AI blurs images, text, video, and voice, trust must move from intuition to evidence. Minerva turns provenance, metadata, model signals, and forensic traces into reviewable content trust intelligence.",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    useCases: "应用场景",
    reports: "报告",
    tryDemo: "开始检测",
    online: "实时系统",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "让 AI 时代的内容重新可信",
    lead: "从图像信号到可复核证据。Minerva 将模型输出、元数据、来源线索和取证信号转化为结构化可信判断。",
    previewTitle: "可信度预览",
  },
  philosophy: {
    eyebrow: "黄昏智慧",
    title: "密涅瓦的猫头鹰只在黄昏降临时才开始它的飞翔",
    body: "当生成式 AI 让图像、文本、视频和声音都变得难以分辨，可信判断必须从直觉转向证据。Minerva 以黄昏中的审慎智慧为隐喻，将来源、元数据、模型信号和取证特征组织成可复核的内容可信链。",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    online: "后端连接正常",
    apiError: "后端连接异常",
  },
  result: {
    reportCreated: "已生成报告，可在报告中心查看。report_id 可用于后续追踪：{id}",
    viewDetail: "查看详情",
    viewHtmlReport: "查看 HTML 报告",
    goReportCenter: "去报告中心",
    htmlOpenFailed: "HTML 报告打开失败，请稍后重试。",
    detectFailedFriendly: "检测失败，请确认后端已启动并重试。",
    reportCenterHint: "报告已写入 SQLite，刷新或重启后端后仍可在报告中心查看。",
  },
  reportCenter: {
    empty: "暂无报告，请先完成一次图片检测。可点击“开始检测”进入单图检测。",
    loadFailed: "报告记录加载失败，请确认后端服务已启动。",
    exportReady: "导出已开始。",
    exportFailed: "导出失败，请稍后重试。",
    exporting: "导出中...",
  },
  systemStatus: {
    eyebrow: "运行状态",
    title: "系统状态",
    description: "演示前检查后端、Reports API、SQLite 持久化和版本字段。",
    backend: "后端连接",
    reportsApi: "Reports API",
    database: "报告数据库",
    warmupReady: "模型预热",
    runtimeMode: "运行模式",
    loadedModels: "已加载模型",
    reportCount: "报告数量",
    schemaVersion: "报告结构版本",
    detectorVersion: "检测器版本",
    modelVersion: "模型版本",
    persistence: "SQLite 持久化",
    htmlReport: "HTML 报告",
    export: "导出能力",
    ok: "正常",
    error: "异常",
    enabled: "已启用",
    disabled: "未启用",
    loading: "检查中",
    unavailable: "不可用",
  },
});

mergeTranslations(translations.en, {
  result: {
    reportCreated: "Report generated. You can find it in Report Center. report_id for tracking: {id}",
    viewDetail: "View Detail",
    viewHtmlReport: "View HTML Report",
    goReportCenter: "Go to Report Center",
    htmlOpenFailed: "HTML report failed to open. Please try again.",
    detectFailedFriendly: "Detection failed. Check that the backend is running and try again.",
    reportCenterHint: "The report is stored in SQLite and remains available after refresh or backend restart.",
  },
  reportCenter: {
    empty: "No reports yet. Complete an image detection first.",
    exportReady: "Export started.",
    exportFailed: "Export failed. Please try again.",
    exporting: "Exporting...",
  },
  systemStatus: {
    eyebrow: "Runtime",
    title: "System Status",
    description: "Pre-demo check for backend, Reports API, SQLite persistence, and version fields.",
    backend: "Backend",
    reportsApi: "Reports API",
    database: "Report database",
    warmupReady: "Model warmup",
    runtimeMode: "Runtime mode",
    loadedModels: "Loaded models",
    reportCount: "Report count",
    schemaVersion: "Report schema version",
    detectorVersion: "Detector version",
    modelVersion: "Model version",
    persistence: "SQLite persistence",
    htmlReport: "HTML report",
    export: "Export",
    ok: "OK",
    error: "Error",
    enabled: "Enabled",
    disabled: "Disabled",
    loading: "Checking",
    unavailable: "Unavailable",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    product: "产品",
    useCases: "应用场景",
    trustConsole: "可信控制台",
    api: "API",
    reports: "报告",
    architecture: "架构",
    errorGallery: "错误图",
    tryDemo: "开始检测",
    refresh: "刷新",
    online: "后端连接正常",
    apiError: "后端连接异常",
  },
  hero: {
    previewTitle: "MVP 运行概览",
    previewPersistence: "SQLite 持久化",
    previewQueue: "待复核记录",
    previewApi: "Reports API",
    lead: "从图像信号到可复核证据。Minerva 将元数据、来源线索和取证信号转化为结构化可信判断。",
    runtimeReady: "就绪",
    runtimeOffline: "异常",
    exportReady: "可用",
  },
  demo: {
    eyebrow: "取证控制台",
    title: "上传图像并生成可信报告",
    description: "上传图片后，系统将生成检测结论、风险等级、证据摘要和可复核报告。",
    resultsEyebrow: "检测结果",
    resultsTitle: "可信风险评估",
    emptyJson: "完成检测后可查看结构化 JSON。",
  },
  workspace: {
    liveEyebrow: "取证工作区",
    liveTitle: "图像信号接入",
    liveBody: "上传图片后，系统将生成检测结论、风险等级、证据摘要和可复核报告。",
  },
  single: {
    detect: "检测图片",
    redetect: "重新检测",
    analyzing: "检测中...",
    scanning: "正在分析来源、元数据与图像取证特征...",
  },
  batch: {
    detect: "批量检测",
    redetect: "重新检测",
    analyzing: "批量检测中...",
  },
  result: {
    emptyTitle: "等待图像检测",
    emptyBody: "检测完成后将显示结论、置信度、风险等级和报告入口。",
    topVerdict: "检测结论",
    sourceEvidence: "来源证据",
    metadataAi: "元数据与 AI 标识",
    forensicFeatures: "图像取证特征",
    detectionOutput: "检测输出",
    reviewAdvice: "复核建议",
    evidenceSummary: "证据摘要",
    recommendation: "复核建议",
    reason: "判断依据",
    evidenceChain: "证据链",
    saved: "已生成报告",
    aiModelLayer: "检测输出",
    modelSignal: "检测输出",
    sourceProvenance: "来源证据",
    metadataLayer: "元数据与 AI 标识",
    forensicLayer: "图像取证特征",
    available: "可用",
    partial: "部分可用",
    notAvailableStatus: "当前不可用",
    exportPdf: "PDF 暂不支持",
    comingSoon: "MVP 暂不支持",
  },
  metrics: {
    aiBadge: "检测输出",
    avgConfidence: "历史平均置信度",
    avgConfidenceHint: "基于已保存报告统计",
    avgConfidenceBadge: "历史统计",
  },
  charts: {
    riskHint: "低 / 中 / 高",
    confidenceHint: "高 / 中 / 低",
  },
  architecture: {
    description: "Minerva 综合来源凭证、元数据、检测输出与传统取证特征，输出可审计结论。",
  },
  workflow: {
    detectBody: "结合元数据、取证特征、一致性检查和检测输出形成可复核结论。",
    reportBody: "围绕元数据、检测输出、取证特征和文件级证据形成报告上下文。",
    reviewBody: "面向误判反馈、复核备注和样本闭环，避免把单一检测结果作为唯一依据。",
  },
  philosophy: {
    body: "当生成式 AI 让图像、文本、视频和声音都变得难以分辨，可信判断必须从直觉转向证据。Minerva 将来源、元数据、检测输出和取证特征组织成可复核的内容可信链。",
  },
  reportCenter: {
    title: "报告中心",
    subtitle: "检索、筛选、排序、导出和复核已保存的检测报告。",
  },
});

mergeTranslations(translations.en, {
  hero: {
    previewTitle: "MVP runtime",
    previewPersistence: "SQLite persistence",
    previewQueue: "Pending review",
    previewApi: "Reports API",
    runtimeReady: "Ready",
    runtimeOffline: "Offline",
    exportReady: "Available",
  },
  demo: {
    eyebrow: "Forensic Console",
    title: "Upload an image and generate a trust report",
    description: "After upload, the system produces a verdict, risk level, evidence summary, and reviewable report.",
    resultsEyebrow: "Detection result",
    resultsTitle: "Trust risk assessment",
    emptyJson: "Run a detection to view structured JSON.",
  },
  workspace: {
    liveEyebrow: "Forensic workspace",
    liveTitle: "Image signal intake",
    liveBody: "Upload an image to generate a verdict, risk level, evidence summary, and reviewable report.",
  },
  single: {
    redetect: "Run Again",
  },
  batch: {
    redetect: "Run Again",
  },
  result: {
    emptyTitle: "Waiting for image detection",
    emptyBody: "After detection, verdict, confidence, risk level, and report actions will appear here.",
    sourceEvidence: "Source evidence",
    metadataAi: "Metadata and AI markers",
    forensicFeatures: "Image forensic features",
    detectionOutput: "Detection output",
    reviewAdvice: "Review recommendation",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    product: "产品",
    useCases: "场景",
    trustConsole: "取证控制台",
    api: "API",
    reports: "报告",
    architecture: "架构",
    errorGallery: "错误图库",
    tryDemo: "开始检测",
    refresh: "刷新",
    refreshing: "刷新中",
    syncing: "同步中",
    checking: "检查中",
    online: "后端连接正常",
    apiError: "后端连接异常",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "让 AI 时代的内容重新可信",
    lead: "从图像信号到可复核证据。Minerva 将模型输出、元数据、来源线索和取证信号转化为结构化可信判断。",
    startScan: "开始可信检测",
    exploreConsole: "查看控制台",
    previewTitle: "可信度预览",
    previewPersistence: "证据层",
    previewQueue: "复核队列",
    previewApi: "本地 API 路径",
    runtimeReady: "Ready",
    runtimeOffline: "--",
    exportReady: "JSON",
  },
  demo: {
    eyebrow: "取证扫描工作台",
    title: "Minerva 图像可信取证控制台",
    description: "接入图像信号，提取取证线索，生成证据摘要，并输出适合人工复核的可信性判定。",
    uploadTab: "单图",
    batchTab: "批量",
    sampleTab: "样例",
    resultsEyebrow: "可信性判定",
    resultsTitle: "Verdict Dossier",
    simpleView: "摘要",
    jsonView: "JSON",
    emptyJson: "完成检测后可查看结构化 JSON。",
  },
  workspace: {
    liveEyebrow: "取证工作区",
    liveTitle: "Evidence Map",
    liveBody: "围绕上传图像建立可复核的取证路径：分析图像信号、提取取证线索、生成证据摘要、输出复核建议。",
    capabilityOne: "分析图像信号",
    capabilityTwo: "提取取证线索",
    capabilityThree: "输出复核建议",
  },
  single: {
    title: "图像信号接入",
    description: "将单张图像送入当前检测链路。",
    choose: "选择图像",
    formats: "支持 JPG / JPEG / PNG / WEBP",
    detect: "开始取证扫描",
    redetect: "重新检测",
    analyzing: "分析中",
    analyzingImage: "正在分析图像",
    release: "松开以上传图像",
    remove: "移除图像",
    invalidType: "请上传 JPG、JPEG、PNG 或 WEBP 图像。",
    scanning: "正在分析图像信号、来源线索与取证特征。",
  },
  batch: {
    title: "批量图像接入",
    description: "使用批量接口分析多张图像。",
    choose: "选择多张图像",
    empty: "尚未选择图像",
    selected: "已选择 {count} 张图像",
    detect: "批量取证扫描",
    redetect: "重新检测",
    analyzing: "批量分析中",
    analyzingImages: "正在分析 {count} 张图像",
    complete: "批量检测完成",
    succeeded: "{succeeded} 成功，{failed} 失败",
    release: "松开以上传批量图像",
    clear: "清空全部",
    more: "+{count}",
    invalidType: "已忽略不支持的文件，请只上传图像。",
    summaryTitle: "批量检测摘要",
    total: "Total",
    ai: "AI",
    uncertain: "Uncertain",
    highRisk: "High Risk",
    avgConfidence: "Average Confidence",
  },
  result: {
    emptyTitle: "等待图像检测",
    emptyBody: "检测完成后将显示结论、置信度、风险等级和报告入口。",
    loading: "Minerva 正在生成证据摘要",
    failed: "检测失败",
    singleComplete: "单图检测完成",
    batchComplete: "批量检测完成",
    topVerdict: "检测结论",
    verdict: "结论",
    riskLevel: "风险等级",
    confidence: "置信度",
    status: "状态",
    saved: "已生成报告",
    evidenceSummary: "证据摘要",
    sourceProvenance: "来源证据",
    metadataLayer: "元数据与 AI 标识",
    aiModelLayer: "检测输出",
    modelSignal: "检测输出",
    forensicLayer: "图像取证特征",
    recommendation: "复核建议",
    reason: "判断依据",
    evidenceChain: "证据链",
    exportJson: "导出 JSON",
    copyJson: "复制 JSON",
    exportPdf: "PDF 暂不支持",
    comingSoon: "暂不支持",
    notAvailable: "当前暂无可用证据",
    available: "可用",
    partial: "部分可用",
    notAvailableStatus: "当前不可用",
    reportCreated: "已生成报告，可在报告中心查看。report_id：{id}",
    viewDetail: "查看详情",
    viewHtmlReport: "查看 HTML 报告",
    goReportCenter: "去报告中心",
    htmlOpenFailed: "HTML 报告打开失败，请稍后重试。",
    detectFailedFriendly: "检测失败，请确认后端已启动后重试。",
    reportCenterHint: "报告已写入 SQLite，刷新或重启后端后仍可在报告中心查看。",
  },
  reportCenter: {
    eyebrow: "Case Repository",
    title: "报告中心",
    description: "集中管理检测记录、证据摘要和人工复核状态。",
    empty: "暂无报告记录，请先完成一次图像检测。",
    loadFailed: "报告记录加载失败，请确认后端服务已启动。",
    exportReady: "导出已开始。",
    exportFailed: "导出失败，请稍后重试。",
    exporting: "导出中",
    queueEmpty: "暂无需要复核的记录。",
    summary: {
      total: "总数",
      filtered: "筛选",
      pending: "待复核",
      highRisk: "高风险",
      uncertain: "不确定",
    },
    queue: {
      title: "风险复核队列",
      subtitle: "高风险 / 不确定 / 待复核记录",
    },
  },
  systemStatus: {
    eyebrow: "运行状态",
    title: "系统状态",
    description: "后端、Reports API、报告数据库和导出能力的轻量状态矩阵。",
    backend: "后端连接",
    reportsApi: "Reports API",
    database: "报告数据库",
    reportCount: "报告数量",
    schemaVersion: "报告结构版本",
    detectorVersion: "检测器版本",
    modelVersion: "模型版本",
    persistence: "SQLite 持久化",
    htmlReport: "HTML 报告",
    export: "导出能力",
    ok: "正常",
    error: "异常",
    enabled: "已启用",
    disabled: "未启用",
    loading: "检查中",
    unavailable: "不可用",
  },
  roadmap: {
    eyebrow: "产品路线图",
    title: "从图像取证到多模态可信检测",
    description: "当前 MVP 聚焦图像检测，后续扩展到视频、文本、语音和多模态报告。",
    image: "图像",
    video: "视频",
    text: "文本",
    audio: "语音",
    report: "多模态报告",
  },
  story: {
    eyebrow: "Why Minerva",
    title: "为什么选择 Minerva",
    evidenceTitle: "Evidence-first detection",
    evidenceBody: "不只判断真假，而是形成可复核的证据链。",
    apiTitle: "SaaS & API path",
    apiBody: "支持网页检测、批量检测和开发者接口。",
    complianceTitle: "Compliance-aware",
    complianceBody: "面向生成式内容标识、来源凭证和企业审计场景。",
    reviewTitle: "Human review friendly",
    reviewBody: "输出复核建议，避免把模型结果作为唯一处置依据。",
  },
});

mergeTranslations(translations.en, {
  nav: {
    product: "Product",
    useCases: "Scenarios",
    trustConsole: "Trust Console",
    api: "API",
    reports: "Reports",
    architecture: "Architecture",
    errorGallery: "Error Gallery",
    tryDemo: "Start Scan",
    refresh: "Refresh",
    online: "Live System",
  },
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "From image signals to reviewable evidence. Minerva turns model output, metadata, source traces, and forensic signals into structured trust decisions.",
    startScan: "Start Trusted Scan",
    exploreConsole: "View Console",
    previewTitle: "Trust Preview",
    previewPersistence: "Evidence Layers",
    previewQueue: "Review Queue",
    previewApi: "Local API path",
    runtimeReady: "Ready",
    exportReady: "JSON",
  },
  demo: {
    eyebrow: "Forensic Scanner Workbench",
    title: "Minerva Image Trust Console",
    description: "Intake image signals, extract forensic traces, generate evidence summaries, and produce human-review friendly verdicts.",
    uploadTab: "Single",
    batchTab: "Batch",
    sampleTab: "Sample",
    resultsEyebrow: "Trust Verdict",
    resultsTitle: "Verdict Dossier",
    simpleView: "Summary",
    jsonView: "JSON",
  },
  workspace: {
    liveEyebrow: "Evidence Map",
    liveTitle: "Forensic workspace",
    liveBody: "Build a reviewable evidence path around each image: analyze image signals, extract forensic traces, generate evidence summaries, and output review guidance.",
    capabilityOne: "Analyze image signals",
    capabilityTwo: "Extract forensic traces",
    capabilityThree: "Output review guidance",
  },
  single: {
    title: "Image Signal Intake",
    description: "Run one image through the current detection chain.",
    detect: "Start Forensic Scan",
    redetect: "Run Again",
    scanning: "Analyzing image signals, source traces, and forensic features.",
  },
  batch: {
    title: "Batch Image Intake",
    description: "Analyze multiple images with the batch endpoint.",
    detect: "Batch Forensic Scan",
    redetect: "Run Again",
    summaryTitle: "Batch Scan Summary",
    total: "Total",
    ai: "AI",
    uncertain: "Uncertain",
    highRisk: "High Risk",
    avgConfidence: "Average Confidence",
  },
  reportCenter: {
    eyebrow: "Case Repository",
    title: "Case Repository",
    description: "Search, review, and export structured detection records.",
    queue: {
      title: "Risk Review Queue",
      subtitle: "High risk / uncertain / pending review records",
    },
  },
  systemStatus: {
    description: "Lightweight status matrix for backend, Reports API, database, and export capability.",
  },
  roadmap: {
    eyebrow: "Product Roadmap",
    title: "From Image Forensics to Multimodal Trust Detection",
    description: "The current MVP starts with image-first evidence, then expands toward video, text, voice, and multimodal reports.",
    image: "Image",
    video: "Video",
    text: "Text",
    audio: "Voice",
    report: "Multimodal Report",
  },
  story: {
    eyebrow: "Why Minerva",
    title: "Why Minerva",
    evidenceTitle: "Evidence-first detection",
    evidenceBody: "Not just a binary truth label, but a reviewable evidence chain.",
    apiTitle: "SaaS & API path",
    apiBody: "Supports web detection, batch detection, and developer APIs.",
    complianceTitle: "Compliance-aware",
    complianceBody: "Built for synthetic content labeling, provenance credentials, and enterprise audit workflows.",
    reviewTitle: "Human review friendly",
    reviewBody: "Outputs review guidance so model results are not treated as the only enforcement basis.",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    product: "产品",
    trustConsole: "可信控制台",
    evidence: "证据",
    reports: "报告",
    architecture: "架构",
    errorGallery: "错误图库",
  },
  hero: {
    title: "AI 图像可信与取证控制台",
    titleZh: "证据优先的检测、复核与报告系统",
    lead: "Minerva 将模型输出、来源线索、元数据和取证信号汇总成可复核的可信判断。",
    previewTitle: "运行状态",
    previewPersistence: "证据层",
    previewQueue: "复核队列",
    previewApi: "本地 API 路径",
    runtimeReady: "就绪",
    runtimeWarming: "预热中",
    runtimeOffline: "离线",
    exportReady: "JSON",
  },
  systemStatus: {
    warmupReady: "模型预热",
    runtimeMode: "运行模式",
    loadedModels: "已加载模型",
  },
});

mergeTranslations(translations.en, {
  nav: {
    product: "Product",
    trustConsole: "Trust Console",
    evidence: "Evidence",
    reports: "Reports",
    architecture: "Architecture",
    errorGallery: "Error Gallery",
  },
  hero: {
    title: "AI Image Trust & Forensics Console",
    titleZh: "Evidence-first detection, review, and reporting",
    lead: "Minerva turns model output, source traces, metadata, and forensic signals into reviewable trust decisions.",
    previewTitle: "Runtime",
    previewPersistence: "Evidence Layers",
    previewQueue: "Review Queue",
    previewApi: "Local API path",
    runtimeReady: "Ready",
    runtimeWarming: "Warming",
    runtimeOffline: "Offline",
    exportReady: "JSON",
  },
  systemStatus: {
    warmupReady: "Model warmup",
    runtimeMode: "Runtime mode",
    loadedModels: "Loaded models",
  },
  calibration: {
    eyebrow: "P2 Calibration",
    title: "Review, Stress & Train Readiness",
    description: "Shows whether review labels, policy replay, scenario stress packs, and local training manifests are ready for improvement.",
    labels: "Reviewed labels",
    replay: "Policy replay",
    stress: "Stress pack",
    training: "Training set",
    recommendation: "Recommendation",
    waiting: "Waiting for cached P2 reports.",
    unavailable: "Calibration readiness is unavailable.",
    needsLabels: "Needs labels",
    cached: "Cached",
    live: "Live",
    ready: "Ready",
    noRecommendation: "No profile recommendation yet",
    labelGap: "Add reviewed labels on current detector reports to make policy replay and local training actionable.",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    evidence: "证据",
  },
  hero: {
    title: "AI 图像可信取证控制台",
    titleZh: "面向生成式内容风险的证据链",
    lead: "可复核的图像风险结论。",
    previewTitle: "实时运行态",
    previewPersistence: "证据层",
    previewQueue: "复核队列",
    previewApi: "本地 API 路径",
    runtimeReady: "就绪",
    exportReady: "JSON",
  },
  systemStatus: {
    warmupReady: "模型预热",
    runtimeMode: "运行模式",
    loadedModels: "已加载模型",
  },
  calibration: {
    eyebrow: "P2 校准",
    title: "复核、压力集与训练就绪",
    description: "展示复核标签、策略复盘、场景压力集和本地训练清单是否已具备优化价值。",
    labels: "已标注样本",
    replay: "策略复盘",
    stress: "压力集",
    training: "训练集",
    recommendation: "建议",
    waiting: "等待 P2 缓存报告。",
    unavailable: "校准状态不可用。",
    needsLabels: "需要标签",
    cached: "缓存",
    live: "实时",
    ready: "就绪",
    noRecommendation: "暂无 profile 推荐",
    labelGap: "请在当前检测器生成的新报告上补充人工复核标签，策略复盘和本地训练才可用于优化。",
  },
});

mergeTranslations(translations.en, {
  nav: {
    evidence: "Evidence",
  },
  hero: {
    title: "AI Image Trust & Forensics Console",
    titleZh: "Evidence chain for generated media risk",
    lead: "Minerva turns provenance, metadata, detector signals, and policy rules into reviewable trust risk decisions.",
    previewTitle: "Runtime",
    previewPersistence: "Evidence Layers",
    previewQueue: "Review Queue",
    previewApi: "Local API path",
    runtimeReady: "Ready",
    exportReady: "JSON",
  },
  systemStatus: {
    warmupReady: "Model warmup",
    runtimeMode: "Runtime mode",
    loadedModels: "Loaded models",
  },
});

mergeTranslations(translations.zh, {
  policyProfile: {
    label: "策略",
    strictSafe: "标准安全",
    highRecall: "高召回复核",
  },
});

mergeTranslations(translations.en, {
  policyProfile: {
    label: "Policy",
    strictSafe: "Strict Safe",
    highRecall: "High Recall",
  },
});

mergeTranslations(translations.en, {
  reportCenter: {
    trainingQueue: {
      title: "Training Label Queue",
      subtitle: "File-ready reports that can unlock local training",
      empty: "No file-ready reports are waiting for training labels.",
      failed: "Training label queue failed to load.",
      needAi: "Need AI labels",
      needReal: "Need real labels",
      needEither: "Needs AI or real label",
      gap: "Need {ai} AI / {real} real",
      suggested: "Suggested",
      markAi: "Confirm AI",
      markReal: "Confirm Real",
      saved: "Saved",
      saveFailed: "Save failed",
      rebuilding: "Rebuilding",
      rebuild: "Rebuild",
      rebuildDone: "Rebuilt",
    },
  },
});

function resolveInitialPolicyProfile() {
  try {
    const saved = String(localStorage.getItem("minerva.policyProfile") || "").trim();
    if (["strict_safe_plus", "high_recall_review"].includes(saved)) {
      return saved;
    }
  } catch {
    // Storage can be unavailable in file/private contexts.
  }
  return "strict_safe_plus";
}

const state = {
  dashboardLoading: false,
  singleLoading: false,
  batchLoading: false,
  singleStatus: "idle",
  selectedSingleFile: null,
  selectedBatchFiles: [],
  selectedSingleObjectUrl: null,
  selectedBatchObjectUrls: [],
  singleDragDepth: 0,
  batchDragDepth: 0,
  lang: resolveInitialLanguage(),
  currentResult: null,
  recentResults: new Map(),
  recentAllResults: [],
  recentFilter: "all",
  reportFilters: {
    q: "",
    risk_level: "all",
    final_label: "all",
    review_status: "all",
    date_range: "all",
    confidence_range: "all",
    sort: "newest",
  },
  reportQueue: [],
  trainingLabelQueue: null,
  calibrationReadiness: null,
  reportSearchTimer: 0,
  systemHealth: null,
  exportLoading: false,
  demoTab: "upload",
  resultView: "simple",
  policyProfile: resolveInitialPolicyProfile(),
  policyProfiles: [],
  prefersReducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
};

const elements = {
  refreshButton: document.querySelector("#refresh-button"),
  serviceStatus: document.querySelector("#service-status"),
  serviceStatusText: document.querySelector("#service-status-text"),
  chartUpdatedAt: document.querySelector("#chart-updated-at"),
  recentCount: document.querySelector("#recent-count"),
  recentBody: document.querySelector("#recent-results-body"),
  recentEmptyState: document.querySelector("#recent-empty-state"),
  auditFilters: document.querySelector("#audit-filters"),
  reportSummaryStrip: document.querySelector("#report-summary-strip"),
  systemStatusGrid: document.querySelector("#system-status-grid"),
  calibrationReadinessGrid: document.querySelector("#calibration-readiness-grid"),
  calibrationReadinessNote: document.querySelector("#calibration-readiness-note"),
  heroBackendMetric: document.querySelector('[data-hero-metric="backend"]'),
  heroReportsMetric: document.querySelector('[data-hero-metric="reports"]'),
  heroReviewMetric: document.querySelector('[data-hero-metric="review"]'),
  heroExportMetric: document.querySelector('[data-hero-metric="export"]'),
  reportSearchInput: document.querySelector("#report-search-input"),
  reportRiskFilter: document.querySelector("#report-risk-filter"),
  reportLabelFilter: document.querySelector("#report-label-filter"),
  reportReviewFilter: document.querySelector("#report-review-filter"),
  reportDateFilter: document.querySelector("#report-date-filter"),
  reportConfidenceFilter: document.querySelector("#report-confidence-filter"),
  reportSortFilter: document.querySelector("#report-sort-filter"),
  reportResetButton: document.querySelector("#report-reset-button"),
  reviewQueueList: document.querySelector("#review-queue-list"),
  reviewQueueCount: document.querySelector("#review-queue-count"),
  trainingLabelQueueList: document.querySelector("#training-label-queue-list"),
  trainingLabelQueueCount: document.querySelector("#training-label-queue-count"),
  trainingLabelQueueGap: document.querySelector("#training-label-queue-gap"),
  labelChart: document.querySelector("#label-chart"),
  riskChart: document.querySelector("#risk-chart"),
  confidenceChart: document.querySelector("#confidence-chart"),
  singleInput: document.querySelector("#single-file-input"),
  batchInput: document.querySelector("#batch-file-input"),
  singleFileLabel: document.querySelector("#single-file-label"),
  singleFileMeta: document.querySelector("#single-file-meta"),
  batchFileLabel: document.querySelector("#batch-file-label"),
  batchFileMeta: document.querySelector("#batch-file-meta"),
  singleDropZone: document.querySelector("#single-drop-zone"),
  batchDropZone: document.querySelector("#batch-drop-zone"),
  singleUploadCard: document.querySelector("#single-upload-card"),
  batchUploadCard: document.querySelector("#batch-upload-card"),
  singlePreview: document.querySelector("#single-file-preview"),
  batchPreview: document.querySelector("#batch-file-preview"),
  singleButton: document.querySelector("#single-detect-button"),
  navDetectButton: document.querySelector(".nav-demo-button"),
  batchButton: document.querySelector("#batch-detect-button"),
  uploadResult: document.querySelector("#upload-result"),
  demoTabs: document.querySelector("#demo-tabs"),
  resultViewToggle: document.querySelector("#result-view-toggle"),
  policyProfileSwitch: document.querySelector("#policy-profile-switch"),
  trustParticles: document.querySelector("#trust-particles"),
  trustWorkbench: document.querySelector("[data-trust-workbench]"),
  scanStateRail: document.querySelector("#scan-state-rail"),
};

function resolveInitialLanguage() {
  const saved = localStorage.getItem("minerva.lang");
  if (saved === "zh" || saved === "en") {
    return saved;
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function t(path, params = {}) {
  const value = String(path)
    .split(".")
    .reduce((current, key) => (current && current[key] !== undefined ? current[key] : undefined), translations[state.lang]);
  const fallback = value === undefined ? path : String(value);
  return Object.entries(params).reduce((text, [key, replacement]) => text.replaceAll(`{${key}}`, replacement), fallback);
}

function applyI18n() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  });
  document.querySelectorAll(".language-button").forEach((button) => {
    const isActive = button.dataset.lang === state.lang;
    button.textContent = button.dataset.lang === "zh" ? "中文" : "English";
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  renderPolicyProfileSwitch();
  setUploadButtons();
  updateFileLabels();
  renderBatchPreview();
  if (state.selectedSingleFile) {
    renderSinglePreview(state.selectedSingleFile);
  }
  if (!state.currentResult) {
    renderEmptyResult();
  } else if (state.currentResult.kind === "single") {
    renderSingleResult(state.currentResult.payload);
  } else if (state.currentResult.kind === "batch") {
    renderBatchResult(state.currentResult.payload);
  }
  if (state.recentAllResults.length) {
    renderRecentRows(filteredRecentResults(), filteredRecentResults().length);
  }
  if (state.reportQueue.length) {
    renderReviewQueue({ items: state.reportQueue, total: state.reportQueue.length });
  }
  if (state.trainingLabelQueue) {
    renderTrainingLabelQueue(state.trainingLabelQueue);
  }
  if (state.calibrationReadiness) {
    renderCalibrationReadiness(state.calibrationReadiness);
  }
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

function formatNumber(value, digits = 2) {
  const number = toNumber(value, NaN);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return number.toFixed(digits);
}

function formatConfidence(value) {
  const number = toNumber(value, NaN);
  if (!Number.isFinite(number)) {
    return "--";
  }
  const normalized = number > 1 && number <= 100 ? number / 100 : number;
  return `${Math.round(Math.max(0, Math.min(1, normalized)) * 100)}%`;
}

function formatFileSize(bytes) {
  const value = toNumber(bytes, 0);
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(2)} MB`;
  }
  return `${Math.max(1, Math.round(value / 1024))} KB`;
}

function fileFormat(file) {
  const ext = String(file?.name || "").split(".").pop()?.toUpperCase();
  if (ext) {
    return ext;
  }
  return String(file?.type || "image").replace("image/", "").toUpperCase();
}

function isSupportedImage(file) {
  const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
  const allowedExtensions = [".jpg", ".jpeg", ".png", ".webp"];
  const name = String(file?.name || "").toLowerCase();
  return allowedTypes.includes(file?.type) || allowedExtensions.some((extension) => name.endsWith(extension));
}

function supportedImages(files) {
  return Array.from(files || []).filter(isSupportedImage);
}

function flashUploadError(card, message) {
  if (!card) {
    return;
  }
  card.classList.add("has-upload-error");
  card.dataset.uploadError = message;
  window.setTimeout(() => {
    card.classList.remove("has-upload-error");
    delete card.dataset.uploadError;
  }, 3600);
}

function formatTimestamp(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString(state.lang === "zh" ? "zh-CN" : undefined, {
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

function labelKey(value) {
  const label = String(value || "unknown").trim().toLowerCase();
  if (["ai", "ai_generated", "likely_ai", "generated"].includes(label)) {
    return label === "ai" ? "ai" : "ai_generated";
  }
  if (["real", "real_photo", "likely_real", "authentic"].includes(label)) {
    return "real";
  }
  if (["low", "medium", "high", "unknown", "failed"].includes(label)) {
    return label;
  }
  return "uncertain";
}

function displayLabel(value) {
  return t(`labels.${labelKey(value)}`);
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

function textFromValue(value, fallback = "--") {
  if (Array.isArray(value)) {
    return value.map((item) => textFromValue(item, "")).filter(Boolean).join("; ") || fallback;
  }
  if (value && typeof value === "object") {
    return firstDefined(value.message, value.action, value.code, JSON.stringify(value), fallback);
  }
  return String(firstDefined(value, fallback));
}

function resultSummaryText(item) {
  return textFromValue(firstDefined(item.user_facing_summary, item.summary, item.decision_reason, item.recommendation), "--");
}

function normalizeRiskKey(value) {
  const risk = String(value || "").trim().toLowerCase().replaceAll("-", "_");
  if (["high", "very_high", "critical"].includes(risk)) return "high";
  if (["medium", "moderate"].includes(risk)) return "medium";
  if (["low", "minimal"].includes(risk)) return "low";
  return "unknown";
}

function normalizeVerdictKey(value) {
  const label = String(value || "").trim().toLowerCase().replaceAll("-", "_");
  if (["ai", "ai_generated", "ai generated", "likely_ai", "generated", "synthetic", "artificial"].includes(label)) return "ai";
  if (["real", "real_photo", "likely_real", "authentic", "photo", "camera"].includes(label)) return "real";
  if (["uncertain", "unsure", "review", "undetermined"].includes(label)) return "uncertain";
  return "unknown";
}

function normalizeReviewStatusKey(value) {
  const status = String(value || "pending_review").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  const allowed = ["unreviewed", "pending_review", "reviewed", "confirmed_ai", "confirmed_real", "false_positive", "false_negative", "needs_recheck", "needs_follow_up", "ignored"];
  return allowed.includes(status) ? status : "pending_review";
}

function getRiskLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = normalizeRiskKey(value);
  return translations[lang]?.reportCenter?.risk?.[key] || t(`reportCenter.risk.${key}`);
}

function getRiskTone(value) {
  return normalizeRiskKey(value);
}

function getVerdictLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = normalizeVerdictKey(value);
  return translations[lang]?.reportCenter?.verdict?.[key] || t(`reportCenter.verdict.${key}`);
}

function getReviewStatusLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = normalizeReviewStatusKey(value);
  return translations[lang]?.reportCenter?.review?.[key] || t(`reportCenter.review.${key}`);
}

function getSortLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = String(value || "newest");
  return translations[lang]?.reportCenter?.sort?.[key] || t(`reportCenter.sort.${key}`);
}

function getDateRangeLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = String(value || "all");
  return translations[lang]?.reportCenter?.date?.[key] || t(`reportCenter.date.${key}`);
}

function getConfidenceRangeLabel(value, locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  const key = value === "0_5_0_8" ? "mid" : String(value || "all");
  return translations[lang]?.reportCenter?.confidence?.[key] || t(`reportCenter.confidence.${key}`);
}

function getReportSearchPlaceholder(locale = state.lang) {
  const lang = locale === "zh" ? "zh" : "en";
  return translations[lang]?.reportCenter?.filters?.searchPlaceholder || t("reportCenter.filters.searchPlaceholder");
}

function reportFilterParams(extra = {}) {
  const params = new URLSearchParams();
  const filters = { ...state.reportFilters, ...extra };
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, value);
    }
  });
  return params;
}

function reportSearchUrl(extra = {}) {
  const params = reportFilterParams({ limit: 100, offset: 0, ...extra });
  return apiUrl(`/api/v1/reports?${params.toString()}`);
}

function reportExportUrl(format) {
  const params = reportFilterParams({ format, limit: 500, offset: 0 });
  return `${API_ENDPOINTS.reportExport}?${params.toString()}`;
}

function timestampForFilename() {
  const date = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function buildSingleDetectionFormData(file) {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
}

async function waitForScanReady({ timeoutMs = 120000, intervalMs = 1500 } = {}) {
  const started = Date.now();
  let lastHealth = null;
  let lastProbeError = null;
  while (Date.now() - started <= timeoutMs) {
    try {
      lastHealth = await ensureApiBaseReachable({ timeoutMs: 5000, force: true });
      lastProbeError = null;
      state.systemHealth = lastHealth;
      renderSystemStatus(lastHealth, false, state.modelStatus);
      if (lastHealth?.warmup_ready !== false) {
        return lastHealth;
      }
      renderLoadingResult(statusCopy("warmupWaiting"));
    } catch (error) {
      lastProbeError = error;
      renderLoadingResult(statusCopy("backendReconnectWaiting"));
    }
    await sleep(intervalMs);
  }
  const message = state.lang === "zh"
    ? "模型预热仍未完成，请确认后端日志没有报错后重试。"
    : "Model warmup is still not complete. Check the backend logs and retry.";
  const error = new Error(message);
  error.payload = lastHealth;
  error.cause = lastProbeError;
  throw error;
}

async function fetchJson(url, options = {}) {
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      ...fetchOptions,
      signal: fetchOptions.signal || controller.signal,
      headers: {
        Accept: "application/json",
        ...authHeaders(),
        ...(fetchOptions.headers || {}),
      },
    });
  } catch (error) {
    const message = error.name === "AbortError"
      ? `Request timed out after ${Math.round(timeoutMs / 1000)}s while waiting for ${url}. Check the FastAPI terminal logs or retry.`
      : error instanceof TypeError
      ? `Backend is not connected. Confirm FastAPI is running at ${API_BASE_URL}. A browser CORS block can also appear as a network failure.`
      : (error.message || "Network request failed.");
    const wrapped = new Error(message);
    wrapped.status = 0;
    wrapped.cause = error;
    throw wrapped;
  } finally {
    window.clearTimeout(timeoutId);
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail = getValue(payload, "error.message", getValue(payload, "detail", response.statusText));
    let hint = "";
    if (response.status === 404) {
      hint = " API path was not found; check the dashboard endpoint configuration.";
    } else if (response.status === 422) {
      hint = " Request format was rejected; check multipart/form-data and the file field name.";
    } else if (response.status >= 500) {
      hint = " Backend detector failed; check the FastAPI terminal for details.";
    }
    const error = new Error(`${response.status} ${detail || response.statusText}${hint}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function isRetryableSingleDetectionError(error) {
  const status = Number(error?.status || 0);
  const message = `${error?.message || ""} ${JSON.stringify(error?.payload || {})}`.toLowerCase();
  return (
    status === 0
    || status === 502
    || status === 503
    || status === 504
    || (
      status >= 500
      && (
        message.includes("warmup")
        || message.includes("cold")
        || message.includes("not loaded")
        || message.includes("timeout")
        || message.includes("temporarily")
        || message.includes("connection")
      )
    )
  );
}

async function postSingleDetectionWithRetry(singleUrl, file) {
  const requestOptions = {
    method: "POST",
    // The backend default is 240s. The browser waits a little longer so the
    // server can return a structured product error instead of a network abort.
    timeoutMs: 300000,
  };
  const retryRequestOptions = {
    ...requestOptions,
    // A retry is meant to bridge a warmup/reconnect race, not double the
    // maximum wait. If the backend still cannot answer, surface the failure.
    timeoutMs: 120000,
  };
  try {
    return await fetchJson(singleUrl, {
      ...requestOptions,
      body: buildSingleDetectionFormData(file),
    });
  } catch (error) {
    if (!isRetryableSingleDetectionError(error)) {
      throw error;
    }
    renderLoadingResult(statusCopy("retryingConnection"));
    await sleep(1200);
    await waitForScanReady({ timeoutMs: 45000, intervalMs: 1500 });
    return await fetchJson(singleUrl, {
      ...retryRequestOptions,
      body: buildSingleDetectionFormData(file),
    });
  }
}

function setServiceStatus(status, label) {
  elements.serviceStatus.dataset.status = status;
  const normalized = String(status || "").toLowerCase();
  const fullLabel = String(label || "");
  const compactLabel = ["offline", "error"].includes(normalized) && /backend|fastapi|api/i.test(fullLabel)
    ? t("nav.apiError")
    : fullLabel;
  elements.serviceStatus.title = fullLabel;
  elements.serviceStatusText.textContent = compactLabel;
  if (!state.singleLoading && !state.currentResult) {
    if (["offline", "error"].includes(normalized)) {
      updateConsoleScanState("offline");
    } else if (normalized === "online") {
      updateConsoleScanState(state.selectedSingleFile ? "ready" : "idle");
    }
  }
}

function updateConsoleScanState(status) {
  const allowed = ["offline", "idle", "ready", "scanning", "success", "review", "error"];
  const normalized = allowed.includes(String(status || "").toLowerCase()) ? String(status).toLowerCase() : "idle";
  document.body.dataset.scanState = normalized;
  elements.trustWorkbench?.setAttribute("data-scan-state", normalized);
  const activeOrder = {
    offline: ["idle"],
    idle: ["idle"],
    ready: ["idle", "ready"],
    scanning: ["idle", "ready", "scanning"],
    success: ["idle", "ready", "scanning", "review"],
    review: ["idle", "ready", "scanning", "review"],
    error: ["idle", "ready", "scanning", "review"],
  };
  const activeSteps = activeOrder[normalized] || activeOrder.idle;
  elements.scanStateRail?.querySelectorAll("[data-scan-step]").forEach((node) => {
    const active = activeSteps.includes(node.dataset.scanStep);
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-current", active && node.dataset.scanStep === activeSteps[activeSteps.length - 1] ? "step" : "false");
  });
}

function setSummaryValue(key, value) {
  const node = document.querySelector(`[data-summary-key="${key}"]`);
  if (node) {
    node.textContent = value;
  }
}

function setUploadButtons() {
  const singleDisabled = state.singleLoading || !state.selectedSingleFile;
  const singleLabel = singleActionLabel();
  elements.singleButton.disabled = singleDisabled;
  elements.batchButton.disabled = state.batchLoading || state.selectedBatchFiles.length === 0;
  const singleComplete = state.currentResult?.kind === "single" && Boolean(state.selectedSingleFile);
  const batchComplete = state.currentResult?.kind === "batch" && state.selectedBatchFiles.length > 0;
  elements.singleButton.textContent = singleLabel;
  elements.singleButton.hidden = !state.selectedSingleFile;
  elements.navDetectButton?.setAttribute("aria-disabled", state.singleLoading ? "true" : "false");
  if (elements.navDetectButton) {
    elements.navDetectButton.textContent = state.selectedSingleFile ? singleLabel : t("nav.tryDemo");
  }
  elements.batchButton.textContent = state.batchLoading ? t("batch.analyzing") : batchComplete ? t("batch.redetect") : t("batch.detect");
  elements.singleUploadCard?.classList.toggle("is-analyzing", state.singleLoading);
  elements.batchUploadCard?.classList.toggle("is-analyzing", state.batchLoading);
  elements.singleUploadCard?.classList.toggle("has-file", Boolean(state.selectedSingleFile));
  elements.batchUploadCard?.classList.toggle("has-file", state.selectedBatchFiles.length > 0);
  elements.singlePreview?.querySelectorAll("[data-action='run-single-detection']").forEach((button) => {
    button.textContent = singleLabel;
    button.disabled = singleDisabled;
  });
}

function renderPolicyProfileSwitch() {
  const switcher = elements.policyProfileSwitch;
  if (!switcher) return;
  switcher.querySelectorAll("[data-policy-profile]").forEach((button) => {
    const profile = button.dataset.policyProfile;
    const active = profile === state.policyProfile;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    const remote = state.policyProfiles.find((item) => item.name === profile);
    const burden = remote?.review_burden;
    button.title = burden === "high"
      ? (state.lang === "zh" ? "提高召回，增加人工复核量" : "Higher recall, more human review")
      : (state.lang === "zh" ? "默认产品安全策略" : "Default product safety policy");
  });
}

function setPolicyProfile(profile) {
  const normalized = String(profile || "").trim().toLowerCase().replace(/-/g, "_");
  if (!["strict_safe_plus", "high_recall_review"].includes(normalized)) {
    return;
  }
  state.policyProfile = normalized;
  try {
    localStorage.setItem("minerva.policyProfile", normalized);
  } catch {
    // Ignore storage failures.
  }
  renderPolicyProfileSwitch();
}

function statusCopy(key) {
  const zh = state.lang === "zh";
  const copy = {
    startButton: zh ? "开始检测" : "Start detection",
    detectingButton: zh ? "检测中..." : "Detecting...",
    redetectButton: zh ? "重新检测" : "Re-detect",
    removeButton: zh ? "移除图片" : "Remove image",
    readyTitle: zh ? "图片已就绪" : "Image ready",
    readyBody: zh ? "点击开始检测以生成结论、置信度、风险等级和报告入口。" : "Click start detection to generate the verdict, confidence, risk level, and report actions.",
    noFile: zh ? "请先上传图片。" : "Please upload an image first.",
    detectingBody: zh ? "正在检测，请稍候。" : "Detecting. Please wait.",
    warmupWaiting: zh ? "模型正在预热，首检会自动等待；请保持页面打开。" : "Models are warming up. The first scan will wait automatically; keep this page open.",
    backendReconnectWaiting: zh ? "正在等待后端连接恢复；首检会在短时间内自动继续。" : "Waiting for the backend connection to recover; the first scan will continue automatically.",
    retryingConnection: zh ? "后端刚恢复或模型仍在切换，正在自动重试一次。" : "Backend just recovered or models are still settling; retrying once automatically.",
    retryAdvice: zh ? "请检查后端状态后重试，或重新选择图片。" : "Check the backend status and retry, or choose the image again.",
  };
  return copy[key] || key;
}

function singleActionLabel() {
  if (state.singleLoading || state.singleStatus === "detecting") {
    return statusCopy("detectingButton");
  }
  if (state.singleStatus === "success" || state.singleStatus === "error") {
    return statusCopy("redetectButton");
  }
  return statusCopy("startButton");
}

function setDemoTab(tab) {
  state.demoTab = ["upload", "batch", "sample"].includes(tab) ? tab : "upload";
  elements.demoTabs?.setAttribute("role", "tablist");
  elements.demoTabs?.querySelectorAll("[data-demo-tab]").forEach((button) => {
    const active = button.dataset.demoTab === state.demoTab;
    button.classList.toggle("active", active);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", active ? "true" : "false");
    button.setAttribute("tabindex", active ? "0" : "-1");
  });
  document.querySelectorAll("[data-demo-panel]").forEach((panel) => {
    const active = panel.dataset.demoPanel === state.demoTab;
    panel.classList.toggle("active", active);
    panel.setAttribute("role", "tabpanel");
    panel.toggleAttribute("hidden", !active);
  });
}

function updateFileLabels() {
  const single = state.selectedSingleFile;
  elements.singleFileLabel.textContent = state.singleDragDepth > 0 ? t("single.release") : single ? single.name : t("single.choose");
  elements.singleFileMeta.textContent = single ? `${formatFileSize(single.size)} · ${single.type || t("single.formats")}` : t("single.formats");

  const count = state.selectedBatchFiles.length;
  elements.batchFileLabel.textContent = state.batchDragDepth > 0 ? t("batch.release") : count ? t("batch.selected", { count }) : t("batch.choose");
  elements.batchFileMeta.textContent = count
    ? state.selectedBatchFiles.map((file) => file.name).slice(0, 2).join(", ") + (count > 2 ? "..." : "")
    : t("batch.empty");
}

function renderSinglePreview(file) {
  if (state.selectedSingleObjectUrl) {
    URL.revokeObjectURL(state.selectedSingleObjectUrl);
    state.selectedSingleObjectUrl = null;
  }
  elements.singlePreview.hidden = !file;
  elements.singlePreview.innerHTML = "";
  if (!file) {
    return;
  }
  state.selectedSingleObjectUrl = URL.createObjectURL(file);
  elements.singlePreview.innerHTML = `
    <img class="selected-file-thumb" src="${state.selectedSingleObjectUrl}" alt="${escapeHtml(file.name)}" />
    <div class="selected-file-meta file-preview-copy">
      <strong class="selected-file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong>
      <span class="selected-file-subtitle">${escapeHtml(formatFileSize(file.size))} - ${escapeHtml(file.type || fileFormat(file))}</span>
    </div>
    <div class="single-upload-actions" aria-label="${escapeHtml(statusCopy("readyTitle"))}">
      <button class="button button-primary single-run-button" type="button" data-action="run-single-detection">${escapeHtml(singleActionLabel())}</button>
      <button class="button button-secondary single-remove-button" type="button" data-action="remove-single-file">${escapeHtml(statusCopy("removeButton"))}</button>
      <button class="button button-secondary single-rechoose-button" type="button" data-action="rechoose-single-file">${escapeHtml(state.lang === "zh" ? "重新选择" : "Choose again")}</button>
    </div>
  `;
  setUploadButtons();
}

function renderBatchPreview() {
  state.selectedBatchObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  state.selectedBatchObjectUrls = [];
  elements.batchPreview.hidden = state.selectedBatchFiles.length === 0;
  elements.batchPreview.innerHTML = "";
  if (!state.selectedBatchFiles.length) {
    return;
  }

  const visibleFiles = state.selectedBatchFiles.slice(0, 6);
  const thumbs = visibleFiles
    .map((file) => {
      const url = URL.createObjectURL(file);
      state.selectedBatchObjectUrls.push(url);
      return `<img src="${url}" alt="${escapeHtml(file.name)}" title="${escapeHtml(file.name)}" />`;
    })
    .join("");
  const remaining = state.selectedBatchFiles.length - visibleFiles.length;
  elements.batchPreview.innerHTML = `
    <div class="batch-thumbs">
      ${thumbs}
      ${remaining > 0 ? `<span class="batch-more">${escapeHtml(t("batch.more", { count: remaining }))}</span>` : ""}
    </div>
    <div class="batch-preview-meta">
      <strong>${escapeHtml(t("batch.selected", { count: state.selectedBatchFiles.length }))}</strong>
      <span>${escapeHtml(state.selectedBatchFiles.map((file) => fileFormat(file)).slice(0, 4).join(" / "))}</span>
    </div>
    <button class="preview-clear" type="button" data-action="clear-batch-files">${escapeHtml(t("batch.clear"))}</button>
  `;
}

function renderSummary(payload) {
  const summary = getValue(payload, "summary", getValue(payload, "data.summary", {}));
  const labels = summary.final_label_distribution || summary.label_distribution || {};
  const risks = summary.risk_level_distribution || summary.risk_distribution || {};
  const quality = summary.decision_quality || {};

  setSummaryValue("totalScans", formatInteger(firstDefined(summary.total_detections, summary.total_scans, summary.total, 0)));
  setSummaryValue("aiDetected", formatInteger(firstDefined(labels.ai_generated, labels.ai, 0)));
  setSummaryValue("realDetected", formatInteger(firstDefined(labels.real, labels.real_photo, 0)));
  setSummaryValue("uncertain", formatInteger(firstDefined(labels.uncertain, 0)));
  setSummaryValue("highRisk", formatInteger(firstDefined(risks.high, risks.critical, 0)));
  setSummaryValue("averageConfidence", formatConfidence(firstDefined(quality.average_confidence, summary.average_confidence, 0)));
}

function chartLabel(label) {
  const normalized = slug(label);
  if (normalized === "ai-generated") return displayLabel("ai_generated");
  if (normalized === "real") return displayLabel("real");
  if (normalized === "uncertain") return displayLabel("uncertain");
  if (normalized === "low") return displayLabel("low");
  if (normalized === "medium") return displayLabel("medium");
  if (normalized === "high") return displayLabel("high");
  if (normalized === "unknown") return displayLabel("unknown");
  if (normalized === "high-confidence") return state.lang === "zh" ? "高置信" : "High Confidence";
  if (normalized === "medium-confidence") return state.lang === "zh" ? "中置信" : "Medium Confidence";
  if (normalized === "low-confidence") return state.lang === "zh" ? "低置信" : "Low Confidence";
  return label;
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
      const rawLabel = firstDefined(point.label, point.name, "Unknown");
      return `
        <div class="bar-row">
          <span class="bar-label">${escapeHtml(chartLabel(rawLabel))}</span>
          <span class="bar-track" aria-hidden="true">
            <span class="bar-fill ${slug(rawLabel)}" style="width: ${width}%"></span>
          </span>
          <span class="bar-value">${formatInteger(value)}</span>
        </div>
      `;
    })
    .join("");
}

function renderCharts(payload) {
  const charts = getValue(payload, "charts", getValue(payload, "chart_data", {}));
  elements.chartUpdatedAt.textContent = payload?.generated_at ? t("charts.updated", { time: formatTimestamp(payload.generated_at) }) : "--";
  renderChart(elements.labelChart, charts.label_distribution || charts.label_pie, t("charts.noLabel"));
  renderChart(elements.riskChart, charts.risk_distribution || charts.risk_bar, t("charts.noRisk"));
  renderChart(elements.confidenceChart, charts.confidence_distribution || charts.confidence_bar, t("charts.noConfidence"));
}

function renderChartsError() {
  elements.chartUpdatedAt.textContent = t("nav.apiError");
  renderChart(elements.labelChart, [], "", t("charts.apiError"));
  renderChart(elements.riskChart, [], "", t("charts.apiError"));
  renderChart(elements.confidenceChart, [], "", t("charts.apiError"));
}

function renderRecentResults(payload) {
  const results = Array.isArray(payload?.results)
    ? payload.results
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.recent_results)
        ? payload.recent_results
        : [];

  state.recentAllResults = results;
  renderReportSummary(payload, results.length);
  renderRecentRows(results, firstDefined(payload?.filtered_total, payload?.count, results.length));
}

function renderReportSummary(payload, shownCount) {
  const summary = payload?.summary || {};
  const values = {
    total_records: firstDefined(summary.total_records, payload?.total, shownCount),
    filtered_total: firstDefined(payload?.filtered_total, payload?.count, shownCount),
    pending_review: firstDefined(summary.pending_review, 0),
    high_risk: firstDefined(summary.high_risk, 0),
    uncertain: firstDefined(summary.uncertain, 0),
  };
  Object.entries(values).forEach(([key, value]) => {
    const node = document.querySelector(`[data-report-summary="${key}"]`);
    if (node) node.textContent = formatInteger(value);
  });
  updateHeroReportMetrics(values);
}

function updateHeroReportMetrics(values = {}) {
  if (elements.heroReportsMetric) {
    elements.heroReportsMetric.textContent = "4";
  }
  if (elements.heroReviewMetric) {
    const pendingReview = values.pending_review;
    elements.heroReviewMetric.textContent = pendingReview === undefined || pendingReview === null ? "live" : formatInteger(pendingReview);
  }
}

function updateHeroHealthMetrics(health = {}, isError = false) {
  if (elements.heroBackendMetric) {
    elements.heroBackendMetric.textContent = isError
      ? t("hero.runtimeOffline")
      : health.warmup_ready
        ? t("hero.runtimeReady")
        : t("hero.runtimeWarming");
  }
  if (elements.heroExportMetric) {
    elements.heroExportMetric.textContent = health.export_enabled === false ? "--" : t("hero.exportReady");
  }
}

function statusText(value) {
  if (value === true) return t("systemStatus.enabled");
  if (value === false) return t("systemStatus.disabled");
  const normalized = String(value || "").toLowerCase();
  if (normalized === "ok") return t("systemStatus.ok");
  if (normalized === "uninitialized") return t("systemStatus.ok");
  if (normalized === "error") return t("systemStatus.error");
  return value === undefined || value === null || value === "" ? "--" : String(value);
}

function renderSystemStatus(payload, isError = false, modelStatus = null) {
  if (!elements.systemStatusGrid) return;
  const health = payload || {};
  updateHeroHealthMetrics(health, isError);
  const runtimes = Array.isArray(modelStatus?.hf_runtimes) ? modelStatus.hf_runtimes : [];
  const loadedRuntimeCount = runtimes.filter((item) => item && item.model_loaded).length;
  const runtimeCount = runtimes.length || Number(modelStatus?.hf_runtime_count || 0);
  const runtimeMode = modelStatus?.detector_runtime_mode || "--";
  const loadedRuntimeNames = runtimes
    .filter((item) => item && item.model_loaded)
    .map((item) => String(item.detector_id || item.model_id || "").trim())
    .filter(Boolean)
    .join(", ");
  const modelLoadText = runtimeCount
    ? `${loadedRuntimeCount}/${runtimeCount}${loadedRuntimeNames ? ` ${loadedRuntimeNames}` : ""}`
    : "--";
  const modelLoadTone = runtimeCount && loadedRuntimeCount === runtimeCount ? "ok" : runtimeCount ? "warning" : "muted";
  const rows = isError
    ? [
        ["backend", t("systemStatus.error"), "error"],
        ["reportsApi", t("systemStatus.unavailable"), "error"],
        ["database", t("systemStatus.unavailable"), "error"],
        ["warmupReady", t("systemStatus.unavailable"), "error"],
        ["runtimeMode", "--", "muted"],
        ["loadedModels", "--", "muted"],
        ["reportCount", "--", "muted"],
        ["schemaVersion", "--", "muted"],
        ["detectorVersion", "--", "muted"],
        ["modelVersion", "--", "muted"],
        ["persistence", t("systemStatus.disabled"), "error"],
        ["htmlReport", t("systemStatus.unavailable"), "error"],
        ["export", t("systemStatus.unavailable"), "error"],
      ]
    : [
        ["backend", statusText(health.api_status), health.api_status === "ok" ? "ok" : "error"],
        ["reportsApi", statusText(health.reports_api_status), health.reports_api_status === "ok" ? "ok" : "error"],
        ["database", statusText(health.database_status), ["ok", "uninitialized"].includes(String(health.database_status || "").toLowerCase()) ? "ok" : "error"],
        ["warmupReady", statusText(Boolean(health.warmup_ready)), health.warmup_ready ? "ok" : "warning"],
        ["runtimeMode", runtimeMode, runtimeMode === "local_hf" ? "ok" : runtimeMode === "--" ? "muted" : "warning"],
        ["loadedModels", modelLoadText, modelLoadTone],
        ["reportCount", health.report_count === null || health.report_count === undefined ? "--" : formatInteger(health.report_count), "muted"],
        ["schemaVersion", health.report_schema_version || "--", "muted"],
        ["detectorVersion", health.detector_version || "--", "muted"],
        ["modelVersion", health.model_version || "--", "muted"],
        ["persistence", statusText(Boolean(health.persistence_enabled)), health.persistence_enabled ? "ok" : "error"],
        ["htmlReport", statusText(Boolean(health.html_report_enabled)), health.html_report_enabled ? "ok" : "error"],
        ["export", statusText(Boolean(health.export_enabled)), health.export_enabled ? "ok" : "error"],
      ];
  elements.systemStatusGrid.innerHTML = rows
    .map(
      ([key, value, tone]) => `
        <span class="system-status-item" data-status-tone="${escapeHtml(tone)}">
          <em>${escapeHtml(t(`systemStatus.${key}`))}</em>
          <strong>${escapeHtml(value)}</strong>
        </span>
      `,
    )
    .join("");
}

function compactReason(value, maxLength = 150) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

function renderCalibrationReadiness(payload, isError = false) {
  if (!elements.calibrationReadinessGrid) return;
  if (isError || !payload) {
    elements.calibrationReadinessGrid.innerHTML = [
      ["labels", "--", "error"],
      ["replay", "--", "error"],
      ["stress", "--", "error"],
      ["training", "--", "error"],
      ["recommendation", t("calibration.unavailable"), "error"],
    ]
      .map(
        ([key, value, tone]) => `
          <span class="system-status-item" data-status-tone="${escapeHtml(tone)}">
            <em>${escapeHtml(t(`calibration.${key}`))}</em>
            <strong>${escapeHtml(value)}</strong>
          </span>
        `,
      )
      .join("");
    if (elements.calibrationReadinessNote) {
      elements.calibrationReadinessNote.textContent = t("calibration.unavailable");
    }
    return;
  }

  const review = payload.reviewCalibration || {};
  const policy = payload.policyReplay || {};
  const stress = payload.scenarioStressPack || {};
  const training = payload.trainingReadiness || {};
  const reviewSummary = review.summary || {};
  const stressSummary = stress.summary || {};
  const trainingSummary = training.summary || {};
  const labeledCount = Number(reviewSummary.labeled_count || 0);
  const totalCount = Number(reviewSummary.total || review.total || 0);
  const labelCoverage = Number(reviewSummary.label_coverage || 0);
  const replayRows = Number(policy.row_count || 0);
  const replayable = Number(policy.metrics?.strict_safe_plus?.replayable_records || 0);
  const readyStress = Number(stressSummary.ready_count || 0);
  const totalStress = Number(stress.total || stress.item_count || 0);
  const supervisedReady = Number(trainingSummary.supervised_ready_count || 0);
  const minSupervised = Number(trainingSummary.min_supervised_labels || 20);
  const trainingLevel = String(trainingSummary.readiness_level || t("calibration.needsLabels"));
  const recommendation = policy.recommended_profile || {};
  const recommendedProfile = recommendation.profile ? String(recommendation.profile) : t("calibration.needsLabels");
  const rows = [
    [
      "labels",
      `${formatInteger(labeledCount)} / ${formatInteger(totalCount)} (${formatConfidence(labelCoverage)})`,
      labelCoverage >= 0.02 ? "ok" : labeledCount > 0 ? "warning" : "error",
    ],
    [
      "replay",
      `${formatInteger(replayable)} / ${formatInteger(replayRows)}`,
      replayable > 0 ? "ok" : replayRows > 0 ? "warning" : "muted",
    ],
    [
      "stress",
      `${formatInteger(readyStress)} / ${formatInteger(totalStress)}`,
      readyStress > 0 && readyStress === totalStress ? "ok" : readyStress > 0 ? "warning" : "muted",
    ],
    [
      "training",
      `${formatInteger(supervisedReady)} / ${formatInteger(minSupervised)} ${trainingLevel}`,
      trainingSummary.readiness_level === "train_ready" ? "ok" : supervisedReady > 0 ? "warning" : "muted",
    ],
    [
      "recommendation",
      recommendedProfile,
      recommendation.profile ? "ok" : "warning",
    ],
  ];
  elements.calibrationReadinessGrid.innerHTML = rows
    .map(
      ([key, value, tone]) => `
        <span class="system-status-item" data-status-tone="${escapeHtml(tone)}">
          <em>${escapeHtml(t(`calibration.${key}`))}</em>
          <strong>${escapeHtml(value)}</strong>
        </span>
      `,
    )
    .join("");
  const cacheState = [review.cached, policy.cached, stress.cached, training.cached].some(Boolean) ? t("calibration.cached") : t("calibration.live");
  const reason = compactReason(recommendation.reason || trainingSummary.recommendation || t("calibration.labelGap"));
  if (elements.calibrationReadinessNote) {
    elements.calibrationReadinessNote.textContent = `${cacheState}: ${reason}`;
  }
}

function filteredRecentResults() {
  if (state.recentFilter === "ai") {
    return state.recentAllResults.filter((item) => normalizeFinalLabel(firstDefined(item.final_label, item.label)) === "ai");
  }
  if (state.recentFilter === "uncertain") {
    return state.recentAllResults.filter((item) => normalizeFinalLabel(firstDefined(item.final_label, item.label)) === "uncertain");
  }
  if (state.recentFilter === "high") {
    return state.recentAllResults.filter((item) => String(firstDefined(item.risk_level, item.risk, "")).toLowerCase() === "high");
  }
  return state.recentAllResults;
}

function renderRecentRows(results, countValue = results.length) {
  state.recentResults.clear();
  elements.recentCount.textContent = t("reportCenter.filteredStatus", { count: formatInteger(countValue) });
  elements.recentBody.innerHTML = "";
  elements.recentEmptyState.hidden = results.length > 0;
  elements.recentEmptyState.textContent = t("reportCenter.empty");

  if (!results.length) {
    return;
  }

  elements.recentBody.innerHTML = results
    .map((item, index) => {
      const id = String(firstDefined(item.report_id, item.id, item.history_file, `recent-${index}`));
      state.recentResults.set(id, item);
      const label = firstDefined(item.final_label, item.label, "uncertain");
      const risk = firstDefined(item.risk_level, item.risk, "unknown");
      const filename = firstDefined(item.filename, item.image_name, "unknown");
      const reviewStatus = firstDefined(item.review_status, "pending_review");
      const summary = resultSummaryText(item);
      const labelTone = normalizeVerdictKey(label) === "ai" ? "ai-generated" : normalizeVerdictKey(label);
      const riskTone = getRiskTone(risk);
      const reviewTone = normalizeReviewStatusKey(reviewStatus);
      return `
        <tr class="audit-row" tabindex="0" data-action="open-recent-detail" data-id="${escapeHtml(id)}" aria-label="Open detection detail for ${escapeHtml(filename)}">
          <td>${escapeHtml(formatTimestamp(item.timestamp || item.created_at || item.processed_at))}</td>
          <td class="filename-cell" title="${escapeHtml(`${filename} / ${id}`)}">
            <strong>${escapeHtml(filename)}</strong>
            <span>${escapeHtml(id)}</span>
          </td>
          <td><span class="badge ${slug(labelTone)}">${escapeHtml(getVerdictLabel(label))}</span></td>
          <td><span class="badge ${slug(riskTone)}">${escapeHtml(getRiskLabel(risk))}</span></td>
          <td>${escapeHtml(formatConfidence(item.confidence))}</td>
          <td><span class="badge review-${slug(reviewTone)}">${escapeHtml(getReviewStatusLabel(reviewStatus))}</span></td>
          <td class="summary-cell" title="${escapeHtml(summary)}">
            <span class="summary-clamp">${escapeHtml(summary)}</span>
          </td>
          <td class="action-cell">
            <button class="table-action" type="button" data-action="view-recent-detail" data-id="${escapeHtml(id)}">${escapeHtml(t("reportCenter.actions.viewDetail"))}</button>
            <button class="table-action" type="button" data-action="report-recent-detail" data-id="${escapeHtml(id)}">${escapeHtml(t("reportCenter.actions.report"))}</button>
            <button class="table-action" type="button" data-action="review-recent-detail" data-id="${escapeHtml(id)}">${escapeHtml(t("reportCenter.actions.review"))}</button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderRecentResultsError() {
  elements.recentCount.textContent = t("nav.apiError");
  elements.recentBody.innerHTML = "";
  elements.recentEmptyState.hidden = false;
  elements.recentEmptyState.textContent = t("reportCenter.loadFailed");
}

function renderReviewQueue(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  state.reportQueue = items;
  if (elements.reviewQueueCount) {
    elements.reviewQueueCount.textContent = formatInteger(firstDefined(payload?.total, items.length));
  }
  if (!elements.reviewQueueList) return;
  if (!items.length) {
    elements.reviewQueueList.innerHTML = `<div class="empty-state compact">${escapeHtml(t("reportCenter.queueEmpty"))}</div>`;
    return;
  }
  elements.reviewQueueList.innerHTML = items
    .map((item, index) => {
      const id = String(firstDefined(item.report_id, item.id, item.history_file, `queue-${index}`));
      state.recentResults.set(id, item);
      const reason = resultSummaryText(item);
      const labelTone = normalizeVerdictKey(item.final_label) === "ai" ? "ai-generated" : normalizeVerdictKey(item.final_label);
      const riskTone = getRiskTone(item.risk_level);
      const reviewTone = normalizeReviewStatusKey(item.review_status);
      return `
        <button class="review-queue-item" type="button" data-action="review-queue-detail" data-id="${escapeHtml(id)}">
          <span class="queue-title" title="${escapeHtml(firstDefined(item.filename, item.image_name, id))}">${escapeHtml(firstDefined(item.filename, item.image_name, id))}</span>
          <span class="queue-badges">
            <em class="badge ${slug(labelTone)}">${escapeHtml(getVerdictLabel(item.final_label))}</em>
            <em class="badge ${slug(riskTone)}">${escapeHtml(getRiskLabel(item.risk_level))}</em>
            <em class="badge review-${slug(reviewTone)}">${escapeHtml(getReviewStatusLabel(item.review_status))}</em>
          </span>
          <span class="queue-meta">${escapeHtml(formatConfidence(item.confidence))} / ${escapeHtml(formatTimestamp(item.created_at || item.timestamp))}</span>
          <span class="queue-reason">${escapeHtml(reason)}</span>
        </button>
      `;
    })
    .join("");
}

function trainingQueueTargetLabel(targetGap) {
  if (targetGap === "ai") return t("reportCenter.trainingQueue.needAi");
  if (targetGap === "real") return t("reportCenter.trainingQueue.needReal");
  return t("reportCenter.trainingQueue.needEither");
}

function quickReviewStatusForTruth(item, truthLabel) {
  const predicted = normalizeVerdictKey(firstDefined(item?.predicted_label, item?.final_label, item?.label, "uncertain"));
  if (truthLabel === "ai") {
    return predicted === "real" ? "false_negative" : "confirmed_ai";
  }
  if (truthLabel === "real") {
    return predicted === "ai" ? "false_positive" : "confirmed_real";
  }
  return "needs_recheck";
}

function renderTrainingLabelQueue(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  state.trainingLabelQueue = payload || null;
  if (elements.trainingLabelQueueCount) {
    elements.trainingLabelQueueCount.textContent = formatInteger(firstDefined(payload?.total, items.length));
  }
  const gap = payload?.gap || {};
  if (elements.trainingLabelQueueGap) {
    elements.trainingLabelQueueGap.textContent = t("reportCenter.trainingQueue.gap", {
      ai: formatInteger(gap.needed_ai_labels || 0),
      real: formatInteger(gap.needed_real_labels || 0),
    });
  }
  if (!elements.trainingLabelQueueList) return;
  if (!items.length) {
    elements.trainingLabelQueueList.innerHTML = `<div class="empty-state compact">${escapeHtml(t("reportCenter.trainingQueue.empty"))}</div>`;
    return;
  }
  elements.trainingLabelQueueList.innerHTML = items
    .map((item, index) => {
      const id = String(firstDefined(item.report_id, item.id, `training-${index}`));
      state.recentResults.set(id, item);
      const labelTone = normalizeVerdictKey(item.predicted_label) === "ai" ? "ai-generated" : normalizeVerdictKey(item.predicted_label);
      const riskTone = getRiskTone(item.risk_level);
      const reviewTone = normalizeReviewStatusKey(item.review_status);
      const suggested = Array.isArray(item.suggested_review_statuses) ? item.suggested_review_statuses.map(getReviewStatusLabel).join(" / ") : "";
      const aiStatus = quickReviewStatusForTruth(item, "ai");
      const realStatus = quickReviewStatusForTruth(item, "real");
      return `
        <article class="review-queue-item training-label-item">
          <button class="training-label-open" type="button" data-action="review-queue-detail" data-id="${escapeHtml(id)}">
            <span class="queue-title" title="${escapeHtml(firstDefined(item.filename, id))}">${escapeHtml(firstDefined(item.filename, id))}</span>
            <span class="queue-badges">
              <em class="badge ${slug(labelTone)}">${escapeHtml(getVerdictLabel(item.predicted_label))}</em>
              <em class="badge ${slug(riskTone)}">${escapeHtml(getRiskLabel(item.risk_level))}</em>
              <em class="badge review-${slug(reviewTone)}">${escapeHtml(getReviewStatusLabel(item.review_status))}</em>
            </span>
            <span class="queue-meta">${escapeHtml(trainingQueueTargetLabel(item.target_gap))} / ${escapeHtml(formatConfidence(item.confidence))}</span>
            <span class="queue-reason">${escapeHtml(t("reportCenter.trainingQueue.suggested"))}: ${escapeHtml(suggested)}</span>
          </button>
          <span class="training-label-quick-actions">
            <button class="table-action" type="button" data-action="training-label-quick-review" data-id="${escapeHtml(id)}" data-review-status="${escapeHtml(aiStatus)}">${escapeHtml(t("reportCenter.trainingQueue.markAi"))}</button>
            <button class="table-action" type="button" data-action="training-label-quick-review" data-id="${escapeHtml(id)}" data-review-status="${escapeHtml(realStatus)}">${escapeHtml(t("reportCenter.trainingQueue.markReal"))}</button>
          </span>
        </article>
      `;
    })
    .join("");
}

function renderReviewQueueError() {
  if (elements.reviewQueueCount) elements.reviewQueueCount.textContent = "--";
  if (elements.reviewQueueList) {
    elements.reviewQueueList.innerHTML = `<div class="error-state compact">${escapeHtml(t("reportCenter.queueFailed"))}</div>`;
  }
}

function renderTrainingLabelQueueError() {
  state.trainingLabelQueue = null;
  if (elements.trainingLabelQueueCount) elements.trainingLabelQueueCount.textContent = "--";
  if (elements.trainingLabelQueueGap) elements.trainingLabelQueueGap.textContent = t("reportCenter.trainingQueue.subtitle");
  if (elements.trainingLabelQueueList) {
    elements.trainingLabelQueueList.innerHTML = `<div class="error-state compact">${escapeHtml(t("reportCenter.trainingQueue.failed"))}</div>`;
  }
}

async function quickReviewTrainingLabel(reportId, reviewStatus, trigger) {
  if (!reportId || !reviewStatus) {
    return;
  }
  const originalText = trigger?.textContent || "";
  if (trigger) {
    trigger.disabled = true;
    trigger.textContent = t("nav.syncing");
  }
  await fetchJson(API_ENDPOINTS.reportReview(reportId), {
    method: "PATCH",
    timeoutMs: 12000,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      review_status: reviewStatus,
      review_note: "Training label queue quick review.",
      reviewed_by: "local_dashboard_training_queue",
    }),
  });
  state.trainingLabelQueue = null;
  if (trigger) {
    trigger.textContent = t("reportCenter.trainingQueue.saved");
  }
  await refreshReportCenter({ silent: true });
  setServiceStatus("online", t("nav.online"));
  if (trigger) {
    window.setTimeout(() => {
      trigger.disabled = false;
      trigger.textContent = originalText;
    }, 1200);
  }
}

async function rebuildTrainingReadiness(trigger) {
  const originalText = trigger?.textContent || "";
  if (trigger) {
    trigger.disabled = true;
    trigger.textContent = t("reportCenter.trainingQueue.rebuilding");
  }
  const payload = await fetchJson(API_ENDPOINTS.trainingReadinessRebuild, {
    method: "POST",
    timeoutMs: 60000,
  });
  state.trainingLabelQueue = null;
  state.calibrationReadiness = {
    ...(state.calibrationReadiness || {}),
    trainingReadiness: {
      schema_version: "training_readiness_manifest_v1",
      summary: payload.summary || {},
      total: payload.total || 0,
      items: [],
      cached: true,
    },
  };
  if (trigger) {
    trigger.textContent = t("reportCenter.trainingQueue.rebuildDone");
  }
  await refreshReportCenter({ silent: true });
  renderCalibrationReadiness(state.calibrationReadiness);
  setServiceStatus("online", t("nav.online"));
  if (trigger) {
    window.setTimeout(() => {
      trigger.disabled = false;
      trigger.textContent = originalText;
    }, 1600);
  }
}

function applyResultView() {
  elements.resultViewToggle?.setAttribute("role", "tablist");
  elements.resultViewToggle?.querySelectorAll("[data-result-view]").forEach((button) => {
    const active = button.dataset.resultView === state.resultView;
    button.classList.toggle("active", active);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", active ? "true" : "false");
    button.setAttribute("tabindex", active ? "0" : "-1");
  });
  document.querySelectorAll("[data-result-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.resultPanel !== state.resultView;
  });
}

function setResultView(view) {
  state.resultView = view === "json" ? "json" : "simple";
  applyResultView();
}

function resultJsonPanel(payload) {
  const json = payload ? JSON.stringify(payload, null, 2) : "{}";
  return `
    <div class="result-json-panel" data-result-panel="json" ${state.resultView === "json" ? "" : "hidden"}>
      <pre>${escapeHtml(json)}</pre>
    </div>
  `;
}

function evidenceTags(data) {
  const debug = data?.debug_evidence || {};
  const provenance = data?.provenance || getValue(debug, "provenance", {});
  const hasMetadata = Boolean(
    getValue(debug, "format_evidence.exif_info.has_exif") ||
      getValue(debug, "format_evidence.format_info.format") ||
      getValue(debug, "feature_summary.raw_debug_evidence.format_info.format"),
  );
  const hasModel = Boolean(getValue(debug, "feature_summary.raw_debug_evidence.raw_result.model_result"));
  const hasForensics = Boolean(getValue(debug, "feature_summary.raw_debug_evidence.raw_result.forensic_result"));
  const hasConsistency = Boolean(getValue(debug, "consistency_checks") || getValue(debug, "feature_summary.raw_debug_evidence.multi_resolution"));
  const tags = [
    [t("result.sourceEvidence"), hasMetadata || Boolean(provenance.c2pa_present || provenance.provenance_confidence)],
    [t("result.metadataAi"), hasMetadata || hasModel],
    [t("result.forensicFeatures"), hasForensics || hasConsistency],
    [t("result.detectionOutput"), true],
    [t("result.reviewAdvice"), true],
  ];
  return tags
    .map(([label, active], index) => `<span class="evidence-tag ${active ? "active" : "muted"}" style="--delay:${index * 90}ms">${escapeHtml(label)}</span>`)
    .join("");
}

function evidenceMiniMap(data) {
  const debug = data?.debug_evidence || {};
  const raw = getValue(debug, "feature_summary.raw_debug_evidence", {});
  const states = {
    source: Boolean(getValue(debug, "format_evidence.exif_info.has_exif") || getValue(raw, "exif_info.has_exif")),
    metadata: Boolean(
      getValue(debug, "format_evidence.format_info.format") ||
        getValue(raw, "format_info.format") ||
        getValue(raw, "raw_result.image_info.format"),
    ),
    model: Boolean(getValue(raw, "raw_result.model_result") || getValue(raw, "model_result")),
    forensics: Boolean(getValue(raw, "raw_result.forensic_result") || getValue(raw, "forensic_result")),
  };
  const nodes = [
    [t("result.sourceEvidence"), states.source, t("result.sourceEvidence")],
    [t("result.metadataAi"), states.metadata || states.model, t("result.metadataAi")],
    [t("result.forensicFeatures"), states.forensics, t("result.forensicFeatures")],
    [t("result.detectionOutput"), true, `${t("result.riskLevel")} + ${t("result.confidence")}`],
    [t("result.reviewAdvice"), true, t("result.reviewAdvice")],
  ];
  return `
    <div class="evidence-mini-map" aria-label="${escapeHtml(t("result.evidenceChain"))}">
      ${nodes
        .map(
          ([label, active, title], index) => `
            <span class="mini-node ${active ? "available" : "partial"}" style="--node-delay:${index * 80}ms" title="${escapeHtml(title)}">
              <i></i><em>${escapeHtml(label)}</em>
            </span>
          `,
        )
        .join("")}
    </div>
  `;
}

function animateNumber(element, from, to, duration = 760) {
  if (!element || state.prefersReducedMotion) {
    if (element) element.textContent = `${Math.round(to)}%`;
    return;
  }
  const start = performance.now();
  const tick = (time) => {
    const progress = Math.min(1, (time - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = `${Math.round(from + (to - from) * eased)}%`;
    if (progress < 1) {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
}

function applyResultRevealClasses(confidencePercent = null) {
  const result = elements.uploadResult.querySelector(".trust-result");
  if (!result) {
    applyResultView();
    return;
  }
  requestAnimationFrame(() => result.classList.add("is-visible"));
  const confidence = elements.uploadResult.querySelector("[data-animate-confidence]");
  if (confidence && confidencePercent !== null) {
    animateNumber(confidence, 0, confidencePercent);
  }
  applyResultView();
}

function renderEmptyResult() {
  const hasSelectedFile = Boolean(state.selectedSingleFile);
  const backendStatus = String(elements.serviceStatus?.dataset.status || "").toLowerCase();
  updateConsoleScanState(hasSelectedFile ? "ready" : ["offline", "error"].includes(backendStatus) ? "offline" : "idle");
  const title = hasSelectedFile ? statusCopy("readyTitle") : t("result.emptyTitle");
  const body = hasSelectedFile ? statusCopy("readyBody") : t("result.emptyBody");
  elements.uploadResult.innerHTML = `
    <div class="result-empty">
      <div data-result-panel="simple" ${state.resultView === "simple" ? "" : "hidden"}>
        <img class="empty-mark result-mark" src="./assets/minerva-mark.png" onerror="this.onerror=null;this.src='./assets/minerva-mark.svg'" alt="" />
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(body)}</p>
        <div class="signal-dots" aria-hidden="true">
          <span></span><span></span><span></span><span></span>
        </div>
      </div>
      <div class="result-json-panel empty-json" data-result-panel="json" ${state.resultView === "json" ? "" : "hidden"}>
        <p>${escapeHtml(t("demo.emptyJson"))}</p>
        <pre>{}</pre>
      </div>
    </div>
  `;
  applyResultView();
}

function renderLoadingResult(message) {
  updateConsoleScanState("scanning");
  const previewUrl = state.selectedSingleObjectUrl || "";
  elements.uploadResult.innerHTML = `
    <div class="result-empty loading scanning-state">
      <div data-result-panel="simple" ${state.resultView === "simple" ? "" : "hidden"}>
        <div class="scan-preview">
          ${
            previewUrl
              ? `<img src="${previewUrl}" alt="${escapeHtml(state.selectedSingleFile?.name || "Scanning preview")}" />`
              : `<img class="scan-mark-image" src="./assets/minerva-mark.png" onerror="this.onerror=null;this.src='./assets/minerva-mark.svg'" alt="" />`
          }
          <span class="scan-line" aria-hidden="true"></span>
        </div>
        <h3>${escapeHtml(t("result.loading"))}</h3>
        <p>${escapeHtml(message)}</p>
        <p class="scan-detail">${escapeHtml(t("single.scanning"))}</p>
        <div class="signal-dots active" aria-hidden="true">
          <span data-signal="Source"></span>
          <span data-signal="Metadata"></span>
          <span data-signal="Model"></span>
          <span data-signal="Forensics"></span>
        </div>
      </div>
      <div class="result-json-panel empty-json" data-result-panel="json" ${state.resultView === "json" ? "" : "hidden"}>
        <p>${escapeHtml(t("result.loading"))}</p>
        <pre>{ "status": "analyzing" }</pre>
      </div>
    </div>
  `;
  applyResultView();
}

function renderErrorResult(message, payload = null) {
  updateConsoleScanState("error");
  const errorPayload = payload || {
    success: false,
    data: null,
    error: {
      message,
    },
  };
  elements.uploadResult.innerHTML = `
    <div class="result-empty result-error">
      <article class="error-state" data-result-panel="simple" ${state.resultView === "simple" ? "" : "hidden"}>
        <h3>${escapeHtml(t("result.failed"))}</h3>
        <p>${escapeHtml(message)}</p>
        <p>${escapeHtml(statusCopy("retryAdvice"))}</p>
      </article>
      <div class="result-json-panel" data-result-panel="json" ${state.resultView === "json" ? "" : "hidden"}>
        <p>${escapeHtml(t("result.failed"))}</p>
        <pre>${escapeHtml(JSON.stringify(errorPayload, null, 2))}</pre>
      </div>
    </div>
  `;
  applyResultView();
}

function evidenceLine(title, text, status = "neutral", stateLabel = t("result.partial")) {
  return `
    <div class="evidence-line ${status}">
      <div>
        <span>${escapeHtml(title)}</span>
        <strong>${escapeHtml(text || t("result.notAvailable"))}</strong>
      </div>
      <em>${escapeHtml(stateLabel)}</em>
    </div>
  `;
}

function evidenceFromDebug(data) {
  const debug = data.debug_evidence || {};
  const provenance = data.provenance || getValue(debug, "provenance", {});
  const raw = getValue(debug, "feature_summary.raw_debug_evidence", {});
  const format = firstDefined(
    getValue(debug, "format_evidence.format_info.format"),
    getValue(raw, "format_info.format"),
    getValue(raw, "raw_result.image_info.format"),
  );
  const hasExif = firstDefined(
    getValue(debug, "format_evidence.exif_info.has_exif"),
    getValue(raw, "exif_info.has_exif"),
  );
  const modelStatus = firstDefined(
    getValue(raw, "raw_result.model_result.model_status"),
    getValue(raw, "raw_result.model_result.model_name"),
  );
  const forensic = firstDefined(
    getValue(raw, "raw_result.forensic_result.noise_estimate"),
    getValue(raw, "raw_result.forensic_result.edge_density"),
  );
  const consistency = firstDefined(
    getValue(debug, "consistency_checks.multi_resolution.consistency_status"),
    getValue(raw, "multi_resolution.consistency_status"),
    textFromValue(getValue(debug, "consistency_checks.uncertainty_flags"), ""),
  );
  return [
    evidenceLine(t("result.sourceProvenance"), provenance.provenance_note || (hasExif ? "EXIF / provenance hint present" : t("result.notAvailable")), provenance.c2pa_present ? "positive" : hasExif ? "positive" : "muted", provenance.c2pa_present || hasExif ? t("result.available") : t("result.notAvailableStatus")),
    evidenceLine(t("result.metadataLayer"), format || hasExif !== undefined ? `${format || "image"} · EXIF ${hasExif ? "present" : "limited"}` : t("result.notAvailable"), hasExif ? "positive" : "warning", format || hasExif !== undefined ? t("result.partial") : t("result.notAvailableStatus")),
    evidenceLine(t("result.aiModelLayer"), modelStatus || t("result.notAvailable"), modelStatus ? "neutral" : "muted", modelStatus ? t("result.partial") : t("result.notAvailableStatus")),
    evidenceLine(t("result.forensicLayer"), forensic !== undefined ? `noise / edge score: ${forensic}` : t("result.notAvailable"), forensic !== undefined ? "neutral" : "muted", forensic !== undefined ? t("result.available") : t("result.notAvailableStatus")),
  ].join("");
}

function productDetectionData(payload) {
  const root = getValue(payload, "data", payload) || {};
  if (root.result && root.input && Array.isArray(root.evidence_cards)) {
    return root;
  }
  const policy = root.policy_result || {};
  const input = {
    filename: firstDefined(root.filename, state.selectedSingleFile?.name, "uploaded image"),
    sha256: firstDefined(root.file_sha256, root.sha256, ""),
    mime_type: firstDefined(root.mime_type, "unknown"),
    width: firstDefined(root.width, getValue(root, "debug_evidence.image.width"), 0),
    height: firstDefined(root.height, getValue(root, "debug_evidence.image.height"), 0),
    file_size_bytes: firstDefined(root.file_size_bytes, 0),
  };
  return {
    report_id: firstDefined(root.report_id, root.id),
    input,
    result: {
      final_label: firstDefined(root.final_label, "uncertain"),
      risk_level: firstDefined(root.risk_level, "unknown"),
      confidence: firstDefined(root.confidence, 0),
      decision_reason: textFromValue(root.decision_reason),
      recommendation: textFromValue(root.recommendation),
      user_facing_summary: firstDefined(root.user_facing_summary, ""),
      technical_explanation: textFromValue(root.technical_explanation),
    },
    evidence_cards: Array.isArray(policy.evidence_cards) ? policy.evidence_cards : [],
    review_triggers: Array.isArray(root.review_triggers) ? root.review_triggers : Array.isArray(policy.review_triggers) ? policy.review_triggers : [],
    detectors: Array.isArray(root.detector_results)
      ? root.detector_results.map((item) => ({
          name: firstDefined(item.detector_id, item.name, "unknown"),
          role: firstDefined(item.role, "auxiliary"),
          ai_score: firstDefined(item.ai_score, 0),
          threshold: firstDefined(item.threshold, 0.5),
          label: firstDefined(item.predicted_label, item.label, "uncertain"),
          latency_ms: item.latency_ms,
          error: getValue(item, "error.message", null),
          version: firstDefined(item.detector_version, item.model_version, "unknown"),
          // P1-c LoRA badge — true when this detector loaded a fine-tuned PEFT adapter on top of the base HF weights
          fine_tuned: Boolean(firstDefined(item.fine_tuned, getValue(item, "debug.raw_output.raw_output_summary.peft_loaded"), false)),
          adapter_path: firstDefined(item.adapter_path, getValue(item, "debug.raw_output.raw_output_summary.peft_adapter_path"), ""),
        }))
      : [],
    policy: {
      policy_version: firstDefined(root.policy_version, policy.policy_version, "unknown"),
      policy_profile: firstDefined(root.policy_profile, policy.policy_profile, state.policyProfile),
      detector_version: firstDefined(root.detector_version, root.detector_registry_version, "unknown"),
      model_version: firstDefined(root.model_version, root.model_adapter_version, "unknown"),
      review_trigger_profile: firstDefined(root.review_trigger_profile, policy.review_trigger_profile, "strict_safe_plus"),
      rules_triggered: [textFromValue(root.decision_reason)].filter(Boolean),
    },
    review: {
      review_status: firstDefined(root.review_status, "unreviewed"),
      review_required: firstDefined(root.review_status, "") === "pending_review" || ["ai", "uncertain", "review_needed"].includes(normalizeFinalLabel(root.final_label)),
      review_reason: textFromValue(root.decision_reason),
    },
    timing: {
      total_latency_ms: firstDefined(root.total_latency_ms, root.latency_ms, 0),
    },
    compat: root,
  };
}

function normalizeProductLabel(label) {
  const value = String(label || "").toLowerCase().replace(/[-\s]/g, "_");
  if (["ai", "ai_generated", "likely_ai"].includes(value)) return "ai";
  if (["real", "likely_real", "real_photo"].includes(value)) return "real";
  if (["review", "review_needed", "needs_review", "pending_review"].includes(value)) return "review_needed";
  return "uncertain";
}

function displayProductLabel(label) {
  const key = normalizeProductLabel(label);
  if (key === "review_needed") return t("result.reviewNeeded");
  return displayLabel(key);
}

function productStatusLabel(status) {
  const key = String(status || "neutral").toLowerCase();
  return t(`evidenceStatus.${key}`) || key;
}

function detectorRoleLabel(role) {
  const key = String(role || "auxiliary").toLowerCase();
  return t(`detectorRole.${key}`) || key;
}

// P4 — in-house display name + hover explainer for each detector role. Public-facing
// surfaces only ever see these labels; the underlying open-source detector id is
// preserved in a `title` attribute so the row remains transparent on hover but not
// in the headline. Aligns with the user's direction not to surface Smogy/Ateeqq/dima806
// names in the dashboard.
function detectorEngineLabel(role) {
  const isZh = state.lang === "zh";
  const key = String(role || "auxiliary").toLowerCase();
  if (isZh) {
    if (key === "primary") return "主视觉判别引擎";
    if (key === "secondary") return "二审支持引擎";
    if (key === "baseline") return "传统取证基线";
    if (key === "diagnostic") return "诊断参考（不投票）";
    return "辅助引擎";
  }
  if (key === "primary") return "Primary Visual Engine";
  if (key === "secondary") return "Secondary Review Engine";
  if (key === "baseline") return "Forensic Baseline";
  if (key === "diagnostic") return "Diagnostic Reference (non-voting)";
  return "Auxiliary Engine";
}

function detectorEngineHint(role) {
  const isZh = state.lang === "zh";
  const key = String(role || "auxiliary").toLowerCase();
  if (isZh) {
    if (key === "primary") return "决定阈值门的主判别（本地微调 Swin），单独可定 AI";
    if (key === "secondary") return "命中阈值时为投票加权；单独绝不定 AI";
    if (key === "baseline") return "频域 / 噪声 / 元数据 / 报告类辅助信号";
    if (key === "diagnostic") return "FP 偏高，仅记录用作诊断 — 永远不参与投票";
    return "辅助信号 — 不直接定案";
  }
  if (key === "primary") return "Primary classifier (locally fine-tuned Swin); can decide AI on its own";
  if (key === "secondary") return "Adds vote weight when triggered; never decides AI on its own";
  if (key === "baseline") return "Frequency / noise / metadata / report-style auxiliary signals";
  if (key === "diagnostic") return "High-FP signal kept only as a reference — never votes";
  return "Auxiliary signal — does not decide on its own";
}

// P3 — Decision-flow strip rendered above the evidence-card grid. It abstracts
// the 5-stage Minerva pipeline without naming any underlying open-source detector
// (per design: present the pipeline as in-house). The status of each stage is
// derived from the evidence_cards grouped by `layer`, then the final node shows
// the resolved verdict so reviewers can read "how the judgement came out" at a
// glance without scrolling.
function decisionFlowStrip(product) {
  const cards = Array.isArray(product?.evidence_cards) ? product.evidence_cards : [];
  const result = product?.result || {};
  const verdict = normalizeProductLabel(result.final_label);
  // status priority — the strongest signal in a layer wins. Anything red/amber
  // surfaces over neutral/skipped so the strip "tells the story" honestly.
  const RANK = { support_ai: 4, support_real: 4, warning: 3, error: 3, neutral: 1, skipped: 0, "": 0 };
  const byLayer = {};
  for (const card of cards) {
    if (!card || typeof card !== "object") continue;
    const layer = String(firstDefined(card.layer, card.type, "policy")).toLowerCase();
    const status = String(firstDefined(card.status, "neutral")).toLowerCase();
    if (!byLayer[layer] || (RANK[status] || 0) > (RANK[byLayer[layer].status] || 0)) {
      byLayer[layer] = { status, summary: String(card.summary || card.title || "") };
    }
  }
  const isZh = state.lang === "zh";
  const STEPS = [
    { key: "source",   label: isZh ? "溯源核验" : "Provenance", hint: isZh ? "C2PA 数字签名 / 原图凭证" : "C2PA signature / origin proof" },
    { key: "metadata", label: isZh ? "元数据"   : "Metadata",   hint: isZh ? "EXIF / 拍摄设备 / 时间链" : "EXIF / device / time chain" },
    { key: "detector", label: isZh ? "Minerva 自研视觉检测" : "Minerva Visual Engine", hint: isZh ? "本地微调判别 + 二审合议" : "Locally fine-tuned classifier + secondary review" },
    { key: "forensic", label: isZh ? "取证特征" : "Forensic",   hint: isZh ? "频域 / 噪声 / 压缩痕迹" : "Frequency / noise / compression" },
    { key: "policy",   label: isZh ? "策略合议" : "Policy",     hint: isZh ? "阈值门 + 投票 + 不确定带" : "Threshold gate + voting + uncertainty" },
  ];
  // map status -> visual tone. support_ai = red triggered, support_real = blue clear, warning = amber, error = grey, neutral/none = muted
  const TONE = {
    support_ai:   { tone: "triggered", glyph: "▲" },
    support_real: { tone: "clear",     glyph: "✓" },
    warning:      { tone: "warning",   glyph: "!" },
    error:        { tone: "error",     glyph: "×" },
    neutral:      { tone: "neutral",   glyph: "·" },
    skipped:      { tone: "skipped",   glyph: "—" },
  };
  const verdictTone = verdict === "ai" ? "triggered" : verdict === "real" ? "clear" : "warning";
  const verdictText = displayProductLabel(result.final_label);
  const nodes = STEPS.map((step) => {
    const found = byLayer[step.key];
    const status = found?.status || "skipped";
    const tone = (TONE[status] || TONE.skipped).tone;
    const glyph = (TONE[status] || TONE.skipped).glyph;
    const statusText = found ? (t(`evidenceStatus.${status}`) || status) : (isZh ? "未触发" : "Not triggered");
    return `
      <li class="flow-node flow-tone-${tone}" title="${escapeHtml(step.hint)}">
        <span class="flow-glyph" aria-hidden="true">${escapeHtml(glyph)}</span>
        <div class="flow-text">
          <strong>${escapeHtml(step.label)}</strong>
          <span>${escapeHtml(statusText)}</span>
        </div>
      </li>`;
  }).join('<li class="flow-arrow" aria-hidden="true">›</li>');
  return `
    <div class="result-section decision-flow-strip" aria-label="${escapeHtml(isZh ? "判断流程" : "Decision Flow")}">
      <h4>${escapeHtml(isZh ? "判断流程 — 是怎么判出来的" : "Decision Flow — how we arrived at this verdict")}</h4>
      <ol class="flow-track">
        ${nodes}
        <li class="flow-arrow" aria-hidden="true">›</li>
        <li class="flow-node flow-verdict flow-tone-${verdictTone}">
          <span class="flow-glyph" aria-hidden="true">→</span>
          <div class="flow-text">
            <strong>${escapeHtml(isZh ? "最终结论" : "Final Verdict")}</strong>
            <span>${escapeHtml(verdictText)}</span>
          </div>
        </li>
      </ol>
    </div>`;
}

function evidenceCardGrid(cards) {
  const items = Array.isArray(cards) ? cards : [];
  if (!items.length) {
    return `<div class="day41-empty-line">${escapeHtml(t("result.noEvidenceCards"))}</div>`;
  }
  // P4 — small status glyph per evidence card so the grid reads at a glance.
  // Maps the existing evidence-card status (support_ai / support_real / warning /
  // neutral / error / skipped) to a glyph + tone class; backed up by CSS color
  // blocks. Pure rendering change — no backend touched.
  const GLYPH = { support_ai: "▲", support_real: "✓", warning: "!", error: "×", neutral: "·", skipped: "—" };
  const TONE = { support_ai: "triggered", support_real: "clear", warning: "warning", error: "error", neutral: "neutral", skipped: "skipped" };
  return `
    <div class="day41-evidence-grid">
      ${items
        .map((card) => {
          const status = String(firstDefined(card.status, "neutral")).toLowerCase();
          const layer = String(firstDefined(card.layer, card.type, "policy")).toLowerCase();
          const severity = String(firstDefined(card.severity, "low")).toLowerCase();
          const glyph = GLYPH[status] || "·";
          const tone = TONE[status] || "neutral";
          return `
            <article class="day41-evidence-card status-${slug(status)} severity-${slug(severity)} evidence-tone-${tone}">
              <div class="day41-card-head">
                <span class="evidence-card-glyph" aria-hidden="true">${escapeHtml(glyph)}</span>
                <span class="evidence-card-layer">${escapeHtml(t(`evidenceLayer.${layer}`) || layer)}</span>
                <em>${escapeHtml(productStatusLabel(status))}</em>
              </div>
              <h5>${escapeHtml(firstDefined(card.title, "Evidence"))}</h5>
              <p>${escapeHtml(firstDefined(card.summary, ""))}</p>
              <div class="day41-card-foot">
                <span>${escapeHtml(t("result.severity"))}: ${escapeHtml(t(`severity.${severity}`) || severity)}</span>
                <span>${escapeHtml(t("result.weight"))}: ${escapeHtml(String(firstDefined(card.weight, 0)))}</span>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function detectorSignalsPanel(detectors) {
  const items = Array.isArray(detectors) ? detectors : [];
  if (!items.length) {
    return `<div class="day41-empty-line">${escapeHtml(t("result.noDetectorSignals"))}</div>`;
  }
  return `
    <div class="day41-detector-list">
      ${items
        .map((detector) => {
          const score = Math.round(Math.max(0, Math.min(1, toNumber(detector.ai_score))) * 100);
          const label = normalizeProductLabel(detector.label === "error" ? "uncertain" : detector.label);
          const role = String(firstDefined(detector.role, "auxiliary")).toLowerCase();
          const fineTunedBadge = detector.fine_tuned
            ? `<span class="detector-finetune-badge" title="${escapeHtml(state.lang === "zh" ? "本检测器已加载本地微调适配器（LoRA），在生产策略下经隔离 test 集验证" : "This detector loaded a locally fine-tuned LoRA adapter, validated on the isolated test set under the production policy")}">${escapeHtml(state.lang === "zh" ? "LoRA 微调" : "LoRA Fine-Tuned")}</span>`
            : "";
          // P4: present the detector by its IN-HOUSE ROLE (per design: never expose Smogy/Ateeqq/dima806/etc.
          // brand names in the public-facing UI). The underlying detector id is preserved in a `title`
          // attribute for transparency on hover, plus a long-form role explainer lives on the same hover.
          const displayName = detectorEngineLabel(role);
          const roleHint = detectorEngineHint(role);
          const rowTitle = `${roleHint} · id=${firstDefined(detector.name, "unknown")}`;
          return `
            <div class="day41-detector-row ${detector.error ? "has-error" : ""}" title="${escapeHtml(rowTitle)}">
              <div>
                <strong>${escapeHtml(displayName)}${fineTunedBadge}</strong>
                <span>${escapeHtml(detectorRoleLabel(role))} · ${escapeHtml(firstDefined(detector.version, "unknown"))}</span>
              </div>
              <div class="day41-detector-score">
                <span style="width:${score}%"></span>
              </div>
              <em>${escapeHtml(detector.error ? t("labels.failed") : displayProductLabel(label))}</em>
              <small>${escapeHtml(score)}% / ${escapeHtml(t("result.threshold"))} ${escapeHtml(String(firstDefined(detector.threshold, "-")))}</small>
              ${detector.error ? `<p>${escapeHtml(detector.error)}</p>` : ""}
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function reviewTriggerPanel(triggers) {
  const items = Array.isArray(triggers) ? triggers.filter((item) => item && item.triggered) : [];
  if (!items.length) {
    return "";
  }
  return `
    <div class="result-section day41-review-trigger-panel">
      <h4>${escapeHtml(state.lang === "zh" ? "复核路由" : "Review Routing")}</h4>
      ${items
        .map((item) => {
          const message = state.lang === "zh" ? firstDefined(item.user_message_zh, item.reason) : firstDefined(item.user_message_en, item.reason);
          const details = item.details || {};
          return `
            <article class="day41-review-trigger-card">
              <div>
                <strong>${escapeHtml(message)}</strong>
                <span>${escapeHtml(state.lang === "zh" ? "建议复核，不作为 AI 直接判定" : "Review recommended; this is not a direct AI decision.")}</span>
              </div>
              <dl>
                <div><dt>${escapeHtml(state.lang === "zh" ? "视角差异" : "View disagreement")}</dt><dd>${escapeHtml(formatNumber(firstDefined(details.disagreement_score, 0), 4))}</dd></div>
                <div><dt>${escapeHtml(state.lang === "zh" ? "最高裁剪分" : "Max crop score")}</dt><dd>${escapeHtml(formatNumber(firstDefined(details.max_crop_score, 0), 4))}</dd></div>
                <div><dt>${escapeHtml(state.lang === "zh" ? "裁剪标签不一致" : "Crop labels disagree")}</dt><dd>${escapeHtml(details.crop_labels_disagree ? t("common.yes") : t("common.no"))}</dd></div>
              </dl>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderSingleResult(payload) {
  state.currentResult = { kind: "single", payload };
  state.resultView = "simple";
  const product = productDetectionData(payload);
  const data = product.result || {};
  const input = product.input || {};
  const label = firstDefined(data.final_label, "uncertain");
  const risk = firstDefined(data.risk_level, "unknown");
  const filename = firstDefined(input.filename, state.selectedSingleFile?.name, "uploaded image");
  const summary = firstDefined(data.user_facing_summary, resultSummaryText(data));
  const reason = textFromValue(data.decision_reason);
  const recommendation = textFromValue(data.recommendation);
  const confidencePercent = Math.round(Math.max(0, Math.min(1, toNumber(data.confidence))) * 100);
  const reportId = firstDefined(product.report_id, getValue(product, "compat.report_id"), getValue(product, "compat.id"));
  const reportNotice = reportId ? t("result.reportCreated", { id: reportId }) : t("result.reportCenterHint");
  const latency = firstDefined(getValue(product, "timing.total_latency_ms"), 0);
  const policy = product.policy || {};
  const review = product.review || {};
  const profileName = firstDefined(policy.policy_profile, policy.review_trigger_profile, state.policyProfile, "strict_safe_plus");
  updateConsoleScanState(review.review_required ? "review" : "success");

  elements.uploadResult.innerHTML = `
    <article class="trust-result demo-result ${slug(risk)}">
      <div data-result-panel="simple">
        <div class="result-topline">
          <div>
            <p class="eyebrow">${escapeHtml(t("result.topVerdict"))}</p>
            <h3 class="result-verdict">${escapeHtml(displayProductLabel(label))}</h3>
            <span title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
          </div>
          <div class="verdict-aside">
            <span class="chain-badge">${escapeHtml(t("result.evidenceChain"))}</span>
            <span class="badge ${slug(risk)}">${escapeHtml(displayLabel(risk))}</span>
            <div class="verdict-score" style="--score: ${confidencePercent * 3.6}deg">
              <span data-animate-confidence="${confidencePercent}">0%</span>
            </div>
          </div>
        </div>
        <div class="trust-meter" aria-hidden="true"><span style="width: ${confidencePercent}%"></span></div>
        <div class="result-metrics">
          <div><span>${escapeHtml(t("result.verdict"))}</span><strong>${escapeHtml(displayProductLabel(label))}</strong></div>
          <div><span>${escapeHtml(t("result.riskLevel"))}</span><strong>${escapeHtml(displayLabel(risk))}</strong></div>
          <div><span>${escapeHtml(t("result.confidence"))}</span><strong>${escapeHtml(formatConfidence(data.confidence))}</strong></div>
          <div><span>${escapeHtml(t("result.latency"))}</span><strong>${escapeHtml(latency ? `${latency} ms` : "-")}</strong></div>
        </div>
        <div class="result-section day41-summary-panel">
          <h4>${escapeHtml(t("result.oneLineConclusion"))}</h4>
          <p>${escapeHtml(summary || reason)}</p>
          <div class="day41-report-meta">
            <span>${escapeHtml(t("result.reportId"))}: <strong>${escapeHtml(reportId || "-")}</strong></span>
            <span>${escapeHtml(t("result.reviewStatus"))}: <strong>${escapeHtml(getReviewStatusLabel(review.review_status))}</strong></span>
          </div>
        </div>
        ${decisionFlowStrip(product)}
        <div class="result-section evidence-tags-section">
          <h4>${escapeHtml(t("result.evidenceSummary"))}</h4>
          ${evidenceCardGrid(product.evidence_cards)}
        </div>
        ${reviewTriggerPanel(product.review_triggers)}
        <div class="result-section day41-detectors-section">
          <h4>${escapeHtml(t("result.detectorSignals"))}</h4>
          ${detectorSignalsPanel(product.detectors)}
        </div>
        <div class="result-section day41-policy-panel">
          <h4>${escapeHtml(t("result.policyExplanation"))}</h4>
          <div class="compact-grid">
            <div><span>${escapeHtml(t("result.policyVersion"))}</span><strong>${escapeHtml(firstDefined(policy.policy_version, "-"))}</strong></div>
            <div><span>${escapeHtml(t("result.detectorVersion"))}</span><strong>${escapeHtml(firstDefined(policy.detector_version, "-"))}</strong></div>
            <div><span>${escapeHtml(t("result.modelVersion"))}</span><strong>${escapeHtml(firstDefined(policy.model_version, "-"))}</strong></div>
            <div><span>${escapeHtml(state.lang === "zh" ? "安全模式" : "Safety Mode")}</span><strong>${escapeHtml(profileName === "strict_safe_plus" ? (state.lang === "zh" ? "标准安全模式 strict_safe_plus" : "Standard Safety Mode strict_safe_plus") : profileName)}</strong></div>
            <div><span>${escapeHtml(t("result.reviewRequired"))}</span><strong>${escapeHtml(review.review_required ? t("common.yes") : t("common.no"))}</strong></div>
          </div>
          ${profileName === "high_recall_review" ? `<p class="day41-profile-warning">${escapeHtml(state.lang === "zh" ? "高召回复核模式会显著增加真实图复核比例。" : "High-recall review mode can substantially increase real-image review burden.")}</p>` : ""}
          <p>${escapeHtml(reason)}</p>
        </div>
        <div class="result-section recommendation-block">
          <h4>${escapeHtml(t("result.recommendation"))}</h4>
          <p>${escapeHtml(recommendation || summary)}</p>
        </div>
        <div class="result-section report-created-block">
          <h4>${escapeHtml(t("reportCenter.title"))}</h4>
          <p>${escapeHtml(reportNotice)}</p>
        </div>
        <div class="result-section">
          <h4>${escapeHtml(t("result.reason"))}</h4>
          <p>${escapeHtml(reason)}</p>
        </div>
        <div class="result-actions">
          <button class="button button-primary" type="button" data-action="view-current-detail">${escapeHtml(t("result.viewDetail"))}</button>
          <button class="button button-ghost" type="button" data-action="open-current-html" ${reportId ? "" : "disabled"}>${escapeHtml(t("result.viewHtmlReport"))}</button>
          <button class="button button-ghost" type="button" data-action="goto-report-center">${escapeHtml(t("result.goReportCenter"))}</button>
          <button class="button button-secondary" type="button" data-action="copy-current-json">${escapeHtml(t("result.copyJson"))}</button>
          <button class="button button-ghost" type="button" data-action="download-current-json">${escapeHtml(t("result.exportJson"))}</button>
          <button class="button button-ghost" type="button" data-action="switch-result-json">${escapeHtml(t("recent.viewJson"))}</button>
          <button class="button button-ghost" type="button" disabled>${escapeHtml(t("result.exportPdf"))}<span class="soon-badge">${escapeHtml(t("result.comingSoon"))}</span></button>
        </div>
      </div>
      ${resultJsonPanel(payload)}
    </article>
  `;
  applyResultRevealClasses(confidencePercent);
  setUploadButtons();
}

function renderBatchResult(payload) {
  state.currentResult = { kind: "batch", payload };
  state.resultView = "simple";
  updateConsoleScanState("success");
  const results = Array.isArray(payload?.results) ? payload.results : [];
  const successfulResults = results
    .filter((item) => item && item.status === "success")
    .map((item) => ({ input: item.input || {}, result: item.result || {} }));
  const confidences = successfulResults.map((item) => toNumber(item.result.confidence)).filter((value) => value > 0);
  const averageConfidence = confidences.length ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length : 0;
  const counts = successfulResults.reduce(
    (acc, item) => {
      acc[normalizeFinalLabel(item.result.final_label)] += 1;
      if (String(item.result.risk_level || "").toLowerCase() === "high") acc.highRisk += 1;
      return acc;
    },
    { ai: 0, real: 0, uncertain: 0, highRisk: 0 },
  );
  const failed = toNumber(firstDefined(payload.failed, results.filter((item) => item.status === "failed").length));

  elements.uploadResult.innerHTML = `
    <article class="trust-result demo-result batch-result">
      <div data-result-panel="simple">
        <div class="result-topline">
          <div>
            <p class="eyebrow">${escapeHtml(t("result.batchComplete"))}</p>
            <h3 class="result-verdict">${escapeHtml(t("batch.succeeded", { succeeded: formatInteger(firstDefined(payload.succeeded, successfulResults.length)), failed: formatInteger(failed) }))}</h3>
            <span>${escapeHtml(firstDefined(payload.batch_id, "batch"))}</span>
          </div>
          <div class="verdict-score">
            <span>${escapeHtml(formatInteger(firstDefined(payload.total, results.length)))}</span>
          </div>
        </div>
        <div class="result-metrics">
          <div><span>${escapeHtml(t("batch.total"))}</span><strong>${escapeHtml(formatInteger(firstDefined(payload.total, results.length)))}</strong></div>
          <div><span>${escapeHtml(t("batch.ai"))}</span><strong>${escapeHtml(formatInteger(counts.ai))}</strong></div>
          <div><span>${escapeHtml(t("batch.uncertain"))}</span><strong>${escapeHtml(formatInteger(counts.uncertain))}</strong></div>
          <div><span>${escapeHtml(t("batch.highRisk"))}</span><strong>${escapeHtml(formatInteger(counts.highRisk))}</strong></div>
          <div><span>${escapeHtml(t("batch.avgConfidence"))}</span><strong>${escapeHtml(formatConfidence(averageConfidence))}</strong></div>
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
                    <span class="badge failed">${escapeHtml(displayLabel("failed"))}</span>
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
                  <span class="badge ${slug(risk)}">${escapeHtml(displayLabel(risk))}</span>
                  <span>${escapeHtml(formatConfidence(result.confidence))}</span>
                </div>
              `;
            })
            .join("")}
        </div>
        <div class="result-actions">
          <button class="button button-secondary" type="button" data-action="copy-current-json">${escapeHtml(t("result.copyJson"))}</button>
          <button class="button button-ghost" type="button" data-action="download-current-json">${escapeHtml(t("result.exportJson"))}</button>
          <button class="button button-ghost" type="button" data-action="switch-result-json">${escapeHtml(t("recent.viewJson"))}</button>
          <button class="button button-ghost" type="button" disabled>${escapeHtml(t("result.exportPdf"))}<span class="soon-badge">${escapeHtml(t("result.comingSoon"))}</span></button>
        </div>
      </div>
      ${resultJsonPanel(payload)}
    </article>
  `;
  applyResultRevealClasses();
}

async function loadDashboardData({ silent = false } = {}) {
  if (state.dashboardLoading) {
    return;
  }

  state.dashboardLoading = true;
  elements.refreshButton.disabled = true;
  elements.refreshButton.textContent = silent ? t("nav.syncing") : t("nav.refreshing");
  setServiceStatus("loading", t("nav.checking"));

  try {
    const health = await ensureApiBaseReachable({ timeoutMs: 1200 });
    const modelStatus = await fetchJson(API_ENDPOINTS.modelStatus, { timeoutMs: 5000 }).catch(() => null);
    const policyProfiles = await fetchJson(API_ENDPOINTS.policyProfiles, { timeoutMs: 5000 }).catch(() => null);
    state.systemHealth = health;
    state.modelStatus = modelStatus;
    state.policyProfiles = Array.isArray(policyProfiles?.profiles) ? policyProfiles.profiles : state.policyProfiles;
    if (!localStorage.getItem("minerva.policyProfile") && policyProfiles?.product_default_policy_profile) {
      setPolicyProfile(policyProfiles.product_default_policy_profile);
    } else {
      renderPolicyProfileSwitch();
    }
    setServiceStatus("online", t("nav.online"));
    renderSystemStatus(health, false, modelStatus);
  } catch (error) {
    state.systemHealth = null;
    state.modelStatus = null;
    setServiceStatus("offline", error.message || `Backend not connected. Start FastAPI at ${DEFAULT_LOCAL_API_BASE_URL}.`);
    renderSystemStatus(null, true);
    renderSummary({});
    renderRecentResultsError();
    renderChartsError();
    renderReviewQueueError();
    renderTrainingLabelQueueError();
    renderCalibrationReadiness(null, true);
    state.dashboardLoading = false;
    elements.refreshButton.disabled = false;
    elements.refreshButton.textContent = t("nav.refresh");
    return;
  }

  const [
    summaryResult,
    recentResult,
    chartResult,
    queueResult,
    reviewCalibrationResult,
    policyReplayResult,
    stressPackResult,
    trainingReadinessResult,
    trainingLabelQueueResult,
  ] = await Promise.allSettled([
    fetchJson(API_ENDPOINTS.summary, { timeoutMs: 15000 }),
    fetchJson(reportSearchUrl(), { timeoutMs: 15000 }),
    fetchJson(API_ENDPOINTS.chartData, { timeoutMs: 15000 }),
    fetchJson(API_ENDPOINTS.reportQueue, { timeoutMs: 15000 }),
    fetchJson(API_ENDPOINTS.reviewCalibration, { timeoutMs: 8000 }),
    fetchJson(API_ENDPOINTS.policyReplay, { timeoutMs: 8000 }),
    fetchJson(API_ENDPOINTS.scenarioStressPack, { timeoutMs: 8000 }),
    fetchJson(API_ENDPOINTS.trainingReadiness, { timeoutMs: 8000 }),
    fetchJson(API_ENDPOINTS.trainingLabelQueue, { timeoutMs: 8000 }),
  ]);

  if (summaryResult.status === "fulfilled") {
    renderSummary(summaryResult.value);
  } else {
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

  if (queueResult.status === "fulfilled") {
    renderReviewQueue(queueResult.value);
  } else {
    renderReviewQueueError();
  }

  if (trainingLabelQueueResult.status === "fulfilled") {
    renderTrainingLabelQueue(trainingLabelQueueResult.value);
  } else {
    renderTrainingLabelQueueError();
  }

  if (
    reviewCalibrationResult.status === "fulfilled" ||
    policyReplayResult.status === "fulfilled" ||
    stressPackResult.status === "fulfilled" ||
    trainingReadinessResult.status === "fulfilled"
  ) {
    state.calibrationReadiness = {
      reviewCalibration: reviewCalibrationResult.status === "fulfilled" ? reviewCalibrationResult.value : null,
      policyReplay: policyReplayResult.status === "fulfilled" ? policyReplayResult.value : null,
      scenarioStressPack: stressPackResult.status === "fulfilled" ? stressPackResult.value : null,
      trainingReadiness: trainingReadinessResult.status === "fulfilled" ? trainingReadinessResult.value : null,
    };
    renderCalibrationReadiness(state.calibrationReadiness);
  } else {
    state.calibrationReadiness = null;
    renderCalibrationReadiness(null, true);
  }

  state.dashboardLoading = false;
  elements.refreshButton.disabled = false;
  elements.refreshButton.textContent = t("nav.refresh");
}

function syncReportFiltersFromControls() {
  state.reportFilters = {
    q: elements.reportSearchInput?.value || "",
    risk_level: elements.reportRiskFilter?.value || "all",
    final_label: elements.reportLabelFilter?.value || "all",
    review_status: elements.reportReviewFilter?.value || "all",
    date_range: elements.reportDateFilter?.value || "all",
    confidence_range: elements.reportConfidenceFilter?.value || "all",
    sort: elements.reportSortFilter?.value || "newest",
  };
}

async function refreshReportCenter({ silent = true } = {}) {
  syncReportFiltersFromControls();
  const [reportsResult, queueResult, trainingQueueResult] = await Promise.allSettled([
    fetchJson(reportSearchUrl()),
    fetchJson(API_ENDPOINTS.reportQueue),
    fetchJson(API_ENDPOINTS.trainingLabelQueue, { timeoutMs: 8000 }),
  ]);
  if (reportsResult.status === "fulfilled") {
    renderRecentResults(reportsResult.value);
  } else {
    renderRecentResultsError();
  }
  if (queueResult.status === "fulfilled") {
    renderReviewQueue(queueResult.value);
  } else {
    renderReviewQueueError();
  }
  if (trainingQueueResult.status === "fulfilled") {
    renderTrainingLabelQueue(trainingQueueResult.value);
  } else {
    renderTrainingLabelQueueError();
  }
  if (!silent) {
    const hasCoreData = reportsResult.status === "fulfilled" || queueResult.status === "fulfilled";
    setServiceStatus(hasCoreData ? "online" : "offline", hasCoreData ? t("nav.online") : t("nav.apiError"));
  }
}

function scheduleReportRefresh() {
  window.clearTimeout(state.reportSearchTimer);
  state.reportSearchTimer = window.setTimeout(() => refreshReportCenter(), 220);
}

function resetReportFilters() {
  if (elements.reportSearchInput) elements.reportSearchInput.value = "";
  if (elements.reportRiskFilter) elements.reportRiskFilter.value = "all";
  if (elements.reportLabelFilter) elements.reportLabelFilter.value = "all";
  if (elements.reportReviewFilter) elements.reportReviewFilter.value = "all";
  if (elements.reportDateFilter) elements.reportDateFilter.value = "all";
  if (elements.reportConfidenceFilter) elements.reportConfidenceFilter.value = "all";
  if (elements.reportSortFilter) elements.reportSortFilter.value = "newest";
  syncReportFiltersFromControls();
  refreshReportCenter();
}

function downloadBlob(text, filename, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function exportReportCenter(format) {
  if (state.exportLoading) return;
  state.exportLoading = true;
  document.querySelectorAll(".report-export-button").forEach((button) => {
    button.disabled = true;
    button.dataset.originalText = button.textContent || "";
    button.textContent = t("reportCenter.exporting");
  });
  syncReportFiltersFromControls();
  try {
    await ensureApiBaseReachable({ timeoutMs: 5000 });
    const response = await fetch(reportExportUrl(format), { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`${t("reportCenter.exportFailed")} ${response.status}`);
    }
    const suffix = timestampForFilename();
    if (format === "csv") {
      downloadBlob(await response.text(), `report_center_export_${suffix}.csv`, "text/csv;charset=utf-8");
      return;
    }
    const payload = await response.json();
    downloadJson(payload, `report_center_export_${suffix}.json`);
  } finally {
    state.exportLoading = false;
    document.querySelectorAll(".report-export-button").forEach((button) => {
      button.disabled = false;
      if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
        delete button.dataset.originalText;
      }
    });
  }
}

async function runSingleDetection() {
  if (!state.selectedSingleFile) {
    setDemoTab("upload");
    document.querySelector("#trust-console")?.scrollIntoView({ behavior: state.prefersReducedMotion ? "auto" : "smooth", block: "start" });
    renderErrorResult(statusCopy("noFile"));
    flashUploadError(elements.singleUploadCard, statusCopy("noFile"));
    return;
  }
  if (state.singleLoading) {
    return;
  }
  state.singleLoading = true;
  state.singleStatus = "detecting";
  state.currentResult = null;
  const fileForDetection = state.selectedSingleFile;
  document.body.classList.add("is-scanning");
  setUploadButtons();
  renderLoadingResult(statusCopy("detectingBody"));

  try {
    await waitForScanReady();
    const singleUrl = `${API_ENDPOINTS.detectSingle}?policy_profile=${encodeURIComponent(state.policyProfile)}`;
    const payload = await postSingleDetectionWithRetry(singleUrl, fileForDetection);
    state.singleStatus = "success";
    renderSingleResult(payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    state.singleStatus = "error";
    const message = `${t("result.detectFailedFriendly")} ${error.message || ""}`.trim();
    renderErrorResult(message, {
      success: false,
      data: null,
      error: {
        status: error.status || 0,
        message,
        detail: error.payload || null,
      },
    });
  } finally {
    state.singleLoading = false;
    document.body.classList.remove("is-scanning");
    setUploadButtons();
  }
}

const detectSingleImage = runSingleDetection;

async function postBatchDetection(formData) {
  await ensureApiBaseReachable({ timeoutMs: 5000 });
  try {
    const job = await fetchJson(API_ENDPOINTS.batchJobSubmit, {
      method: "POST",
      body: formData,
      timeoutMs: 30000,
    });
    if (job?.job_id) {
      return await pollBatchJob(job.job_id, Number(job.total || state.selectedBatchFiles.length || 0));
    }
  } catch (error) {
    if (![404, 405].includes(error.status)) {
      throw error;
    }
  }

  let lastError = null;
  for (const endpoint of API_ENDPOINTS.detectBatchCandidates) {
    try {
      return await fetchJson(endpoint, {
        method: "POST",
        body: formData,
        timeoutMs: 180000,
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

async function pollBatchJob(jobId, total) {
  const started = Date.now();
  const timeoutMs = 180000;
  while (Date.now() - started < timeoutMs) {
    const status = await fetchJson(API_ENDPOINTS.batchJobStatus(jobId), { timeoutMs: 15000 });
    if (status.status === "completed") {
      return await fetchJson(API_ENDPOINTS.batchJobResult(jobId), { timeoutMs: 30000 });
    }
    if (status.status === "failed") {
      const detail = status.error?.message || "Batch job failed.";
      throw new Error(detail);
    }
    const processed = Math.min(Number(status.processed || 0), Number(total || status.total || 0));
    const totalText = formatInteger(Number(total || status.total || 0));
    const progressText = processed > 0 ? `${formatInteger(processed)}/${totalText}` : totalText;
    renderLoadingResult(
      state.lang === "zh"
        ? `批量任务${status.status === "queued" ? "排队中" : "运行中"}：${progressText} 张图片`
        : `Batch job ${status.status === "queued" ? "queued" : "running"}: ${progressText} images`
    );
    await sleep(1500);
  }
  throw new Error("Batch job timed out while waiting for results.");
}

async function detectBatchImages() {
  if (!state.selectedBatchFiles.length || state.batchLoading) {
    return;
  }
  state.batchLoading = true;
  state.currentResult = null;
  document.body.classList.add("is-scanning");
  setUploadButtons();
  renderLoadingResult(t("batch.analyzingImages", { count: state.selectedBatchFiles.length }));

  const formData = new FormData();
  state.selectedBatchFiles.forEach((file) => {
    formData.append("files", file);
  });
  formData.append("policy_profile", state.policyProfile);

  try {
    const payload = await postBatchDetection(formData);
    renderBatchResult(payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    renderErrorResult(`${t("result.detectFailedFriendly")} ${error.message || ""}`.trim());
  } finally {
    state.batchLoading = false;
    document.body.classList.remove("is-scanning");
    setUploadButtons();
  }
}

function downloadJson(payload, filename = "minerva-result.json") {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function copyJson(payload) {
  const text = JSON.stringify(payload, null, 2);
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // Fall back to the legacy textarea copy path below.
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("Copy failed");
  }
}

function currentPayload() {
  return state.currentResult?.payload || null;
}

function selectSingleFile(file) {
  if (file && !isSupportedImage(file)) {
    elements.singleInput.value = "";
    state.selectedSingleFile = null;
    state.singleStatus = "idle";
    state.currentResult = null;
    renderSinglePreview(null);
    renderEmptyResult();
    updateFileLabels();
    setUploadButtons();
    flashUploadError(elements.singleUploadCard, t("single.invalidType"));
    return;
  }
  state.selectedSingleFile = file || null;
  state.singleStatus = file ? "selected" : "idle";
  state.currentResult = null;
  if (file) setDemoTab("upload");
  updateFileLabels();
  renderSinglePreview(state.selectedSingleFile);
  renderEmptyResult();
  setUploadButtons();
}

function selectBatchFiles(files) {
  const allFiles = Array.from(files || []);
  const images = supportedImages(allFiles);
  if (allFiles.length && images.length < allFiles.length) {
    flashUploadError(elements.batchUploadCard, t("batch.invalidType"));
  }
  state.selectedBatchFiles = images;
  if (images.length) setDemoTab("batch");
  updateFileLabels();
  renderBatchPreview();
  setUploadButtons();
}

function clearBatchFiles() {
  state.selectedBatchFiles = [];
  elements.batchInput.value = "";
  updateFileLabels();
  renderBatchPreview();
  setUploadButtons();
}

function setupDropZone({ zone, input, card, multiple }) {
  if (!zone || !input || !card) {
    return;
  }
  const dragKey = multiple ? "batchDragDepth" : "singleDragDepth";
  const setDragging = (active) => {
    card.classList.toggle("is-dragging", active);
    updateFileLabels();
  };

  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      if (eventName === "dragenter") {
        state[dragKey] += 1;
      }
      setDragging(true);
    });
  });

  zone.addEventListener("dragleave", (event) => {
    event.preventDefault();
    state[dragKey] = Math.max(0, state[dragKey] - 1);
    setDragging(state[dragKey] > 0);
  });

  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    state[dragKey] = 0;
    setDragging(false);
    const droppedFiles = Array.from(event.dataTransfer.files || []);
    if (multiple) {
      selectBatchFiles(droppedFiles);
    } else {
      selectSingleFile(droppedFiles[0] || null);
    }
  });
}

function handleSegmentedKeyboard(event, selector, activate) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    return;
  }
  const buttons = Array.from(event.currentTarget.querySelectorAll(selector));
  if (!buttons.length) return;
  const currentIndex = Math.max(0, buttons.indexOf(document.activeElement));
  const nextIndex = event.key === "Home"
    ? 0
    : event.key === "End"
    ? buttons.length - 1
    : event.key === "ArrowLeft"
    ? (currentIndex - 1 + buttons.length) % buttons.length
    : (currentIndex + 1) % buttons.length;
  event.preventDefault();
  buttons[nextIndex].focus();
  activate(buttons[nextIndex]);
}

elements.singleInput.addEventListener("change", (event) => {
  selectSingleFile(event.target.files?.[0] || null);
});

elements.batchInput.addEventListener("change", (event) => {
  selectBatchFiles(event.target.files || []);
});

elements.singleButton.addEventListener("click", runSingleDetection);
elements.batchButton.addEventListener("click", detectBatchImages);
elements.refreshButton.addEventListener("click", () => loadDashboardData());
elements.navDetectButton?.addEventListener("click", (event) => {
  event.preventDefault();
  setDemoTab("upload");
  document.querySelector("#trust-console")?.scrollIntoView({ behavior: state.prefersReducedMotion ? "auto" : "smooth", block: "start" });
  if (state.singleLoading) {
    return;
  }
  if (!state.selectedSingleFile) {
    renderEmptyResult();
    flashUploadError(elements.singleUploadCard, statusCopy("noFile"));
    return;
  }
  runSingleDetection();
});

elements.auditFilters?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) {
    return;
  }
  state.recentFilter = button.dataset.filter || "all";
  elements.auditFilters.querySelectorAll("[data-filter]").forEach((node) => {
    node.classList.toggle("active", node === button);
  });
  const filtered = filteredRecentResults();
  renderRecentRows(filtered, filtered.length);
});

elements.reportSearchInput?.addEventListener("input", scheduleReportRefresh);
[
  elements.reportRiskFilter,
  elements.reportLabelFilter,
  elements.reportReviewFilter,
  elements.reportDateFilter,
  elements.reportConfidenceFilter,
  elements.reportSortFilter,
].forEach((control) => {
  control?.addEventListener("change", () => refreshReportCenter());
});
elements.reportResetButton?.addEventListener("click", resetReportFilters);

window.addEventListener("minerva:report-review-updated", () => {
  refreshReportCenter();
  loadDashboardData({ silent: true });
});

elements.recentBody?.addEventListener("keydown", (event) => {
  const row = event.target.closest(".audit-row");
  if (!row || (event.key !== "Enter" && event.key !== " ")) {
    return;
  }
  event.preventDefault();
  row.click();
});

elements.demoTabs?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-demo-tab]");
  if (!button) return;
  setDemoTab(button.dataset.demoTab);
});
elements.demoTabs?.addEventListener("keydown", (event) => {
  handleSegmentedKeyboard(event, "[data-demo-tab]", (button) => setDemoTab(button.dataset.demoTab));
});

elements.resultViewToggle?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-result-view]");
  if (!button) return;
  setResultView(button.dataset.resultView);
});
elements.resultViewToggle?.addEventListener("keydown", (event) => {
  handleSegmentedKeyboard(event, "[data-result-view]", (button) => setResultView(button.dataset.resultView));
});

elements.policyProfileSwitch?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-policy-profile]");
  if (!button) return;
  setPolicyProfile(button.dataset.policyProfile);
});
elements.policyProfileSwitch?.addEventListener("keydown", (event) => {
  handleSegmentedKeyboard(event, "[data-policy-profile]", (button) => setPolicyProfile(button.dataset.policyProfile));
});

document.addEventListener("click", (event) => {
  const anchor = event.target.closest('a[href^="#"]');
  if (!anchor) {
    return;
  }
  const href = anchor.getAttribute("href");
  if (!href || href.length < 2) {
    return;
  }
  const target = document.querySelector(href);
  if (!target) {
    return;
  }
  event.preventDefault();
  target.scrollIntoView({ behavior: state.prefersReducedMotion ? "auto" : "smooth", block: "start" });
});

setupDropZone({
  zone: elements.singleDropZone,
  input: elements.singleInput,
  card: elements.singleUploadCard,
  multiple: false,
});
setupDropZone({
  zone: elements.batchDropZone,
  input: elements.batchInput,
  card: elements.batchUploadCard,
  multiple: true,
});

document.querySelectorAll(".language-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang === "zh" ? "zh" : "en";
    localStorage.setItem("minerva.lang", state.lang);
    applyI18n();
    loadDashboardData({ silent: true });
  });
});

document.addEventListener("click", async (event) => {
  const disabledLink = event.target.closest('a[aria-disabled="true"]');
  if (disabledLink) {
    event.preventDefault();
    return;
  }

  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }
  const action = target.dataset.action;
  try {
    if (action === "remove-single-file") {
      elements.singleInput.value = "";
      selectSingleFile(null);
      return;
    }
    if (action === "run-single-detection") {
      await runSingleDetection();
      return;
    }
    if (action === "rechoose-single-file") {
      elements.singleInput.click();
      return;
    }
    if (action === "clear-batch-files") {
      clearBatchFiles();
      return;
    }
    if (action === "download-current-json" && currentPayload()) {
      downloadJson(currentPayload(), `minerva-${Date.now()}-result.json`);
      target.textContent = t("result.downloadReady");
    }
    if (action === "switch-result-json") {
      setResultView("json");
      return;
    }
    if (action === "view-current-detail" && currentPayload()) {
      const data = getValue(currentPayload(), "data", currentPayload()) || {};
      window.DetectionDetails?.open?.(data, { trigger: target });
      return;
    }
    if (action === "open-current-html" && currentPayload()) {
      const data = getValue(currentPayload(), "data", currentPayload()) || {};
      const reportId = firstDefined(data.report_id, data.id);
      if (!reportId) throw new Error(t("result.htmlOpenFailed"));
      const opened = window.open(API_ENDPOINTS.reportHtml(reportId), "_blank", "noopener");
      if (!opened) throw new Error(t("result.htmlOpenFailed"));
      return;
    }
    if (action === "goto-report-center") {
      document.querySelector("#audit-log")?.scrollIntoView({ behavior: state.prefersReducedMotion ? "auto" : "smooth", block: "start" });
      refreshReportCenter({ silent: true });
      return;
    }
    if (action === "copy-current-json" && currentPayload()) {
      await copyJson(currentPayload());
      target.textContent = t("result.copied");
    }
    if (action === "open-recent-detail" || action === "view-recent-detail" || action === "report-recent-detail" || action === "review-recent-detail" || action === "review-queue-detail") {
      const payload = state.recentResults.get(target.dataset.id);
      if (payload) {
        const debugPayload = {
          id: firstDefined(payload.id, payload.history_file, target.dataset.id),
          filename: firstDefined(payload.filename, "unknown"),
          final_label: firstDefined(payload.final_label, payload.label, "uncertain"),
        };
        console.log(action === "report-recent-detail" ? "[Day27] report clicked" : "[Day27] detail clicked", debugPayload);
        if (!window.DetectionDetails?.open) {
          console.warn("[Day27] detail drawer module is not available");
          return;
        }
        window.DetectionDetails.open(payload, {
          trigger: target,
          focusReport: action === "report-recent-detail",
          focusReview: action === "review-recent-detail" || action === "review-queue-detail",
        });
      }
      return;
    }
    if (action === "training-label-quick-review") {
      await quickReviewTrainingLabel(target.dataset.id, target.dataset.reviewStatus, target);
      return;
    }
    if (action === "rebuild-training-readiness") {
      await rebuildTrainingReadiness(target);
      return;
    }
    if (action === "copy-recent-json") {
      const payload = state.recentResults.get(target.dataset.id);
      if (payload) {
        if (window.DetectionDetails?.copyJson) {
          await window.DetectionDetails.copyJson(payload);
        } else {
          await copyJson(payload);
        }
        target.textContent = t("result.copied");
      }
      return;
    }
    if (action === "export-report-center-json") {
      await exportReportCenter("json");
      return;
    }
    if (action === "export-report-center-csv") {
      await exportReportCenter("csv");
      return;
    }
  } catch (error) {
    if (action?.startsWith("export-report-center")) {
      target.textContent = t("reportCenter.exportFailed");
    } else if (action === "open-current-html") {
      target.textContent = t("result.htmlOpenFailed");
    } else if (action === "training-label-quick-review") {
      target.textContent = t("reportCenter.trainingQueue.saveFailed");
    } else if (action === "rebuild-training-readiness") {
      target.textContent = t("reportCenter.trainingQueue.saveFailed");
    } else {
      target.textContent = t("result.copyFailed");
    }
    console.warn("[Day30] UI action failed", error);
  }
});

document.querySelectorAll(".logo-mark img").forEach((img) => {
  img.addEventListener("error", () => {
    img.style.display = "none";
  });
});

mergeTranslations(translations.zh, {
  common: {
    yes: "是",
    no: "否",
  },
  result: {
    reviewNeeded: "需要复核",
    oneLineConclusion: "一句话结论",
    reportId: "报告 ID",
    reviewStatus: "复核状态",
    reviewRequired: "需要复核",
    detectorSignals: "检测器信号",
    policyExplanation: "策略说明",
    policyVersion: "策略版本",
    detectorVersion: "检测器版本",
    modelVersion: "模型版本",
    latency: "耗时",
    threshold: "阈值",
    severity: "严重度",
    weight: "权重",
    noEvidenceCards: "当前没有可展示的证据卡片。",
    noDetectorSignals: "当前没有可展示的检测器信号。",
  },
  evidenceLayer: {
    source: "来源",
    metadata: "元数据",
    detector: "检测器",
    forensic: "取证",
    policy: "策略",
  },
  evidenceStatus: {
    support_ai: "支持 AI",
    support_real: "支持真实",
    neutral: "中性",
    warning: "警告",
    error: "错误",
  },
  detectorRole: {
    primary: "主检测器",
    auxiliary: "辅助证据",
    disabled: "已禁用",
    legacy: "旧版基线",
    error: "错误",
  },
  severity: {
    low: "低",
    medium: "中",
    high: "高",
  },
});

mergeTranslations(translations.en, {
  common: {
    yes: "Yes",
    no: "No",
  },
  result: {
    reviewNeeded: "Review Needed",
    oneLineConclusion: "One-line conclusion",
    reportId: "Report ID",
    reviewStatus: "Review Status",
    reviewRequired: "Review Required",
    detectorSignals: "Detector Signals",
    policyExplanation: "Policy Explanation",
    policyVersion: "Policy Version",
    detectorVersion: "Detector Version",
    modelVersion: "Model Version",
    latency: "Latency",
    threshold: "threshold",
    severity: "Severity",
    weight: "Weight",
    noEvidenceCards: "No evidence cards are available.",
    noDetectorSignals: "No detector signals are available.",
  },
  evidenceLayer: {
    source: "Source",
    metadata: "Metadata",
    detector: "Detector",
    forensic: "Forensic",
    policy: "Policy",
  },
  evidenceStatus: {
    support_ai: "Supports AI",
    support_real: "Supports Real",
    neutral: "Neutral",
    warning: "Warning",
    error: "Error",
  },
  detectorRole: {
    primary: "Primary",
    auxiliary: "Auxiliary",
    disabled: "Disabled",
    legacy: "Legacy",
    error: "Error",
  },
  severity: {
    low: "Low",
    medium: "Medium",
    high: "High",
  },
});

mergeTranslations(translations.zh, {
  nav: {
    product: "产品",
    trustConsole: "可信控制台",
    evidence: "证据",
    reports: "报告",
    architecture: "架构",
    errorGallery: "错误图库",
    tryDemo: "开始扫描",
    refresh: "刷新",
    checking: "检查中",
    online: "系统在线",
    apiError: "后端异常",
  },
  demo: {
    eyebrow: "运行中可信控制台",
    title: "Minerva 图像可信控制台",
    description: "上传图像、选择策略、运行检测，并在首屏查看可信判定和证据档案。",
    uploadTab: "单图",
    batchTab: "批量",
    sampleTab: "样例",
    resultsEyebrow: "可信判定",
    resultsTitle: "证据档案",
    simpleView: "摘要",
    jsonView: "JSON",
    emptyJson: "完成检测后可查看结构化 JSON。",
  },
  workspace: {
    liveEyebrow: "证据地图",
    liveTitle: "图像信号接入",
    liveBody: "首屏保留真实上传、批量检测、策略切换、JSON 查看和报告中心入口，适合本地演示与产品评审。",
    capabilityOne: "单图与批量扫描",
    capabilityTwo: "风险、置信度与证据上下文",
    capabilityThree: "人工复核建议",
  },
  single: {
    title: "单图扫描",
    description: "将一张图像送入当前检测链路。",
    choose: "选择图像",
    formats: "JPG、JPEG、PNG 或 WEBP",
    detect: "开始扫描",
    redetect: "重新扫描",
    analyzing: "扫描中",
    analyzingImage: "正在分析图像",
    release: "松开以上传图像",
    remove: "移除图像",
    invalidType: "请上传 JPG、JPEG、PNG 或 WEBP 图像。",
    scanning: "正在分析来源、元数据、模型输出与取证特征。",
  },
  batch: {
    title: "批量扫描",
    description: "使用批量接口分析多张图像。",
    choose: "选择多张图像",
    empty: "尚未选择图像",
    selected: "已选择 {count} 张图像",
    detect: "批量扫描",
    redetect: "重新扫描",
    analyzing: "批量扫描中",
    analyzingImages: "正在分析 {count} 张图像",
    complete: "批量检测完成",
    succeeded: "{succeeded} 成功，{failed} 失败",
  },
  result: {
    emptyTitle: "等待图像扫描",
    emptyBody: "上传后将在这里显示结论、置信度、风险等级和报告入口。",
    topVerdict: "可信判定",
    evidenceChain: "证据链",
    evidenceSummary: "证据摘要",
    recommendation: "复核建议",
    reason: "判断依据",
    saved: "已生成报告",
    copyJson: "复制 JSON",
    exportJson: "导出 JSON",
  },
  policyProfile: {
    label: "策略",
    strictSafe: "标准安全",
    highRecall: "高召回复核",
  },
});

mergeTranslations(translations.en, {
  nav: {
    product: "Product",
    trustConsole: "Trust Console",
    evidence: "Evidence",
    reports: "Reports",
    architecture: "Architecture",
    errorGallery: "Error Gallery",
    tryDemo: "Start Scan",
    refresh: "Refresh",
    checking: "Checking",
    online: "System Online",
    apiError: "Backend Error",
  },
  demo: {
    eyebrow: "Operational Trust Console",
    title: "Minerva Image Trust Console",
    description: "Upload an image, choose a policy profile, run detection, and inspect the trust verdict in the first screen.",
    uploadTab: "Single",
    batchTab: "Batch",
    sampleTab: "Sample",
    resultsEyebrow: "Trust Verdict",
    resultsTitle: "Evidence Dossier",
    simpleView: "Summary",
    jsonView: "JSON",
    emptyJson: "Run a detection to view structured JSON.",
  },
  workspace: {
    liveEyebrow: "Evidence Map",
    liveTitle: "Image Signal Intake",
    liveBody: "The first screen keeps real upload, batch detection, policy switching, JSON inspection, and report-center routing available for local review.",
    capabilityOne: "Single image and batch scan",
    capabilityTwo: "Risk, confidence, evidence context",
    capabilityThree: "Human review recommendation",
  },
  single: {
    title: "Single Image Scan",
    description: "Run one image through the current detection chain.",
    detect: "Start Scan",
    redetect: "Run Again",
    scanning: "Analyzing provenance, metadata, model output, and forensic features.",
  },
  batch: {
    title: "Batch Scan",
    description: "Analyze multiple images with the batch endpoint.",
    detect: "Batch Scan",
    redetect: "Run Again",
  },
  result: {
    emptyTitle: "Waiting for image scan",
    emptyBody: "After upload, verdict, confidence, risk level, and report actions will appear here.",
    topVerdict: "Trust Verdict",
    evidenceChain: "Evidence Chain",
    evidenceSummary: "Evidence Summary",
    recommendation: "Review Recommendation",
    reason: "Decision Rationale",
  },
  policyProfile: {
    label: "Policy",
    strictSafe: "Strict Safe",
    highRecall: "High Recall",
  },
});

mergeTranslations(translations.zh, {
  hero: {
    previewApi: "本地 API 路径",
    previewSample: "示例预览",
    previewAwaiting: "等待扫描",
    previewNoVerdict: "非静态结论",
  },
  validated: {
    zeroLeakage: "泄漏受控测试划分",
  },
  story: {
    apiTitle: "SaaS 与 API 路径",
  },
  workbench: {
    eyebrow: "本地可信工作台",
    title: "Agent-first 证据控制台",
    scopeLocal: "本地 API 路径",
    scopeEvidence: "指标绑定报告证据",
    scopePreflight: "本地预检，非生产 SLA",
    routeEyebrow: "证据路由",
    routeTitle: "从上传到复核决策",
    routeUpload: "上传接入",
    routeProvenance: "来源与元数据",
    routeModel: "模型信号",
    routePolicy: "策略门控",
  },
  scanState: {
    idle: "空闲",
    ready: "文件就绪",
    scanning: "扫描中",
    review: "复核门控",
  },
  pipeline: {
    source: "来源",
    metadata: "元数据",
    model: "模型",
    forensic: "取证",
    policy: "策略",
  },
});

mergeTranslations(translations.en, {
  hero: {
    previewApi: "Local API path",
    previewSample: "Sample preview",
    previewAwaiting: "Awaiting scan",
    previewNoVerdict: "No static verdict",
  },
  validated: {
    zeroLeakage: "Leakage-controlled split",
  },
  story: {
    apiTitle: "SaaS & API path",
  },
  workbench: {
    eyebrow: "Local Trust Workbench",
    title: "Agent-first evidence console",
    scopeLocal: "Local API path",
    scopeEvidence: "Evidence-linked metrics",
    scopePreflight: "Preflight, not production SLA",
    routeEyebrow: "Evidence routing",
    routeTitle: "From upload to review decision",
    routeUpload: "Upload intake",
    routeProvenance: "Provenance",
    routeModel: "Model signals",
    routePolicy: "Policy gate",
  },
  scanState: {
    idle: "Idle",
    ready: "File ready",
    scanning: "Scanning",
    review: "Review gate",
  },
  pipeline: {
    source: "Source",
    metadata: "Metadata",
    model: "Model",
    forensic: "Forensics",
    policy: "Policy",
  },
});

function initTrustParticles() {
  const canvas = elements.trustParticles;
  if (!canvas) {
    return;
  }
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const colors = ["rgba(216,162,74,0.62)", "rgba(190,207,225,0.42)", "rgba(114,162,245,0.38)"];
  let width = 0;
  let height = 0;
  let dpr = 1;
  let particles = [];
  let animationFrame = 0;

  const resize = () => {
    const bounds = canvas.getBoundingClientRect();
    width = Math.max(1, bounds.width);
    height = Math.max(1, bounds.height);
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.min(64, Math.max(34, Math.round(width / 24)));
    particles = Array.from({ length: count }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      radius: 0.8 + Math.random() * 1.8,
      vx: (Math.random() - 0.5) * 0.08,
      vy: (Math.random() - 0.5) * 0.06,
      color: colors[index % colors.length],
      phase: Math.random() * Math.PI * 2,
    }));
  };

  const drawStatic = () => {
    context.clearRect(0, 0, width, height);
    for (const particle of particles) {
      context.beginPath();
      context.fillStyle = particle.color;
      context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
      context.fill();
    }
  };

  const draw = (time = 0) => {
    context.clearRect(0, 0, width, height);
    const pulse = document.body.classList.contains("is-scanning") ? 1.7 : 1;
    for (const particle of particles) {
      particle.x += particle.vx * pulse;
      particle.y += particle.vy * pulse;
      if (particle.x < -8) particle.x = width + 8;
      if (particle.x > width + 8) particle.x = -8;
      if (particle.y < -8) particle.y = height + 8;
      if (particle.y > height + 8) particle.y = -8;
      const glow = 0.45 + Math.sin(time * 0.0008 + particle.phase) * 0.25;
      context.beginPath();
      context.fillStyle = particle.color.replace(/[\d.]+\)$/, `${Math.max(0.2, glow)})`);
      context.arc(particle.x, particle.y, particle.radius * (document.body.classList.contains("is-scanning") ? 1.35 : 1), 0, Math.PI * 2);
      context.fill();
    }
    animationFrame = window.requestAnimationFrame(draw);
  };

  resize();
  if (state.prefersReducedMotion) {
    drawStatic();
  } else {
    animationFrame = window.requestAnimationFrame(draw);
  }
  window.addEventListener("resize", () => {
    window.cancelAnimationFrame(animationFrame);
    resize();
    if (state.prefersReducedMotion) {
      drawStatic();
    } else {
      animationFrame = window.requestAnimationFrame(draw);
    }
  });
}

setUploadButtons();
setDemoTab(state.demoTab);
applyResultView();
applyI18n();
initTrustParticles();
window.addEventListener("DOMContentLoaded", () => loadDashboardData());
