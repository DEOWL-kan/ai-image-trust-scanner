const API_ENDPOINTS = {
  summary: "/dashboard/summary",
  recentResults: "/api/v1/reports?limit=100",
  reportQueue: "/api/v1/reports/queue?limit=20",
  reportReview: (id) => `/api/v1/reports/${encodeURIComponent(id)}/review`,
  reportExport: "/api/v1/reports/export",
  chartData: "/dashboard/chart-data",
  detectSingle: "/api/v1/detect",
  detectBatchCandidates: ["/detect/batch", "/api/v1/detect/batch"],
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
      apiTitle: "SaaS & API ready",
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
      apiBody: "/api/v1/detect、/detect/batch 和结构化 JSON 可信输出。",
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
      apiTitle: "SaaS & API ready",
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
      apiBody: "/api/v1/detect, /detect/batch, and structured JSON trust output.",
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
    previewApi: "API 就绪",
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
    apiTitle: "SaaS & API ready",
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
    apiBody: "/api/v1/detect、/detect/batch 和结构化 JSON 可信输出。",
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

mergeTranslations(translations.en, {
  hero: {
    title: "Make the world for real",
    titleZh: "Evidence-first AI content trust infrastructure",
    lead: "Minerva turns image detection, metadata, provenance signals, and forensic traces into reviewable trust evidence.",
    previewTitle: "Live trust preview",
    previewQueue: "Review queue",
    previewApi: "API ready",
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

const state = {
  dashboardLoading: false,
  singleLoading: false,
  batchLoading: false,
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
  reportSearchTimer: 0,
  demoTab: "upload",
  resultView: "simple",
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
  batchButton: document.querySelector("#batch-detect-button"),
  uploadResult: document.querySelector("#upload-result"),
  demoTabs: document.querySelector("#demo-tabs"),
  resultViewToggle: document.querySelector("#result-view-toggle"),
  trustParticles: document.querySelector("#trust-particles"),
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
  return `/api/v1/reports?${params.toString()}`;
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
  elements.singleButton.textContent = state.singleLoading ? t("single.analyzing") : t("single.detect");
  elements.batchButton.textContent = state.batchLoading ? t("batch.analyzing") : t("batch.detect");
  elements.singleUploadCard?.classList.toggle("is-analyzing", state.singleLoading);
  elements.batchUploadCard?.classList.toggle("is-analyzing", state.batchLoading);
  elements.singleUploadCard?.classList.toggle("has-file", Boolean(state.selectedSingleFile));
  elements.batchUploadCard?.classList.toggle("has-file", state.selectedBatchFiles.length > 0);
}

function setDemoTab(tab) {
  state.demoTab = ["upload", "batch", "sample"].includes(tab) ? tab : "upload";
  elements.demoTabs?.querySelectorAll("[data-demo-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.demoTab === state.demoTab);
  });
  document.querySelectorAll("[data-demo-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.demoPanel === state.demoTab);
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
    <button class="selected-file-remove preview-remove" type="button" data-action="remove-single-file" aria-label="${escapeHtml(t("single.remove"))}">x</button>
  `;
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

function renderReviewQueueError() {
  if (elements.reviewQueueCount) elements.reviewQueueCount.textContent = "--";
  if (elements.reviewQueueList) {
    elements.reviewQueueList.innerHTML = `<div class="error-state compact">${escapeHtml(t("reportCenter.queueFailed"))}</div>`;
  }
}

function applyResultView() {
  elements.resultViewToggle?.querySelectorAll("[data-result-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.resultView === state.resultView);
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
  const hasMetadata = Boolean(
    getValue(debug, "format_evidence.exif_info.has_exif") ||
      getValue(debug, "format_evidence.format_info.format") ||
      getValue(debug, "feature_summary.raw_debug_evidence.format_info.format"),
  );
  const hasModel = Boolean(getValue(debug, "feature_summary.raw_debug_evidence.raw_result.model_result"));
  const hasForensics = Boolean(getValue(debug, "feature_summary.raw_debug_evidence.raw_result.forensic_result"));
  const hasConsistency = Boolean(getValue(debug, "consistency_checks") || getValue(debug, "feature_summary.raw_debug_evidence.multi_resolution"));
  const tags = [
    [t("result.sourceProvenance"), hasMetadata],
    [t("result.metadataLayer"), hasMetadata],
    [t("result.aiModelLayer"), hasModel],
    [t("result.forensicLayer"), hasForensics || hasConsistency],
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
    ["Source", states.source, t("result.sourceProvenance")],
    ["Metadata", states.metadata, t("result.metadataLayer")],
    ["Model", states.model, t("result.aiModelLayer")],
    ["Forensics", states.forensics, t("result.forensicLayer")],
    ["Output", true, `${t("result.riskLevel")} + ${t("result.confidence")}`],
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
  elements.uploadResult.innerHTML = `
    <div class="result-empty">
      <div data-result-panel="simple" ${state.resultView === "simple" ? "" : "hidden"}>
        <img class="empty-mark result-mark" src="./assets/minerva-mark.png" onerror="this.onerror=null;this.src='./assets/minerva-mark.svg'" alt="" />
        <h3>${escapeHtml(t("result.emptyTitle"))}</h3>
        <p>${escapeHtml(t("result.emptyBody"))}</p>
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

function renderErrorResult(message) {
  elements.uploadResult.innerHTML = `
    <article class="error-state result-error">
      <h3>${escapeHtml(t("result.failed"))}</h3>
      <p>${escapeHtml(message)}</p>
    </article>
  `;
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
    evidenceLine(t("result.sourceProvenance"), hasExif ? "EXIF / provenance hint present" : t("result.notAvailable"), hasExif ? "positive" : "muted", hasExif ? t("result.available") : t("result.notAvailableStatus")),
    evidenceLine(t("result.metadataLayer"), format || hasExif !== undefined ? `${format || "image"} · EXIF ${hasExif ? "present" : "limited"}` : t("result.notAvailable"), hasExif ? "positive" : "warning", format || hasExif !== undefined ? t("result.partial") : t("result.notAvailableStatus")),
    evidenceLine(t("result.aiModelLayer"), modelStatus || t("result.notAvailable"), modelStatus ? "neutral" : "muted", modelStatus ? t("result.partial") : t("result.notAvailableStatus")),
    evidenceLine(t("result.forensicLayer"), forensic !== undefined ? `noise / edge score: ${forensic}` : t("result.notAvailable"), forensic !== undefined ? "neutral" : "muted", forensic !== undefined ? t("result.available") : t("result.notAvailableStatus")),
  ].join("");
}

function renderSingleResult(payload) {
  state.currentResult = { kind: "single", payload };
  state.resultView = "simple";
  const data = getValue(payload, "data", payload) || {};
  const label = firstDefined(data.final_label, "uncertain");
  const risk = firstDefined(data.risk_level, "unknown");
  const filename = firstDefined(data.filename, state.selectedSingleFile?.name, "uploaded image");
  const summary = resultSummaryText(data);
  const reason = textFromValue(data.decision_reason);
  const recommendation = textFromValue(data.recommendation);
  const confidencePercent = Math.round(Math.max(0, Math.min(1, toNumber(data.confidence))) * 100);

  elements.uploadResult.innerHTML = `
    <article class="trust-result demo-result ${slug(risk)}">
      <div data-result-panel="simple">
        <div class="result-topline">
          <div>
            <p class="eyebrow">${escapeHtml(t("result.topVerdict"))}</p>
            <h3 class="result-verdict">${escapeHtml(displayLabel(label))}</h3>
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
          <div><span>${escapeHtml(t("result.verdict"))}</span><strong>${escapeHtml(displayLabel(label))}</strong></div>
          <div><span>${escapeHtml(t("result.riskLevel"))}</span><strong>${escapeHtml(displayLabel(risk))}</strong></div>
          <div><span>${escapeHtml(t("result.confidence"))}</span><strong>${escapeHtml(formatConfidence(data.confidence))}</strong></div>
          <div><span>${escapeHtml(t("result.status"))}</span><strong>${escapeHtml(t("result.saved"))}</strong></div>
        </div>
        <div class="result-section evidence-tags-section">
          <h4>${escapeHtml(t("result.evidenceSummary"))}</h4>
          ${evidenceMiniMap(data)}
          <div class="evidence-tags">${evidenceTags(data)}</div>
        </div>
        <div class="result-section recommendation-block">
          <h4>${escapeHtml(t("result.recommendation"))}</h4>
          <p>${escapeHtml(recommendation || summary)}</p>
        </div>
        <div class="result-section">
          <h4>${escapeHtml(t("result.reason"))}</h4>
          <p>${escapeHtml(reason)}</p>
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
  applyResultRevealClasses(confidencePercent);
}

function renderBatchResult(payload) {
  state.currentResult = { kind: "batch", payload };
  state.resultView = "simple";
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
          <div><span>Total</span><strong>${escapeHtml(formatInteger(firstDefined(payload.total, results.length)))}</strong></div>
          <div><span>AI</span><strong>${escapeHtml(formatInteger(counts.ai))}</strong></div>
          <div><span>Uncertain</span><strong>${escapeHtml(formatInteger(counts.uncertain))}</strong></div>
          <div><span>High risk</span><strong>${escapeHtml(formatInteger(counts.highRisk))}</strong></div>
          <div><span>Average confidence</span><strong>${escapeHtml(formatConfidence(averageConfidence))}</strong></div>
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

  const [summaryResult, recentResult, chartResult, queueResult] = await Promise.allSettled([
    fetchJson(API_ENDPOINTS.summary),
    fetchJson(reportSearchUrl()),
    fetchJson(API_ENDPOINTS.chartData),
    fetchJson(API_ENDPOINTS.reportQueue),
  ]);

  if (summaryResult.status === "fulfilled") {
    setServiceStatus("online", t("nav.online"));
    renderSummary(summaryResult.value);
  } else {
    setServiceStatus("offline", t("nav.apiError"));
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
  try {
    const [reports, queue] = await Promise.all([fetchJson(reportSearchUrl()), fetchJson(API_ENDPOINTS.reportQueue)]);
    renderRecentResults(reports);
    renderReviewQueue(queue);
    if (!silent) setServiceStatus("online", t("nav.online"));
  } catch (error) {
    renderRecentResultsError();
    renderReviewQueueError();
    if (!silent) setServiceStatus("offline", t("nav.apiError"));
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
  syncReportFiltersFromControls();
  const response = await fetch(reportExportUrl(format), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }
  const suffix = timestampForFilename();
  if (format === "csv") {
    downloadBlob(await response.text(), `report_center_export_${suffix}.csv`, "text/csv;charset=utf-8");
    return;
  }
  const payload = await response.json();
  downloadJson(payload, `report_center_export_${suffix}.json`);
}

async function detectSingleImage() {
  if (!state.selectedSingleFile || state.singleLoading) {
    return;
  }
  state.singleLoading = true;
  state.currentResult = null;
  document.body.classList.add("is-scanning");
  setUploadButtons();
  renderLoadingResult(t("single.analyzingImage"));

  const formData = new FormData();
  formData.append("file", state.selectedSingleFile);

  try {
    const payload = await fetchJson(API_ENDPOINTS.detectSingle, {
      method: "POST",
      body: formData,
    });
    renderSingleResult(payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    renderErrorResult(`Single detection failed: ${error.message || "Unknown error"}`);
  } finally {
    state.singleLoading = false;
    document.body.classList.remove("is-scanning");
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
  state.currentResult = null;
  document.body.classList.add("is-scanning");
  setUploadButtons();
  renderLoadingResult(t("batch.analyzingImages", { count: state.selectedBatchFiles.length }));

  const formData = new FormData();
  state.selectedBatchFiles.forEach((file) => {
    formData.append("files", file);
  });

  try {
    const payload = await postBatchDetection(formData);
    renderBatchResult(payload);
    await loadDashboardData({ silent: true });
  } catch (error) {
    renderErrorResult(`Batch detection failed: ${error.message || "Unknown error"}`);
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
    renderSinglePreview(null);
    updateFileLabels();
    setUploadButtons();
    flashUploadError(elements.singleUploadCard, t("single.invalidType"));
    return;
  }
  state.selectedSingleFile = file || null;
  if (file) setDemoTab("upload");
  updateFileLabels();
  renderSinglePreview(state.selectedSingleFile);
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

elements.singleInput.addEventListener("change", (event) => {
  selectSingleFile(event.target.files?.[0] || null);
});

elements.batchInput.addEventListener("change", (event) => {
  selectBatchFiles(event.target.files || []);
});

elements.singleButton.addEventListener("click", detectSingleImage);
elements.batchButton.addEventListener("click", detectBatchImages);
elements.refreshButton.addEventListener("click", () => loadDashboardData());

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

elements.resultViewToggle?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-result-view]");
  if (!button) return;
  setResultView(button.dataset.resultView);
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
  } catch {
    target.textContent = t("result.copyFailed");
  }
});

document.querySelectorAll(".logo-mark img").forEach((img) => {
  img.addEventListener("error", () => {
    img.style.display = "none";
  });
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

