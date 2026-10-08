"""Keep one background coordinator alive until every result and score is saved."""

import asyncio
from collections.abc import Callable

from app.core.logging_config import logger


_running_batches: set[asyncio.Task] = set()
_active_task_ids: set[str] = set()
_batch_tasks: dict[str, asyncio.Task] = {}

def cancel_batch(task_id):
    task = _batch_tasks.get(task_id)
    if task is not None: task.cancel()


def is_batch_running(task_id: str) -> bool:
    return task_id in _active_task_ids


async def run_batch(task_id: str, subtasks: list[dict], worker: Callable) -> None:
    semaphore = asyncio.Semaphore(5)

    async def run_one(data: dict):
        async with semaphore:
            from app.services.batch_cancellation import is_cancelled
            if is_cancelled(task_id): return {'skipped': True}
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
    if task_id in _active_task_ids:
        raise RuntimeError("批次仍在执行")
    _active_task_ids.add(task_id)
    task = asyncio.create_task(run_batch(task_id, subtasks, worker))
    _running_batches.add(task)
    _batch_tasks[task_id] = task
    def finished(done):
        _running_batches.discard(done)
        _active_task_ids.discard(task_id)
        _batch_tasks.pop(task_id, None)
    task.add_done_callback(finished)
