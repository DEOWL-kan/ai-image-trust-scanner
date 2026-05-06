from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["ai-image-trust-scanner"]
    version: str


class ErrorResponse(BaseModel):
    code: Literal["INVALID_FILE_TYPE", "DETECTION_FAILED", "EMPTY_FILE", "INTERNAL_ERROR"]
    message: str


class DetectionData(BaseModel):
    report_id: str | None = None
    id: str | None = None
    filename: str
    final_label: Literal["ai", "real", "uncertain"]
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    decision_reason: Any
    recommendation: Any
    user_facing_summary: str
    technical_explanation: Any
    debug_evidence: dict[str, Any]
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
