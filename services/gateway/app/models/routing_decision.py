"""Auditable routing decision entity."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoutingDecision(Base):
    __tablename__ = "routing_decision"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column("traceId", String(64), unique=True, nullable=False)
    evaluation_run_id: Mapped[str | None] = mapped_column("evaluationRunId", String(64), nullable=True)
    task_type: Mapped[str] = mapped_column("taskType", String(64), nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_model: Mapped[str | None] = mapped_column("requestedModel", String(128), nullable=True)
    selected_model_id: Mapped[int | None] = mapped_column("selectedModelId", BigInteger, nullable=True)
    selected_model_key: Mapped[str | None] = mapped_column("selectedModelKey", String(128), nullable=True)
    quality_weight: Mapped[Decimal] = mapped_column("qualityWeight", Numeric(6, 4), nullable=False)
    latency_weight: Mapped[Decimal] = mapped_column("latencyWeight", Numeric(6, 4), nullable=False)
    cost_weight: Mapped[Decimal] = mapped_column("costWeight", Numeric(6, 4), nullable=False)
    reliability_weight: Mapped[Decimal] = mapped_column("reliabilityWeight", Numeric(6, 4), nullable=False)
    final_score: Mapped[Decimal | None] = mapped_column("finalScore", Numeric(10, 6), nullable=True)
    candidate_snapshot: Mapped[list | None] = mapped_column("candidateSnapshot", JSON, nullable=True)
    fallback_order: Mapped[list | None] = mapped_column("fallbackOrder", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False, server_default=func.current_timestamp())
