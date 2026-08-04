"""OpenAI-compatible discovery endpoints."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.model import Model
from app.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/v1", tags=["openai-compatible"])


@router.get("/models")
async def list_models(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if await ApiKeyService(db).get_by_key_value(authorization[7:]) is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    models = list((await db.scalars(select(Model).where(Model.is_delete == 0, Model.status == "active"))).all())
    return {"object": "list", "data": [{
        "id": item.model_key, "object": "model", "name": item.model_name,
        "description": item.description, "context_length": item.context_length,
        # Gateway prices are stored per 1K tokens; OpenAI-compatible discovery exposes per-token prices.
        "pricing": {"prompt": str(float(item.input_price) / 1_000),
                    "completion": str(float(item.output_price) / 1_000)},
        "architecture": {"modality": "text"},
    } for item in models]}
