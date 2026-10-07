"""Console and server-to-server online answer feedback."""
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.middleware.auth import require_login
from app.models.user import User
from app.core.config import get_settings
from app.services.api_key_service import ApiKeyService
from app.services.answer_feedback_service import AnswerFeedbackService
from app.common.result_utils import success

router = APIRouter(tags=['answer-feedback'])

class FeedbackRequest(BaseModel):
    requestId: str = Field(min_length=1, max_length=64)
    vote: Literal[-1, 1]
    reason: Literal['incorrect', 'incomplete', 'irrelevant', 'other'] | None = None
    comment: str | None = Field(default=None, max_length=2000)

@router.post('/internal/chat/feedback')
async def console_feedback(payload: FeedbackRequest, user: User = Depends(require_login), db: AsyncSession = Depends(get_db_session)):
    return success(await AnswerFeedbackService(db).submit(payload.requestId, payload.vote, payload.reason,
                                                         payload.comment, user.id))

@router.post('/v1/feedback')
async def api_feedback(payload: FeedbackRequest, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'missing bearer token')
    key = await ApiKeyService(db).get_by_key_value(authorization[7:])
    if not key:
        raise HTTPException(401, 'invalid API key')
    return await AnswerFeedbackService(db).submit(payload.requestId, payload.vote, payload.reason,
                                                 payload.comment, key.user_id, key.id)

@router.get('/internal/answer-feedback')
async def feedback_report(x_internal_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db_session)):
    token = get_settings().internal_service_token
    if not token or x_internal_token != token:
        raise HTTPException(401, 'invalid internal service token')
    service = AnswerFeedbackService(db)
    result = await service.summary()
    result['recent'] = await service.recent()
    return result
