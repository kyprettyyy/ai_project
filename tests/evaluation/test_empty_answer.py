import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/evaluation'))
from app.services.batch_test_worker import run_subtask_sync
from app.models.test_result import TestResult

class EmptyAnswerTest(unittest.TestCase):
    def test_empty_response_is_saved_and_progress_committed(self):
        task = SimpleNamespace(status='running', config='{}', completed_subtasks=1, total_subtasks=2)
        task_result = MagicMock(); task_result.scalar_one_or_none.return_value = task
        no_model = MagicMock(); no_model.scalar_one_or_none.return_value = None
        session = MagicMock()
        session.execute.side_effect = [task_result, no_model, MagicMock(), MagicMock(), task_result]
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            model='model', choices=[SimpleNamespace(message=SimpleNamespace(content=''))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0))
        with patch('app.services.batch_test_worker.get_sync_session', return_value=session), \
             patch('app.services.batch_test_worker.OpenAI', return_value=client), \
             patch('app.services.batch_test_worker.get_redis_client_sync', return_value=None):
            result = run_subtask_sync({'taskId':'batch','modelName':'model','promptContent':'test','userId':0})
        stored = session.add.call_args.args[0]
        self.assertIsInstance(stored, TestResult)
        self.assertEqual(stored.output_text, '')
        self.assertEqual(stored.input_tokens, 10)
        self.assertIsNone(stored.ai_score)
        self.assertIn('resultId', result)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    def test_fallback_or_missing_model_is_not_saved(self):
        for actual in ('deepseek', None):
            with self.subTest(actual=actual):
                task = SimpleNamespace(status='running', config='{}')
                session = MagicMock()
                session.execute.return_value.scalar_one_or_none.return_value = task
                client = MagicMock()
                client.chat.completions.create.return_value = SimpleNamespace(model=actual)
                with patch('app.services.batch_test_worker.get_sync_session', return_value=session), \
                     patch('app.services.batch_test_worker.OpenAI', return_value=client), \
                     patch('app.services.batch_test_worker.get_redis_client_sync', return_value=None):
                    with self.assertRaisesRegex(RuntimeError, '测评模型不匹配'):
                        run_subtask_sync({'taskId':'batch','modelName':'kimi','promptContent':'test','userId':0})
                session.add.assert_not_called()
