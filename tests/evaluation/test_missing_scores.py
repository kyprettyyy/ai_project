import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from app.services.missing_score_service import valid_score, eligible, start_missing_scores

class SelectionTests(unittest.TestCase):
    def test_existing_zero_score_is_preserved(self):
        raw = json.dumps({'averageRating': 0, 'judges': [{'rating': 0}]})
        self.assertTrue(valid_score(raw))
        self.assertFalse(eligible(SimpleNamespace(output_text='answer', ai_score=raw)))

    def test_empty_answers_are_not_called(self):
        self.assertFalse(eligible(SimpleNamespace(output_text='  ', ai_score=None)))

    def test_invalid_and_missing_scores_can_retry(self):
        for raw in (None, '{}', '{bad', '{"averageRating":10,"judges":[]}', '{"averageRating":NaN,"judges":[{}]}'):
            self.assertTrue(eligible(SimpleNamespace(output_text='answer', ai_score=raw)))

class StartTests(unittest.IsolatedAsyncioTestCase):
    async def test_running_answer_task_is_rejected(self):
        from app.core.errors import BusinessException
        db = AsyncMock()
        with self.assertRaises(BusinessException):
            await start_missing_scores(db, SimpleNamespace(id='test', status='running'))
        db.execute.assert_not_called()

    async def test_no_missing_scores_creates_no_paid_job(self):
        row = SimpleNamespace(id='r', output_text='answer', ai_score=json.dumps({'averageRating': 5, 'judges': [{'rating':5}]}))
        db = AsyncMock()
        from unittest.mock import MagicMock
        query = MagicMock()
        query.scalars.return_value.all.return_value = [row]
        db.execute.return_value = query
        task = SimpleNamespace(id='test', status='completed', config='{}')
        with patch('app.services.missing_score_service.asyncio.create_task') as spawn:
            result = await start_missing_scores(db, task)
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['skipped'], 1)
        spawn.assert_not_called()

class RepairTests(unittest.TestCase):
    def test_only_judge_is_called_and_original_answer_is_preserved(self):
        from unittest.mock import MagicMock
        from app.services.missing_score_service import repair
        from app.models.test_task import TestTask
        from app.models.test_result import TestResult
        from app.models.scene_prompt import ScenePrompt
        task = SimpleNamespace(id='t', is_delete=0, user_id=1, config='{}')
        result = SimpleNamespace(id='r', is_delete=0, ai_score=None, prompt_id='p',
                                 input_prompt='question', output_text='original answer', model_name='tested')
        session = MagicMock()
        session.get.side_effect = lambda model, key: task if model is TestTask else result if model is TestResult else None
        session.execute.return_value.rowcount = 1
        progress = dict(status='running', total=1, processed=0, succeeded=0, failed=0, errors=[])
        raw = json.dumps({'averageRating': 8, 'judges': [{'rating':8}]})
        with patch('app.services.missing_score_service.get_sync_session', return_value=session), \
             patch('app.services.missing_score_service.OpenAI'), \
             patch('app.services.missing_score_service.register_client'), \
             patch('app.services.missing_score_service.unregister_client'), \
             patch('app.services.missing_score_service.get_redis_client_sync'), \
             patch('app.services.missing_score_service.run_ai_scoring_sync', return_value=object()) as judge, \
             patch('app.services.missing_score_service.ai_score_result_to_json', return_value=raw):
            repair('t', ['r'], progress)
        judge.assert_called_once()
        self.assertEqual(judge.call_args.args[3], 'original answer')
        self.assertEqual(result.output_text, 'original answer')
        self.assertEqual(progress['succeeded'], 1)
        self.assertEqual(progress['status'], 'completed')
        self.assertEqual(judge.call_args.kwargs['extra_headers']['X-Eval-Run-Id'], 't')
