"""Online answers, one current vote per answer, and batched satisfaction profiles."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import DATETIME

PRECISE_TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")
from app.db.base import Base

class OnlineAnswer(Base):
    __tablename__ = 'online_answer'
    request_log_id: Mapped[int] = mapped_column('requestLogId', BigInteger, primary_key=True)
    trace_id: Mapped[str] = mapped_column('traceId', String(64), unique=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)

class AnswerFeedback(Base):
    __tablename__ = 'answer_feedback'
    request_log_id: Mapped[int] = mapped_column('requestLogId', BigInteger, primary_key=True)
    vote: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column('updatedAt', PRECISE_TIME, default=datetime.utcnow)

class SatisfactionProfile(Base):
    __tablename__ = 'satisfaction_profile'
    __table_args__ = (UniqueConstraint('modelId', 'taskType', name='uk_satisfaction_model_task'),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column('modelId', BigInteger)
    task_type: Mapped[str] = mapped_column('taskType', String(64))
    sample_count: Mapped[int] = mapped_column('sampleCount', Integer, default=0)
    positive_count: Mapped[int] = mapped_column('positiveCount', Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column('publishedAt', PRECISE_TIME, nullable=True)

class PersonalSatisfactionProfile(Base):
    __tablename__ = 'personal_satisfaction_profile'
    user_id: Mapped[int] = mapped_column('userId', BigInteger, primary_key=True)
    model_id: Mapped[int] = mapped_column('modelId', BigInteger, primary_key=True)
    task_type: Mapped[str] = mapped_column('taskType', String(64), primary_key=True)
    sample_count: Mapped[int] = mapped_column('sampleCount', Integer, default=0)
    positive_count: Mapped[int] = mapped_column('positiveCount', Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column('publishedAt', PRECISE_TIME, nullable=True)

class UserRoutingPreference(Base):
    __tablename__ = 'user_routing_preference'
    user_id: Mapped[int] = mapped_column('userId', BigInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), default='balanced')
