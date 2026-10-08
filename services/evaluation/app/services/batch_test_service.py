"""
批量测试服务层
"""
import json
import time
import uuid
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.scene import Scene
from app.models.scene_prompt import ScenePrompt
from app.schemas.evaluation import AIScoreResult, ai_score_result_to_json
from app.core.errors import BusinessException, ErrorCode
from app.core.logging_config import logger


class BatchTestService:
    """
    批量测试服务类
    """

    @staticmethod
    async def create_batch_test_task(db: AsyncSession, request_data: dict, user_id: int) -> str:
        """
        创建批量测试任务

        Args:
            db: 数据库会话
            request_data: 请求数据
            user_id: 用户ID

        Returns:
            任务ID

        Raises:
            BusinessException: 业务异常
        """
        from app.services.model_service import ModelService
        await ModelService(db).refresh_catalog()
        scene_id = request_data.get("scene_id") or request_data.get("sceneId")
        if not scene_id or not str(scene_id).strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "场景ID不能为空")

        models = request_data.get("models")
        if not models or not isinstance(models, list) or len(models) == 0:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "模型列表不能为空")

        scene_result = await db.execute(
            select(Scene).where(Scene.id == scene_id.strip(), Scene.is_delete == 0)
        )
        scene = scene_result.scalar_one_or_none()
        if not scene:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "场景不存在")

        if scene.is_preset == 0 and scene.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限使用该场景")

        prompts_result = await db.execute(
            select(ScenePrompt)
            .where(ScenePrompt.scene_id == scene_id.strip(), ScenePrompt.is_delete == 0)
            .order_by(ScenePrompt.prompt_index.asc())
        )
        prompts = list(prompts_result.scalars().all())
        if not prompts:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "场景中没有提示词")

        task_id = str(uuid.uuid4())
        total_subtasks = len(models) * len(prompts)

        config_map = {"taskType": request_data.get("task_type") or request_data.get("taskType") or "general"}
        config_map["promptSnapshot"] = [{"id": p.id, "title": p.title, "content": p.content} for p in prompts]
        if request_data.get("temperature") is not None:
            config_map["temperature"] = request_data["temperature"]
        if request_data.get("top_p") is not None:
            config_map["topP"] = request_data["top_p"]
        if request_data.get("topP") is not None:
            config_map["topP"] = request_data["topP"]
        if request_data.get("max_tokens") is not None:
            config_map["maxTokens"] = request_data["max_tokens"]
        if request_data.get("maxTokens") is not None:
            config_map["maxTokens"] = request_data["maxTokens"]
        if request_data.get("top_k") is not None:
            config_map["topK"] = request_data["top_k"]
        if request_data.get("topK") is not None:
            config_map["topK"] = request_data["topK"]
        if request_data.get("frequency_penalty") is not None:
            config_map["frequencyPenalty"] = request_data["frequency_penalty"]
        if request_data.get("frequencyPenalty") is not None:
            config_map["frequencyPenalty"] = request_data["frequencyPenalty"]
        if request_data.get("presence_penalty") is not None:
            config_map["presencePenalty"] = request_data["presence_penalty"]
        if request_data.get("presencePenalty") is not None:
            config_map["presencePenalty"] = request_data["presencePenalty"]
        if request_data.get("enable_ai_scoring") is not None:
            config_map["enableAiScoring"] = request_data["enable_ai_scoring"]
        if request_data.get("enableAiScoring") is not None:
            config_map["enableAiScoring"] = request_data["enableAiScoring"]
        config_json = json.dumps(config_map) if config_map else None

        models_json = json.dumps(models)

        task = TestTask(
            id=task_id,
            user_id=user_id,
            name=request_data.get("name"),
            scene_id=scene_id.strip(),
            models=models_json,
            config=config_json,
            status="pending",
            total_subtasks=total_subtasks,
            completed_subtasks=0,
            is_delete=0
        )
        db.add(task)
        await db.commit()

        logger.info(
            "创建批量测试任务: taskId={}, sceneId={}, models={}, prompts={}, totalSubtasks={}",
            task_id, scene_id, len(models), len(prompts), total_subtasks
        )

        from app.services.progress_service import publish_progress
        from app.services.batch_test_worker import run_subtask_sync

        publish_progress(task_id, {
            "taskId": task_id,
            "percentage": 0,
            "completedSubtasks": 0,
            "totalSubtasks": total_subtasks,
            "status": "pending",
            "timestamp": int(time.time() * 1000)
        })

        subtasks = []
        for model_name in models:
            for prompt in prompts:
                sub_task_data = {
                    "taskId": task_id,
                    "sceneId": scene_id.strip(),
                    "promptId": prompt.id,
                    "promptTitle": prompt.title,
                    "promptContent": prompt.content,
                    "modelName": model_name,
                    "userId": user_id
                }
                subtasks.append(sub_task_data)

        from app.services.batch_test_runner import start_batch
        start_batch(task_id, subtasks, run_subtask_sync)

        return task_id

    @staticmethod
    async def restart_batch_test(db: AsyncSession, task_id: str, user_id: int) -> str:
        """Start a fresh run from the original configuration and frozen prompts."""
        from app.services.model_service import ModelService
        from app.services.batch_test_runner import start_batch, is_batch_running
        from app.services.batch_test_worker import run_subtask_sync
        original = await BatchTestService.get_task(db, task_id, user_id)
        if original.status in ("pending", "running") or is_batch_running(task_id):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "任务仍在执行，请结束后再从头测试")
        models = json.loads(original.models)
        config = json.loads(original.config or '{}')
        available = {m.id for m in await ModelService(db).get_all_models()}
        missing = [m for m in models if m not in available]
        if missing:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "原任务模型已停用或删除，请先启用：" + "、".join(missing))
        prompts = config.get('promptSnapshot')
        if not prompts:
            current = list((await db.execute(select(ScenePrompt).where(
                ScenePrompt.scene_id == original.scene_id, ScenePrompt.is_delete == 0
            ).order_by(ScenePrompt.prompt_index.asc()))).scalars().all())
            prompts = [{"id": p.id, "title": p.title, "content": p.content} for p in current]
            saved = list((await db.execute(select(TestResult).where(
                TestResult.task_id == task_id, TestResult.is_delete == 0))).scalars().all())
            content = {p['id']: p['content'] for p in prompts}
            if len(prompts) * len(models) != original.total_subtasks or any(
                content.get(r.prompt_id) != r.input_prompt for r in saved
            ):
                raise BusinessException(ErrorCode.PARAMS_ERROR, "原任务未保存题目快照且场景已变更，请重新配置测试")
        if not prompts or not models:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "原任务缺少模型或题目")
        config['promptSnapshot'] = prompts
        config.pop('resumeCount', None)
        config.pop('aiScoringProgress', None)
        config['restartOf'] = task_id
        config['restartCount'] = int(config.get('restartCount', 0)) + 1
        config['originalName'] = config.get('originalName') or original.name or '未命名'
        run_name = f"{config['originalName']}（重跑{config['restartCount']} · {datetime.now():%m-%d %H:%M:%S}）"
        new_id = str(uuid.uuid4())
        new_task = TestTask(id=new_id, user_id=user_id, name=run_name,
            scene_id=original.scene_id, models=original.models,
            config=json.dumps(config, ensure_ascii=False), status='pending',
            total_subtasks=len(models)*len(prompts), completed_subtasks=0, is_delete=0)
        db.add(new_task)
        await db.commit()
        subtasks = [{"taskId": new_id, "sceneId": original.scene_id,
            "promptId": p['id'], "promptTitle": p.get('title', ''),
            "promptContent": p['content'], "modelName": m, "userId": user_id}
            for m in models for p in prompts]
        start_batch(new_id, subtasks, run_subtask_sync)
        return new_id

    @staticmethod
    async def resume_batch_test(db: AsyncSession, task_id: str, user_id: int) -> dict:
        from datetime import datetime
        from app.services.batch_test_runner import start_batch, is_batch_running
        from app.services.batch_test_worker import run_subtask_sync
        task = (await db.execute(select(TestTask).where(
            TestTask.id == task_id, TestTask.is_delete == 0).with_for_update())).scalar_one_or_none()
        if task is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")
        if task.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限重试该任务")
        from app.services.missing_score_service import _jobs as scoring_jobs
        if task_id in scoring_jobs:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "正在补评分，请等待完成后继续重试")
        if is_batch_running(task_id) or task.status in ("pending", "running"):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "任务仍在执行，请等待当前请求结束后重试")
        if task.status not in ("failed", "cancelled"):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "只有失败或取消的任务可以继续重试")
        config = json.loads(task.config or '{}')
        models = json.loads(task.models)
        saved = list((await db.execute(select(TestResult).where(
            TestResult.task_id == task_id, TestResult.is_delete == 0))).scalars().all())
        prompts = config.get('promptSnapshot')
        if not prompts:
            current = list((await db.execute(select(ScenePrompt).where(
                ScenePrompt.scene_id == task.scene_id, ScenePrompt.is_delete == 0))).scalars().all())
            prompts = [{"id": p.id, "title": p.title, "content": p.content} for p in current]
            content = {p['id']: p['content'] for p in prompts}
            if len(prompts)*len(models) != task.total_subtasks or any(
                    content.get(r.prompt_id) != r.input_prompt for r in saved):
                raise BusinessException(ErrorCode.PARAMS_ERROR, "原场景题目已变更，无法安全续跑，请重新测试")
        done = {(r.model_name, r.prompt_id) for r in saved}
        pairs = {(m, p['id']) for m in models for p in prompts}
        if len(pairs) != task.total_subtasks or not done.issubset(pairs):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "任务数据不一致，无法继续重试")
        subtasks = [{"taskId": task_id, "sceneId": task.scene_id, "promptId": p['id'],
                     "promptTitle": p['title'], "promptContent": p['content'],
                     "modelName": m, "userId": user_id}
                    for m in models for p in prompts if (m, p['id']) not in done]
        task.completed_subtasks = len(done)
        task.completed_at = None if subtasks else datetime.now()
        task.status = 'pending' if subtasks else 'completed'
        config['promptSnapshot'] = prompts
        config['resumeCount'] = config.get('resumeCount', 0)+1
        task.config = json.dumps(config, ensure_ascii=False)
        await db.commit()
        if subtasks:
            start_batch(task_id, subtasks, run_subtask_sync)
        return {"taskId": task_id, "retainedResults": len(done), "retrySubtasks": len(subtasks)}

    @staticmethod
    async def get_task(db: AsyncSession, task_id: str, user_id: int) -> TestTask:
        """
        获取任务详情

        Args:
            db: 数据库会话
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            任务对象

        Raises:
            BusinessException: 业务异常
        """
        result = await db.execute(
            select(TestTask).where(TestTask.id == task_id.strip(), TestTask.is_delete == 0)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "任务不存在")

        if task.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看")

        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        user_id: int,
        query_request: dict
    ) -> dict:
        """
        分页查询任务列表

        Args:
            db: 数据库会话
            user_id: 用户ID
            query_request: 查询参数

        Returns:
            分页结果
        """
        conditions = [TestTask.user_id == user_id, TestTask.is_delete == 0]

        category = query_request.get("category")
        if category and str(category).strip():
            scene_result = await db.execute(
                select(Scene.id).where(Scene.category == str(category).strip(), Scene.is_delete == 0)
            )
            scene_ids = [row[0] for row in scene_result.fetchall()]
            if scene_ids:
                conditions.append(TestTask.scene_id.in_(scene_ids))
            else:
                conditions.append(TestTask.id == "impossible")

        status = query_request.get("status")
        if status and str(status).strip():
            conditions.append(TestTask.status == str(status).strip())

        keyword = query_request.get("keyword")
        if keyword and str(keyword).strip():
            conditions.append(TestTask.name.like(f"%{str(keyword).strip()}%"))

        start_time = query_request.get("start_time") or query_request.get("startTime")
        if start_time and str(start_time).strip():
            try:
                dt = datetime.strptime(str(start_time).strip(), "%Y-%m-%d %H:%M:%S")
                conditions.append(TestTask.create_time >= dt)
            except ValueError:
                logger.warning("解析开始时间失败: %s", start_time)

        end_time = query_request.get("end_time") or query_request.get("endTime")
        if end_time and str(end_time).strip():
            try:
                dt = datetime.strptime(str(end_time).strip(), "%Y-%m-%d %H:%M:%S")
                conditions.append(TestTask.create_time <= dt)
            except ValueError:
                logger.warning("解析结束时间失败: %s", end_time)

        page_num = query_request.get("page_num") or query_request.get("pageNum") or 1
        page_size = query_request.get("page_size") or query_request.get("pageSize") or 10

        count_result = await db.execute(
            select(func.count()).select_from(TestTask).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        offset = (page_num - 1) * page_size
        result = await db.execute(
            select(TestTask)
            .where(and_(*conditions))
            .order_by(TestTask.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        records = result.scalars().all()

        return {
            "records": [BatchTestService._task_to_dict(t) for t in records],
            "total": total,
            "totalRow": total,
            "pageNum": page_num,
            "pageSize": page_size
        }

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: str, user_id: int) -> bool:
        """
        删除任务

        Args:
            db: 数据库会话
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            是否成功

        Raises:
            BusinessException: 业务异常
        """
        task = await BatchTestService.get_task(db, task_id, user_id)
        task.is_delete = 1
        task.status = 'cancelled'
        await db.commit()
        from app.services.batch_cancellation import cancel_batch_calls
        from app.services.batch_test_runner import cancel_batch
        cancel_batch_calls(task_id)
        cancel_batch(task_id)
        return True

    @staticmethod
    async def get_task_results(db: AsyncSession, task_id: str, user_id: int) -> List[dict]:
        """
        获取任务的测试结果

        Args:
            db: 数据库会话
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            测试结果列表

        Raises:
            BusinessException: 业务异常
        """
        await BatchTestService.get_task(db, task_id, user_id)

        result = await db.execute(
            select(TestResult)
            .where(TestResult.task_id == task_id.strip(), TestResult.is_delete == 0)
            .order_by(TestResult.create_time.asc())
        )
        results = result.scalars().all()

        return [BatchTestService._result_to_dict(r) for r in results]

    @staticmethod
    async def update_test_result_rating(
        db: AsyncSession,
        result_id: str,
        user_rating: Optional[int],
        user_id: int
    ) -> bool:
        """
        更新测试结果评分

        Args:
            db: 数据库会话
            result_id: 测试结果ID
            user_rating: 用户评分(1-5)
            user_id: 用户ID

        Returns:
            是否成功

        Raises:
            BusinessException: 业务异常
        """
        if not result_id or not str(result_id).strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "测试结果ID不能为空")

        if user_rating is not None and (user_rating < 1 or user_rating > 5):
            raise BusinessException(ErrorCode.PARAMS_ERROR, "评分必须在1-5之间")

        result = await db.execute(
            select(TestResult).where(TestResult.id == result_id.strip(), TestResult.is_delete == 0)
        )
        test_result = result.scalar_one_or_none()
        if not test_result:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "测试结果不存在")

        if test_result.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限修改该测试结果")

        test_result.user_rating = user_rating
        test_result.update_time = datetime.now()
        await db.commit()

        logger.info("更新测试结果评分: resultId=%s, userId=%s, rating=%s", result_id, user_id, user_rating)
        return True

    @staticmethod
    async def update_test_result_ai_score(
        db: AsyncSession,
        result_id: str,
        ai_score_result: AIScoreResult,
        user_id: int
    ) -> bool:
        """
        更新测试结果的 AI 评分

        Args:
            db: 数据库会话
            result_id: 测试结果ID
            ai_score_result: AI 评分结果
            user_id: 用户ID

        Returns:
            是否成功

        Raises:
            BusinessException: 业务异常
        """
        if not result_id or not str(result_id).strip():
            raise BusinessException(ErrorCode.PARAMS_ERROR, "测试结果ID不能为空")

        result = await db.execute(
            select(TestResult).where(TestResult.id == result_id.strip(), TestResult.is_delete == 0)
        )
        test_result = result.scalar_one_or_none()
        if not test_result:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "测试结果不存在")

        if test_result.user_id != user_id:
            raise BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限修改该测试结果")

        test_result.ai_score = ai_score_result_to_json(ai_score_result)
        test_result.update_time = datetime.now()
        await db.commit()

        logger.info("更新测试结果AI评分: resultId=%s, userId=%s", result_id, user_id)
        return True

    @staticmethod
    def _task_to_dict(task: TestTask) -> dict:
        """将TestTask对象转为前端需要的字典格式"""
        cost_val = task.cost if hasattr(task, 'cost') else None
        try:
            run_config = json.loads(task.config or '{}')
        except (ValueError, TypeError):
            run_config = {}
        progress = run_config.get("aiScoringProgress")
        if progress and progress.get("status") == "running":
            from app.services.missing_score_service import _jobs
            if task.id not in _jobs:
                progress = {**progress, "status": "interrupted"}
        return {
            "id": task.id,
            "userId": task.user_id,
            "name": task.name,
            "restartOf": run_config.get("restartOf"),
            "restartCount": run_config.get("restartCount", 1 if run_config.get("restartOf") else 0),
            "resumeCount": run_config.get("resumeCount", 0),
            "scoringProgress": progress,
            "sceneId": task.scene_id,
            "models": task.models,
            "config": task.config,
            "status": task.status,
            "totalSubtasks": task.total_subtasks,
            "completedSubtasks": task.completed_subtasks,
            "startedAt": task.started_at.isoformat() if task.started_at else None,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
            "createTime": task.create_time.isoformat() if task.create_time else None,
            "updateTime": task.update_time.isoformat() if task.update_time else None
        }

    @staticmethod
    def _result_to_dict(result: TestResult) -> dict:
        """将TestResult对象转为前端需要的字典格式"""
        cost_val = float(result.cost) if result.cost is not None else None
        return {
            "id": result.id,
            "taskId": result.task_id,
            "userId": result.user_id,
            "sceneId": result.scene_id,
            "promptId": result.prompt_id,
            "modelName": result.model_name,
            "inputPrompt": result.input_prompt,
            "outputText": result.output_text,
            "resultStatus": "success" if (result.output_text or "").strip() else "empty",
            "reasoning": result.reasoning,
            "responseTimeMs": result.response_time_ms,
            "inputTokens": result.input_tokens,
            "outputTokens": result.output_tokens,
            "cost": cost_val,
            "costCurrency": getattr(result, "cost_currency", "UNKNOWN"),
            "userRating": result.user_rating,
            "aiScore": result.ai_score,
            "createTime": result.create_time.isoformat() if result.create_time else None,
            "updateTime": result.update_time.isoformat() if result.update_time else None
        }
