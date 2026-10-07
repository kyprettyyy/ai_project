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
