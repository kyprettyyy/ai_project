"""Publish satisfaction in batches; retries do not overwrite offline quality profiles."""
import asyncio
import logging
from app.db.session import session_maker
from app.services.answer_feedback_service import AnswerFeedbackService
logger = logging.getLogger(__name__)

async def run_feedback_loop(stop_event):
    while not stop_event.is_set():
        try:
            async with session_maker() as db:
                await AnswerFeedbackService(db).publish_batches()
        except Exception:
            logger.exception('线上满意度画像批次更新失败，将在下一轮重试')
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass
