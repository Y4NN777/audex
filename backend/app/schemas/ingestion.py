from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    stored_path: str
    metadata: dict[str, Any] | None = None


class ProcessingEventSchema(BaseModel):
    code: str
    label: str
    kind: str
    timestamp: datetime
    progress: int | None = None
    details: dict[str, Any] | None = None


class OCRTextSchema(BaseModel):
    filename: str
    engine: str
    content: str
    confidence: float | None = None
    warnings: list[str] | None = None
    error: str | None = None


class VisionObservationSchema(BaseModel):
    filename: str
    label: str
    severity: str
    confidence: float | None = None
    bbox: list[int] | None = None
    source: str | None = None
    class_name: str | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime | None = None


class RiskBreakdownSchema(BaseModel):
    label: str
    severity: str
    count: int
    score: float


class RiskScoreSchema(BaseModel):
    total_score: float
    normalized_score: float
    breakdown: list[RiskBreakdownSchema]
    created_at: datetime


class BatchResponse(BaseModel):
    batch_id: str = Field(..., description="Unique identifier of the stored batch.")
    files: list[FileMetadata]
    stored_at: datetime
    status: str = Field(..., description="Current status of the batch processing.")
    report_hash: str | None = None
    report_url: str | None = None
    last_error: str | None = None
    timeline: list[ProcessingEventSchema] | None = None
    ocr_texts: list[OCRTextSchema] | None = None
    observations: list[VisionObservationSchema] | None = None
    gemini_status: str | None = None
    gemini_summary: str | None = None
    gemini_prompt_hash: str | None = None
    gemini_model: str | None = None
    risk_score: RiskScoreSchema | None = None
    summary: BatchSummarySchema | None = None


class GeminiAnalysisRecord(BaseModel):
    id: int
    status: str
    summary: str | None = None
    warnings: list[str] | None = None
    prompt_hash: str | None = None
    prompt_version: str | None = None
    provider: str | None = None
    model: str | None = None
    duration_ms: int | None = None
    requested_by: str | None = None
    created_at: datetime
    observations: list[dict[str, Any]] | None = None
    raw_response: Any | None = None


class GeminiAnalysisResponse(BaseModel):
    latest: GeminiAnalysisRecord | None = None
    history: list[GeminiAnalysisRecord] | None = None


class GeminiAnalysisRequest(BaseModel):
    requested_by: str | None = Field(default=None, description="Identifiant de l'utilisateur déclenchant l'analyse.")


class BatchSummarySchema(BaseModel):
    status: str
    source: str | None = None
    text: str | None = None
    findings: list[str] | None = None
    recommendations: list[str] | None = None
    warnings: list[str] | None = None
    prompt_hash: str | None = None
    response_hash: str | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None


BatchResponse.model_rebuild()
