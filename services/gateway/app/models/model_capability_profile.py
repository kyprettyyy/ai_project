"""Evaluation-derived capability profile for one model and task type."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelCapabilityProfile(Base):
    __tablename__ = "model_capability_profile"
    __table_args__ = (
        UniqueConstraint("modelId", "taskType", name="uk_model_task"),
        Index("idx_task_quality", "taskType", "qualityScore"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column("modelId", BigInteger, nullable=False)
    model_key: Mapped[str] = mapped_column("modelKey", String(128), nullable=False)
    task_type: Mapped[str] = mapped_column("taskType", String(64), nullable=False, default="general")
    quality_score: Mapped[Decimal] = mapped_column("qualityScore", Numeric(8, 4), nullable=False, server_default=text("0.5"))
    latency_score: Mapped[Decimal] = mapped_column("latencyScore", Numeric(8, 4), nullable=False, server_default=text("0.5"))
    cost_score: Mapped[Decimal] = mapped_column("costScore", Numeric(8, 4), nullable=False, server_default=text("0.5"))
    reliability_score: Mapped[Decimal] = mapped_column("reliabilityScore", Numeric(8, 4), nullable=False, server_default=text("0.5"))
    sample_count: Mapped[int] = mapped_column("sampleCount", Integer, nullable=False, server_default=text("0"))
    evaluation_run_id: Mapped[str | None] = mapped_column("evaluationRunId", String(64), nullable=True)
    profile_version: Mapped[int] = mapped_column("profileVersion", Integer, nullable=False, server_default=text("1"))
    evaluated_at: Mapped[datetime | None] = mapped_column("evaluatedAt", DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column("createTime", DateTime, nullable=False, server_default=func.current_timestamp())
    update_time: Mapped[datetime] = mapped_column("updateTime", DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=datetime.utcnow)
