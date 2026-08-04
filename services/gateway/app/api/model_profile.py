"""Internal feedback API for evaluation-derived model profiles."""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.model import Model
from app.models.model_capability_profile import ModelCapabilityProfile
from app.schemas.model_profile import ModelProfileBatch

router = APIRouter(prefix="/internal/model-profiles", tags=["evaluation-feedback"])


@router.put("")
async def upsert_profiles(payload: ModelProfileBatch, x_internal_token: str | None = Header(default=None),
                          db: AsyncSession = Depends(get_db_session)):
    if x_internal_token != get_settings().internal_service_token:
        raise HTTPException(status_code=401, detail="invalid internal service token")
    updated = 0
    for item in payload.profiles:
        model = await db.scalar(select(Model).where(Model.model_key == item.model, Model.is_delete == 0))
        if model is None:
            continue
        profile = await db.scalar(select(ModelCapabilityProfile).where(
            ModelCapabilityProfile.model_id == model.id,
            ModelCapabilityProfile.task_type == item.task_type,
        ))
        if profile is None:
            profile = ModelCapabilityProfile(model_id=model.id, model_key=model.model_key, task_type=item.task_type)
            db.add(profile)
        profile.quality_score = item.quality_score
        profile.latency_score = item.latency_score
        profile.cost_score = item.cost_score
        profile.reliability_score = item.reliability_score
        profile.sample_count = item.sample_count
        profile.evaluation_run_id = item.evaluation_run_id
        profile.evaluated_at = item.evaluated_at or datetime.utcnow()
        profile.profile_version = (profile.profile_version or 0) + 1
        updated += 1
    await db.commit()
    return {"updated": updated, "received": len(payload.profiles)}


@router.get("")
async def list_profiles(x_internal_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)):
    if x_internal_token != get_settings().internal_service_token:
        raise HTTPException(status_code=401, detail="invalid internal service token")
    profiles = list((await db.scalars(select(ModelCapabilityProfile))).all())
    return [{
        "model": item.model_key, "taskType": item.task_type,
        "qualityScore": float(item.quality_score), "latencyScore": float(item.latency_score),
        "costScore": float(item.cost_score), "reliabilityScore": float(item.reliability_score),
        "sampleCount": item.sample_count, "evaluationRunId": item.evaluation_run_id,
        "profileVersion": item.profile_version,
    } for item in profiles]
