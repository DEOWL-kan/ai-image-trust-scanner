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
    filename: str
    final_label: Literal["ai", "real", "uncertain"]
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    decision_reason: Any
    recommendation: Any
    user_facing_summary: str
    technical_explanation: Any
    debug_evidence: dict[str, Any]


class DetectionResponse(BaseModel):
    success: bool
    data: DetectionData | None
    error: ErrorResponse | None
