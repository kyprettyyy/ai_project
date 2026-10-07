"""Batch completion hook and periodic recovery for pending profile publications."""

import asyncio

from app.core.config import get_settings
from app.core.logging_config import logger
from app.db.session import AsyncSessionLocal
from app.services.model_profile_service import ModelProfileService


_job_lock = asyncio.Lock()


async def update_model_profiles_job() -> None:
    if not get_settings().PROFILE_AUTO_UPDATE_ENABLED or _job_lock.locked():
        return
    async with _job_lock:
        try:
            async with AsyncSessionLocal() as db:
                result = await ModelProfileService(db).rebuild_and_publish(automatic=True)
                if result["published"]:
                    logger.info("批次画像自动发布完成: {}", result)
        except Exception:
            # Results and unpublished snapshots remain in MySQL. The next tick retries
            # even after a process restart, without failing the completed evaluation.
            logger.exception("批次画像自动发布失败，将在下次后台检查重试")
