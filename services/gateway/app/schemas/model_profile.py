"""Schemas used by the evaluation-to-gateway feedback API."""

from datetime import datetime

from pydantic import BaseModel, Field


class ModelProfileUpsert(BaseModel):
    model: str
    task_type: str = "general"
    quality_score: float = Field(ge=0, le=1)
    latency_score: float = Field(ge=0, le=1)
    cost_score: float = Field(ge=0, le=1)
    reliability_score: float = Field(ge=0, le=1)
    sample_count: int = Field(default=0, ge=0)
    evaluation_run_id: str | None = None
    evaluated_at: datetime | None = None


class ModelProfileBatch(BaseModel):
    profiles: list[ModelProfileUpsert]
