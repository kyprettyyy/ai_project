import sys, unittest, json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.services.report_service import ReportService

class ReportDimensionsTest(unittest.TestCase):
    def test_separate_dimensions_empty_zero_and_missing_excluded(self):
        rows=[SimpleNamespace(model_name='m',output_text='answer',ai_score=json.dumps({'averageRating':9,'judges':[{'scores':{'accuracy':30,'completeness':10}},{'scores':{'accuracy':15,'completeness':20}}]})),
              SimpleNamespace(model_name='m',output_text='',ai_score=None),
              SimpleNamespace(model_name='m',output_text='ungraded',ai_score=None)]
        self.assertEqual(ReportService._dimension_average(rows,'m','accuracy',30),37.5)
        self.assertEqual(ReportService._dimension_average(rows,'m','completeness',20),37.5)
    def test_zero_score_is_preserved(self):
        rows=[SimpleNamespace(model_name='m',output_text='answer',ai_score=json.dumps({'judges':[{'scores':{'accuracy':0}}]}))]
        self.assertEqual(ReportService._dimension_average(rows,'m','accuracy',30),0)

    def test_missing_scores_are_not_zero(self):
        rows=[SimpleNamespace(model_name='m',output_text='answer',ai_score=None)]
        self.assertIsNone(ReportService._dimension_average(rows,'m','accuracy',30))
    def test_relative_speed_and_unknown_cost(self):
        stats=[SimpleNamespace(model_name='fast',avg_response_time_ms=5000,avg_cost=None,cost_currency='UNKNOWN',avg_user_rating=None),
               SimpleNamespace(model_name='slow',avg_response_time_ms=10000,avg_cost=None,cost_currency='UNKNOWN',avg_user_rating=None)]
        result=ReportService._generate_radar_chart([],stats)
        self.assertEqual(result.series[0].values[2],100)
        self.assertEqual(result.series[1].values[2],50)
        self.assertIsNone(result.series[0].values[3])
        self.assertIsNone(result.series[0].values[4])
    def test_single_model_has_no_relative_scores(self):
        stats=[SimpleNamespace(model_name='only',avg_response_time_ms=5000,avg_cost=.01,cost_currency='CNY',avg_user_rating=None)]
        result=ReportService._generate_radar_chart([],stats)
        self.assertIsNone(result.series[0].values[2])
        self.assertIsNone(result.series[0].values[3])
