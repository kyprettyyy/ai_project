from unittest import TestCase
from unittest.mock import Mock, patch
from app.services.ai_scoring_service import _select_judge_models_sync, run_ai_scoring_sync


class JudgeCatalogTest(TestCase):
    def test_catalog_models_are_not_filtered_by_region_and_exclude_self(self):
        session = Mock()
        session.execute.return_value.fetchall.return_value = [('glm-5.3-flash',), ('mimo-v2.6-flash',), ('hy3',)]
        self.assertEqual(_select_judge_models_sync(session, 'hy3'), ['glm-5.3-flash', 'mimo-v2.6-flash'])
        statement = str(session.execute.call_args.args[0])
        self.assertNotIn('isChina', statement)

    def test_empty_catalog_does_not_call_obsolete_default(self):
        session, client = Mock(), Mock()
        with patch('app.services.ai_scoring_service._select_judge_models_sync', return_value=[]):
            self.assertIsNone(run_ai_scoring_sync(session, client, 'question', 'answer', 'hy3'))
        client.chat.completions.create.assert_not_called()
