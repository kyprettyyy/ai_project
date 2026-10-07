"""Admin-only gateway feedback proxy; never expose the internal token to browsers."""
import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.services.user_service import UserService
router = APIRouter(prefix='/online-feedback', tags=['线上用户反馈'])

@router.get('')
async def report(request: Request, db: AsyncSession = Depends(get_db)):
    await UserService.check_admin(db, request)
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(settings.GATEWAY_BASE_URL.rstrip('/') + '/internal/answer-feedback',
                headers={'X-Internal-Token': settings.GATEWAY_INTERNAL_TOKEN})
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise BusinessException(ErrorCode.OPERATION_ERROR, '线上反馈暂时无法加载，请稍后重试') from exc
    return {'code': 0, 'data': data, 'message': 'ok'}
