"""Feedback ownership and aggregation. Unrated answers are never positive votes."""
from datetime import datetime
from sqlalchemy import func, select
from fastapi import HTTPException
from app.models.request_log import RequestLog
from app.models.model import Model
from app.models.answer_feedback import OnlineAnswer, AnswerFeedback, SatisfactionProfile, PersonalSatisfactionProfile

BATCH_SIZE = 30

class AnswerFeedbackService:
    def __init__(self, db):
        self.db = db

    async def save_answer(self, log, messages, answer):
        if log.evaluation_run_id or not answer.strip():
            return
        question = next((m.content for m in reversed(messages) if m.role == 'user'), '')
        if not isinstance(question, str):
            import json
            question = json.dumps(question, ensure_ascii=False)
        self.db.add(OnlineAnswer(request_log_id=log.id, trace_id=log.trace_id,
                                 question=question, answer=answer))
        await self.db.commit()

    async def submit(self, trace_id, vote, reason, comment, user_id, api_key_id=None):
        # Serialize edits through the existing log row, including first submissions.
        log = await self.db.scalar(select(RequestLog).where(
            RequestLog.trace_id == trace_id, RequestLog.status == 'success',
            RequestLog.request_type == 'chat', RequestLog.evaluation_run_id.is_(None),
            RequestLog.user_id == user_id,
            RequestLog.api_key_id == api_key_id,
        ).with_for_update())
        if not log or not await self.db.get(OnlineAnswer, log.id):
            raise HTTPException(404, '回答不存在或无权评价此回答')
        row = await self.db.get(AnswerFeedback, log.id)
        if row is None:
            row = AnswerFeedback(request_log_id=log.id)
            self.db.add(row)
        normalized_reason = reason if vote == -1 else None
        normalized_comment = (comment or '').strip() or None
        if (row.vote, row.reason, row.comment) != (vote, normalized_reason, normalized_comment):
            row.vote, row.reason, row.comment = vote, normalized_reason, normalized_comment
            row.updated_at = datetime.utcnow()
        await self.db.commit()
        return {'requestId': trace_id, 'vote': row.vote, 'reason': row.reason, 'comment': row.comment}

    async def publish_batches(self):
        groups = (await self.db.execute(select(RequestLog.model_id, RequestLog.task_type)
            .join(AnswerFeedback, AnswerFeedback.request_log_id == RequestLog.id)
            .where(RequestLog.model_id.is_not(None)).distinct().order_by(RequestLog.model_id, RequestLog.task_type))).all()
        updated = 0
        for model_id, task_type in groups:
            task_type = task_type or 'general'
            # Parent lock prevents two gateway processes publishing the same batch.
            model = await self.db.scalar(select(Model).where(Model.id == model_id).with_for_update())
            if not model or model.is_delete:
                continue
            profile = await self.db.scalar(select(SatisfactionProfile).where(
                SatisfactionProfile.model_id == model_id, SatisfactionProfile.task_type == task_type)
                .execution_options(populate_existing=True))
            votes = list((await self.db.scalars(select(AnswerFeedback).join(
                RequestLog, RequestLog.id == AnswerFeedback.request_log_id).where(
                RequestLog.model_id == model_id, func.coalesce(RequestLog.task_type, 'general') == task_type))).all())
            changed = sum(1 for row in votes if not profile or not profile.published_at or row.updated_at > profile.published_at)
            if len(votes) < BATCH_SIZE or changed < BATCH_SIZE:
                continue
            if not profile:
                profile = SatisfactionProfile(model_id=model_id, task_type=task_type, version=0)
                self.db.add(profile)
            profile.sample_count = len(votes)
            profile.positive_count = sum(row.vote == 1 for row in votes)
            profile.version = (profile.version or 0) + 1
            # High-water mark of the snapshot; later edits are picked up next batch.
            profile.published_at = max(row.updated_at for row in votes)
            updated += 1
        await self.db.commit()
        await self.publish_personal_batches()
        return updated

    async def publish_personal_batches(self):
        from app.models.user import User
        valid = [RequestLog.user_id.is_not(None), RequestLog.model_id.is_not(None),
                 RequestLog.evaluation_run_id.is_(None), RequestLog.status == 'success',
                 AnswerFeedback.vote.in_([-1, 1])]
        groups = (await self.db.execute(select(RequestLog.user_id, RequestLog.model_id,
            func.coalesce(func.nullif(RequestLog.task_type, ''), 'general'))
            .join(AnswerFeedback, AnswerFeedback.request_log_id == RequestLog.id)
            .where(*valid).distinct())).all()
        updated = 0
        for uid, mid, task in groups:
            owner = await self.db.scalar(select(User).where(User.id == uid, User.is_delete == 0).with_for_update())
            if owner is None: continue
            profile = await self.db.scalar(select(PersonalSatisfactionProfile).where(
                PersonalSatisfactionProfile.user_id == uid, PersonalSatisfactionProfile.model_id == mid,
                PersonalSatisfactionProfile.task_type == task).execution_options(populate_existing=True))
            votes = list((await self.db.scalars(select(AnswerFeedback).join(RequestLog,
                RequestLog.id == AnswerFeedback.request_log_id).where(*valid, RequestLog.user_id == uid,
                RequestLog.model_id == mid, func.coalesce(func.nullif(RequestLog.task_type, ''), 'general') == task))).all())
            changed = sum(not profile or not profile.published_at or v.updated_at > profile.published_at for v in votes)
            if len(votes) < BATCH_SIZE or changed < BATCH_SIZE: continue
            if profile is None:
                profile = PersonalSatisfactionProfile(user_id=uid, model_id=mid, task_type=task, version=0)
                self.db.add(profile)
            profile.sample_count = len(votes)
            profile.positive_count = sum(v.vote == 1 for v in votes)
            profile.version = (profile.version or 0) + 1
            profile.published_at = max(v.updated_at for v in votes)
            updated += 1
        await self.db.commit()
        return updated

    async def summary(self):
        stmt = (select(RequestLog.model_id, RequestLog.model_name,
            func.coalesce(RequestLog.task_type, 'general'), func.count(RequestLog.id),
            func.count(AnswerFeedback.request_log_id), func.sum(AnswerFeedback.vote == 1))
            .join(OnlineAnswer, OnlineAnswer.request_log_id == RequestLog.id)
            .outerjoin(AnswerFeedback, AnswerFeedback.request_log_id == RequestLog.id)
            .where(RequestLog.evaluation_run_id.is_(None), RequestLog.status == 'success')
            .group_by(RequestLog.model_id, RequestLog.model_name, func.coalesce(RequestLog.task_type, 'general')))
        profiles = {(p.model_id, p.task_type): p for p in (await self.db.scalars(select(SatisfactionProfile))).all()}
        rows = []
        for mid, model, task, answers, feedback, positive in (await self.db.execute(stmt)).all():
            positive = int(positive or 0)
            p = profiles.get((mid, task))
            rows.append({'model':model, 'taskType':task, 'answerCount':answers,
                'feedbackCount':feedback, 'positiveCount':positive, 'negativeCount':feedback-positive,
                'satisfactionRate':positive/feedback if feedback else None,
                'feedbackCoverage':feedback/answers if answers else 0,
                'profileSampleCount':p.sample_count if p else 0, 'profileVersion':p.version if p else 0,
                'publishedSatisfactionRate':p.positive_count/p.sample_count if p and p.sample_count else None})
        return {'batchSize': BATCH_SIZE, 'rows': rows}

    async def recent(self, limit=50):
        stmt = (select(RequestLog, OnlineAnswer, AnswerFeedback)
            .join(OnlineAnswer, OnlineAnswer.request_log_id == RequestLog.id)
            .join(AnswerFeedback, AnswerFeedback.request_log_id == RequestLog.id)
            .order_by(AnswerFeedback.updated_at.desc()).limit(limit))
        return [{'requestId':log.trace_id, 'model':log.model_name, 'taskType':log.task_type or 'general',
                 'question':answer.question, 'answer':answer.answer, 'vote':feedback.vote,
                 'reason':feedback.reason, 'comment':feedback.comment,
                 'updatedAt':feedback.updated_at.isoformat()} for log, answer, feedback in (await self.db.execute(stmt)).all()]
