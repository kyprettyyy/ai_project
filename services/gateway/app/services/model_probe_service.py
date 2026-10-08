"""Direct administrator connectivity probes, separate from production statistics."""
import asyncio
import time
from sqlalchemy import select
from app.models.model import Model
from app.models.model_provider import ModelProvider
from app.services.model_invoke_service import ModelInvokeService
from app.schemas.chat import ChatRequest, ChatMessage
from app.exceptions.business_exception import BusinessException
from app.core.constants import ErrorCode

async def probe_model(db, model_id):
    model = await db.scalar(select(Model).where(Model.id == model_id, Model.is_delete == 0))
    if model is None:
        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, '模型不存在')
    if model.model_type != 'chat':
        raise BusinessException(ErrorCode.PARAMS_ERROR, '目前仅支持对话模型的连接测试')
    provider = await db.scalar(select(ModelProvider).where(ModelProvider.id == model.provider_id, ModelProvider.is_delete == 0))
    if provider is None:
        raise BusinessException(ErrorCode.NOT_FOUND_ERROR, '供应商不存在')
    start = time.perf_counter()
    ok = False
    error = None
    try:
        if not provider.api_key or not provider.api_key.strip():
            raise ValueError('供应商 API Key 未配置')
        response = await asyncio.wait_for(ModelInvokeService().invoke(model, provider, ChatRequest(
            model=model.model_key, messages=[ChatMessage(role='user', content='请只回复 OK。')],
            max_tokens=64)), timeout=60)
        if response.model != model.model_key:
            raise ValueError('返回模型与测试模型不一致')
        if not response.choices or not (response.choices[0].message.content or '').strip():
            raise ValueError('接口返回空回答')
        ok = True
    except asyncio.TimeoutError:
        error = '连接测试超时（60 秒）'
    except Exception as exc:
        error = str(exc)
        if provider.api_key:
            error = error.replace(provider.api_key, '[已隐藏密钥]')
        error = error[:1500]
    elapsed = int((time.perf_counter() - start) * 1000)
    model.health_status = 'healthy' if ok else 'unhealthy'
    await db.commit()
    return {'modelId': model.id, 'modelKey': model.model_key, 'healthy': ok,
            'latencyMs': elapsed, 'error': error}
