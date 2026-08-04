"""Capability-profile feedback endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.model_profile_service import ModelProfileService

router = APIRouter(prefix="/model-profiles", tags=["model-profiles"])


class RebuildRequest(BaseModel):
    evaluation_run_id: str | None = None


@router.post("/rebuild")
async def rebuild(payload: RebuildRequest, db: AsyncSession = Depends(get_db)):
    return await ModelProfileService(db).rebuild_and_publish(payload.evaluation_run_id)


@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    return await ModelProfileService(db).list_snapshots()
