import sys, unittest
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.mysql import TINYINT
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/gateway'))
from app.models.model import Model
from app.models.request_log import RequestLog
from app.models.answer_feedback import OnlineAnswer, AnswerFeedback, SatisfactionProfile, PersonalSatisfactionProfile
from app.models.user import User
from app.models.model_capability_profile import ModelCapabilityProfile
from app.services.answer_feedback_service import AnswerFeedbackService
from app.routing.explainable_router import CandidateSignals, ExplainableRouter, RoutingContext
from decimal import Decimal

@compiles(BigInteger, 'sqlite')
@compiles(TINYINT, 'sqlite')
def sqlite_integer(element, compiler, **kwargs): return 'INTEGER'

class AnswerFeedbackTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite://')
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda conn: Model.metadata.create_all(conn, tables=[
                User.__table__, PersonalSatisfactionProfile.__table__, Model.__table__, RequestLog.__table__, OnlineAnswer.__table__,
                AnswerFeedback.__table__, SatisfactionProfile.__table__, ModelCapabilityProfile.__table__]))
        async with self.sessions() as db:
            db.add(User(id=1,user_account='one',user_password='unused'))
            db.add(User(id=2,user_account='two',user_password='unused'))
            db.add(Model(id=1, provider_id=1, model_key='actual', model_name='Actual'))
            db.add(ModelCapabilityProfile(model_id=1, model_key='actual', task_type='general', quality_score=.9, sample_count=50))
            for i in range(1, 62):
                db.add(RequestLog(id=i, trace_id=f'call-{i}', user_id=1, api_key_id=7 if i==61 else None,
                                  model_id=1, model_name='actual', task_type='general', status='success'))
                db.add(OnlineAnswer(request_log_id=i, trace_id=f'call-{i}', question='Question', answer='Answer'))
            await db.commit()

    async def test_personal_batches_isolate_users_and_require_30(self):
        async with self.sessions() as db:
            for i in range(1,61):
                log=await db.get(RequestLog,i)
                log.user_id=1 if i<=30 else 2
                db.add(AnswerFeedback(request_log_id=i,vote=1 if i<=30 else -1,updated_at=datetime.utcnow()))
            await db.commit()
            service=AnswerFeedbackService(db)
            self.assertEqual(await service.publish_personal_batches(),2)
            one=await db.get(PersonalSatisfactionProfile,(1,1,'general'))
            two=await db.get(PersonalSatisfactionProfile,(2,1,'general'))
            self.assertEqual((one.sample_count,one.positive_count),(30,30))
            self.assertEqual((two.sample_count,two.positive_count),(30,0))
            from app.services.personal_routing_service import other_users_priors
            prior_one = await other_users_priors(db,1,[1],['general'])
            prior_two = await other_users_priors(db,2,[1],['general'])
            self.assertAlmostEqual(prior_one[(1,'general')][0],1/32)
            self.assertAlmostEqual(prior_two[(1,'general')][0],31/32)
            self.assertEqual(await service.publish_personal_batches(),0)
            offline=await db.scalar(select(ModelCapabilityProfile))
            self.assertAlmostEqual(float(offline.quality_score),.9)

    async def asyncTearDown(self): await self.engine.dispose()

    async def test_duplicate_vote_is_one_row_and_edit_replaces_it(self):
        async with self.sessions() as db:
            service=AnswerFeedbackService(db)
            await service.submit('call-1', -1, 'incorrect', 'wrong', 1)
            row=await db.get(AnswerFeedback, 1); original=row.updated_at
            await service.submit('call-1', -1, 'incorrect', 'wrong', 1)
            self.assertEqual(row.updated_at, original)
            await service.submit('call-1', 1, 'incorrect', None, 1)
            summary=await service.summary()
            self.assertEqual(summary['rows'][0]['feedbackCount'], 1)
            self.assertEqual(summary['rows'][0]['positiveCount'], 1)
            self.assertIsNone(row.reason)
            self.assertAlmostEqual(summary['rows'][0]['feedbackCoverage'],1/61)

    async def test_owner_key_and_success_required(self):
        async with self.sessions() as db:
            service=AnswerFeedbackService(db)
            for trace, user, key in [('call-1', 2, None),('call-61', 1, None),('call-61', 1, 8)]:
                with self.assertRaises(HTTPException): await service.submit(trace, 1, None, None, user, key)
            await service.submit('call-61', 1, None, None, 1, 7)
            log=await db.get(RequestLog, 2); log.status='failed'; await db.commit()
            with self.assertRaises(HTTPException): await service.submit('call-2', 1, None, None, 1)
            log=await db.get(RequestLog, 3); log.evaluation_run_id='offline'; await db.commit()
            with self.assertRaises(HTTPException): await service.submit('call-3', 1, None, None, 1)

    async def test_unrated_is_not_positive_and_batches_leave_offline_profile_unchanged(self):
        async with self.sessions() as db:
            service=AnswerFeedbackService(db)
            self.assertIsNone((await service.summary())['rows'][0]['satisfactionRate'])
            for i in range(1,30): await service.submit(f'call-{i}', 1, None, None, 1)
            self.assertEqual(await service.publish_batches(),0)
            await service.submit('call-30', -1, 'incomplete', None, 1)
            self.assertEqual(await service.publish_batches(),1)
            self.assertEqual(await service.publish_batches(),0)
            profile=await db.scalar(select(SatisfactionProfile))
            self.assertEqual((profile.sample_count,profile.positive_count,profile.version),(30,29,1))
            quality=await db.scalar(select(ModelCapabilityProfile));self.assertAlmostEqual(float(quality.quality_score),.9)
            await service.submit('call-31', 1, None, None, 1)
            self.assertEqual(await service.publish_batches(),0)
            for i in range(32,61): await service.submit(f'call-{i}', -1, None, None, 1)
            self.assertEqual(await service.publish_batches(),1)
            self.assertEqual((profile.sample_count,profile.positive_count,profile.version),(60,30,2))

    async def test_only_nonempty_online_answers_are_eligible(self):
        async with self.sessions() as db:
            service=AnswerFeedbackService(db)
            for id, content, run in [(70,'',None),(71,'Answer','offline')]:
                log=RequestLog(id=id,trace_id=str(id),user_id=1,model_name='actual',evaluation_run_id=run)
                db.add(log);await db.commit()
                await service.save_answer(log,[SimpleNamespace(role='user',content='Question')],content)
                self.assertIsNone(await db.get(OnlineAnswer,id))

class SatisfactionRoutingTest(unittest.TestCase):
    def candidate(self, **extra):
        return CandidateSignals(model_id=1,model_key='model',context_length=32000,input_price=Decimal('0'),output_price=Decimal('0'),avg_latency_ms=100,live_success_rate=1,quality_score=.8,sample_count=50,**extra)
    def test_satisfaction_changes_routing_only_after_batch_without_changing_quality_confidence(self):
        router=ExplainableRouter(); context=RoutingContext()
        original=router.rank([self.candidate()],context).eligible[0]
        too_few=router.rank([self.candidate(satisfaction_score=0,satisfaction_samples=29)],context).eligible[0]
        published=router.rank([self.candidate(satisfaction_score=0,satisfaction_samples=30)],context).eligible[0]
        self.assertEqual(original.scores,too_few.scores)
        self.assertLess(published.scores['quality'],original.scores['quality'])
        self.assertGreater(published.scores['quality'],.64)
        self.assertEqual(published.snapshot()['feedbackEstimate']['algorithm'],'beta-bernoulli-v1')
        self.assertEqual(original.profile_confidence,published.profile_confidence)
        self.assertEqual(original.scores['latency'],published.scores['latency'])
        self.assertIn('共享反馈满意度',published.explanation)
