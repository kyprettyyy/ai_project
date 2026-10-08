import unittest
from app.services.ai_scoring_service import _parse_evaluation_result
class ScoringFormatTests(unittest.TestCase):
 def test_prose_wrapped_score_preserves_fractional_rating(self):
  raw='评分如下： {"scores":{"accuracy":30},"total_score":85,"rating":8.5,"comment":"ok"} 说明完毕'
  score=_parse_evaluation_result(raw)
  self.assertIsNotNone(score)
  self.assertEqual(score.rating,8.5)
  self.assertEqual(score.total_score,85)
 def test_truncated_and_empty_payloads_do_not_become_zero_scores(self):
  for raw in ('{}','{"scores":{}}','{"scores":{"accuracy":30},"total_score":85,"rating":','{"scores":{},"total_score":100,"rating":11}'):
   self.assertIsNone(_parse_evaluation_result(raw))
 def test_camel_case_and_fenced_score(self):
  score=_parse_evaluation_result('```json\n{"scores":{"accuracy":30},"totalScore":90,"rating":9}\n```')
  self.assertEqual(score.total_score,90)
