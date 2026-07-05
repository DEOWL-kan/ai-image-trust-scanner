from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["ai-image-trust-scanner"]
    version: str
    api: Literal["ready"]


class ErrorResponse(BaseModel):
    code: Literal["INVALID_FILE_TYPE", "DETECTION_FAILED", "EMPTY_FILE", "INTERNAL_ERROR"]
    message: str


class ProvenanceVerified(BaseModel):
    c2pa_present: bool
    c2pa_readable: bool
    c2pa_valid: bool | None = None
    c2pa_issuer: str | None = None
    c2pa_generator: str | None = None
    openai_provenance_detected: bool
    confidence: Literal["high", "unknown", "unavailable"]


class ProvenanceMarkers(BaseModel):
    binary_c2pa_marker_found: bool
    binary_openai_marker_found: bool
    binary_gpt_image_marker_found: bool
    marker_confidence: Literal["weak", "none"]
    used_for_final_decision: Literal[False] = False
    marker_offsets_preview: list[str] | None = None


class ProvenanceDiagnostics(BaseModel):
    c2pa_probe_status: Literal["parsed", "no_manifest", "stdout_empty", "stdout_not_json", "tool_error", "timeout", "claim_cbor_decode_error"] | None = None
    c2patool_version: str | None = None
    c2patool_path: str | None = None
    c2patool_source: Literal["env", "path", "missing"] | None = None
    c2patool_upgrade_recommended: bool | None = None
    c2patool_returncode: int | None = None
    raw_manifest_path: str | None = None
    error: str | None = None
    error_detail: str | None = None
    stdout_preview: str | None = None
    stderr_preview: str | None = None


class ProvenanceData(BaseModel):
    verified: ProvenanceVerified
    unverified_markers: ProvenanceMarkers
    diagnostics: ProvenanceDiagnostics
    user_note: str


class DetectionData(BaseModel):
    report_id: str | None = None
    id: str | None = None
    filename: str
    final_label: Literal["ai", "ai_generated", "real", "uncertain"]
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    decision_reason: Any
    recommendation: Any
    user_facing_summary: str
    technical_explanation: Any
    debug_evidence: dict[str, Any]
    open_source_score: float | None = Field(default=None, ge=0.0, le=1.0)
    open_source_evidence: dict[str, Any] | None = None
    detector_result_schema_version: str | None = None
    detector_results: list[dict[str, Any]] | None = None
    detector_summary: dict[str, Any] | None = None
    detector_registry_version: str | None = None
    threshold_profile: str | None = None
    model_adapter_version: str | None = None
    policy_result: dict[str, Any] | None = None
    policy_version: str | None = None
    policy_snapshot: dict[str, Any] | None = None
    provenance: ProvenanceData | None = None
    review_status: str | None = None
    report_schema_version: str | None = None
    detector_version: str | None = None
    model_version: str | None = None
    html_report_available: bool | None = None


class DetectionResponse(BaseModel):
    success: bool
    data: DetectionData | None
    error: ErrorResponse | None
    history: dict[str, Any] | None = None


class BatchPathRequest(BaseModel):
    image_paths: list[str]
    save_history: bool = True


class DashboardDecisionQuality(BaseModel):
    uncertain_rate: float = Field(ge=0.0, le=1.0)
    high_risk_rate: float = Field(ge=0.0, le=1.0)
    average_confidence: float = Field(ge=0.0, le=1.0)


class DashboardSummaryStats(BaseModel):
    total_detections: int
    single_detection_count: int
    batch_detection_count: int
    total_images_processed: int
    final_label_distribution: dict[str, int]
    risk_level_distribution: dict[str, int]
    confidence_distribution: dict[str, int]
    decision_quality: DashboardDecisionQuality


class DashboardRecentResult(BaseModel):
    id: str
    timestamp: str
    filename: str
    final_label: Literal["ai_generated", "real", "uncertain"]
    risk_level: Literal["low", "medium", "high", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    user_facing_summary: str
    recommendation: str
    history_type: str
    history_file: str
    batch_id: str | None = None


class DashboardRecentBatch(BaseModel):
    id: str
    timestamp: str
    total: int
    succeeded: int
    failed: int
    history_file: str


class ChartPoint(BaseModel):
    label: str
    value: int


class DailyTrendPoint(BaseModel):
    date: str
    count: int


class DashboardChartData(BaseModel):
    label_pie: list[ChartPoint]
    risk_bar: list[ChartPoint]
    confidence_bar: list[ChartPoint]
    daily_trend: list[DailyTrendPoint]


class DashboardSummaryResponse(BaseModel):
    status: Literal["ok"]
    generated_at: str
    summary: DashboardSummaryStats
    recent_results: list[DashboardRecentResult]
    recent_batches: list[DashboardRecentBatch]
    chart_data: DashboardChartData
    alerts: list[dict[str, Any]]
    debug: dict[str, Any] | None = None


class DashboardRecentResultsResponse(BaseModel):
    status: Literal["ok"]
    count: int
    results: list[DashboardRecentResult]


class DashboardCharts(BaseModel):
    label_distribution: list[ChartPoint]
    risk_distribution: list[ChartPoint]
    confidence_distribution: list[ChartPoint]
    daily_detection_trend: list[DailyTrendPoint]


class DashboardChartDataResponse(BaseModel):
    status: Literal["ok"]
    generated_at: str
    charts: DashboardCharts
