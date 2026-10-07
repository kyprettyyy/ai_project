"""
模型同步定时任务
"""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.model_service import ModelService
from app.core.logging_config import logger
from app.core.config import get_settings
from app.jobs.model_profile_job import update_model_profiles_job


async def sync_models_job():
    """
    同步模型信息定时任务
    每 30 秒执行一次
    """
    try:
        logger.info("开始执行模型同步任务")
        
        async with AsyncSessionLocal() as db:
            model_service = ModelService(db)
            count = await model_service.sync_models_from_gateway()
            
            logger.info(f"模型同步任务完成，同步了 {count} 个模型")
    
    except Exception as e:
        logger.error(f"模型同步任务失败: {str(e)}", exc_info=True)


def start_scheduler():
    """
    启动定时任务调度器
    """
    scheduler = AsyncIOScheduler()
    settings = get_settings()
    if settings.PROFILE_AUTO_UPDATE_ENABLED:
        scheduler.add_job(
            update_model_profiles_job,
            trigger="interval",
            seconds=settings.PROFILE_AUTO_UPDATE_INTERVAL_SECONDS,
            id="update_model_profiles_job",
            name="批次画像更新与失败重试",
            next_run_time=datetime.now(),
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
    
    scheduler.add_job(
        sync_models_job,
        trigger="interval",
        seconds=30,
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
        id="sync_models_job",
        name="同步模型信息",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("定时任务调度器已启动")
    
    return scheduler
