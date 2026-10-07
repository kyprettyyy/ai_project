"""Keep one background coordinator alive until every result and score is saved."""

import asyncio
from collections.abc import Callable

from app.core.logging_config import logger


_running_batches: set[asyncio.Task] = set()


async def run_batch(task_id: str, subtasks: list[dict], worker: Callable) -> None:
    semaphore = asyncio.Semaphore(5)

    async def run_one(data: dict):
        async with semaphore:
            return await asyncio.to_thread(worker, data)

    results = await asyncio.gather(*(run_one(data) for data in subtasks), return_exceptions=True)
    if any(isinstance(result, BaseException) or result.get("error") or result.get("skipped")
           for result in results):
        logger.warning("批次未全部成功，保留评测结果，不自动发布画像: taskId={}", task_id)
        return

    # The job uses its own DB session; the HTTP request session is already closed.
    from app.jobs.model_profile_job import update_model_profiles_job
    await update_model_profiles_job()


def start_batch(task_id: str, subtasks: list[dict], worker: Callable) -> None:
    task = asyncio.create_task(run_batch(task_id, subtasks, worker))
    _running_batches.add(task)
    task.add_done_callback(_running_batches.discard)
