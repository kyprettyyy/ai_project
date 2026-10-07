"""Immutable published model profile versions for dashboard trends."""
from sqlalchemy import BigInteger,String,Integer,DateTime,JSON,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base
class ModelProfileHistory(Base):
    __tablename__='model_profile_history'
    __table_args__=(UniqueConstraint('modelKey','taskType','profileVersion',name='uk_profile_history_version'),)
    id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    model_key:Mapped[str]=mapped_column('modelKey',String(128))
    task_type:Mapped[str]=mapped_column('taskType',String(64))
    profile_version:Mapped[int]=mapped_column('profileVersion',Integer)
    snapshot:Mapped[dict]=mapped_column(JSON)
    recorded_at:Mapped[object]=mapped_column('recordedAt',DateTime,server_default=func.current_timestamp())
