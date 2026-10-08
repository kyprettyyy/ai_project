"""Repair missing scores without regenerating answers or publishing profiles."""
import asyncio
import json
import math
from sqlalchemy import select, update
from openai import OpenAI
from app.core.config import get_settings
from app.core.errors import BusinessException, ErrorCode
from app.db.sync_session import get_sync_session
from app.db.redis import get_redis_client_sync
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.scene_prompt import ScenePrompt
from app.services.batch_cancellation import register_client, unregister_client
from app.services.ai_scoring_service import run_ai_scoring_sync
from app.schemas.evaluation import ai_score_result_to_json

_jobs = {}
_lock = asyncio.Lock()


def valid_score(raw):
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        rating = data['averageRating']
        return (isinstance(rating, (int, float)) and not isinstance(rating, bool)
                and math.isfinite(rating) and 0 <= rating <= 10
                and isinstance(data.get('judges'), list) and bool(data['judges']))
    except (ValueError, TypeError, KeyError):
        return False


def eligible(result):
    return bool((result.output_text or '').strip()) and not valid_score(result.ai_score)


def save_progress(session, task, progress):
    config = json.loads(task.config or '{}')
    config['aiScoringProgress'] = progress
    task.config = json.dumps(config, ensure_ascii=False)
    session.commit()


async def start_missing_scores(db, task):
    async with _lock:
        if task.id in _jobs:
            raise BusinessException(ErrorCode.PARAMS_ERROR, '该任务正在补评分，请等待完成')
        if task.status in ('pending', 'running'):
            raise BusinessException(ErrorCode.PARAMS_ERROR, '请等待回答生成结束后补评分')
        rows = (await db.execute(select(TestResult).where(TestResult.task_id == task.id, TestResult.is_delete == 0))).scalars().all()
        ids = [r.id for r in rows if eligible(r)]
        progress = dict(status='running' if ids else 'completed', total=len(ids), processed=0,
                        succeeded=0, failed=0, errors=[], skipped=len(rows)-len(ids))
        config = json.loads(task.config or '{}')
        config['aiScoringProgress'] = progress
        task.config = json.dumps(config, ensure_ascii=False)
        await db.commit()
        if ids:
            job = asyncio.create_task(asyncio.to_thread(repair, task.id, ids, progress.copy()))
            _jobs[task.id] = job
            job.add_done_callback(lambda finished: _jobs.pop(task.id, None))
        return progress


def repair(task_id, ids, progress):
    session = get_sync_session()
    client = None
    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.GATEWAY_API_KEY, base_url=settings.gateway_openai_base_url)
        register_client(task_id, client)
        for result_id in ids:
            session.expire_all()
            task = session.get(TestTask, task_id)
            if not task or task.is_delete:
                return
            result = session.get(TestResult, result_id)
            error = None
            if result and not result.is_delete and eligible(result):
                original = result.ai_score
                prompt = session.get(ScenePrompt, result.prompt_id)
                reference = None
                try:
                    reference = json.loads(prompt.expected_output) if prompt and prompt.expected_output else None
                    if not isinstance(reference, dict): reference = None
                except (ValueError, TypeError): pass
                try:
                    score = run_ai_scoring_sync(session, client, result.input_prompt, result.output_text,
                        result.model_name, extra_headers={'X-Eval-Run-Id': task_id,
                        'X-Task-Type': 'evaluation_judge', 'X-Client': 'EvalRoute Evaluation'},
                        user_id=task.user_id, redis_client=get_redis_client_sync(), reference=reference)
                    if score is None:
                        error = '未获得有效评分：请检查评分模型可用性、余额或评分返回格式'
                    else:
                        raw = ai_score_result_to_json(score)
                        if not valid_score(raw):
                            error = '评分返回格式不完整'
                        else:
                            changed = session.execute(update(TestResult).where(TestResult.id == result_id,
                                TestResult.ai_score == original).values(ai_score=raw)).rowcount
                            progress['succeeded'] += int(bool(changed))
                except Exception as exc:
                    session.rollback()
                    error = f'评分调用失败（{type(exc).__name__}），可再次补评'
            if error:
                progress['failed'] += 1
                progress['errors'].append({'resultId': result_id, 'message': error})
            progress['processed'] += 1
            session.expire_all()
            task = session.get(TestTask, task_id)
            if not task or task.is_delete: return
            save_progress(session, task, progress)
        progress['status'] = 'partial' if progress['failed'] else 'completed'
        save_progress(session, task, progress)
    except Exception as exc:
        session.rollback()
        task = session.get(TestTask, task_id)
        if task and not task.is_delete:
            progress['status'] = 'interrupted'
            progress['errors'].append({'message': f'补评分中断（{type(exc).__name__}），已有分数保留，可再次补评'})
            save_progress(session, task, progress)
    finally:
        if client is not None: unregister_client(task_id, client)
        session.close()
