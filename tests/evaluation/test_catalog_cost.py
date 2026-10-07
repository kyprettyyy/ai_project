import sys,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.utils.catalog_cost import estimate_cost
from app.services.report_service import ReportService
class CostTests(unittest.TestCase):
 def test_units_and_unknown(self):
  self.assertEqual(float(estimate_cost(1000000,1000000,20,100,'CNY')[0]),120)
  self.assertIsNone(estimate_cost(10,10,0,0,'CNY')[0])
 def test_offpeak_boundary(self):
  policy={'offPeak':{'input':1,'output':4}}
  for hour,expected in [(7,5),(8,10),(21,10),(22,5)]:
   self.assertEqual(float(estimate_cost(1000000,1000000,2,8,'CNY',policy,datetime(2026,10,6,hour,tzinfo=ZoneInfo('Asia/Shanghai')))[0]),expected)
 def test_historical_judge_is_unknown_and_mixed_not_summed(self):
  row=SimpleNamespace(cost=2,cost_currency='CNY',ai_score='{}',output_text='answer',response_time_ms=1,input_tokens=1,output_tokens=2,model_name='a')
  summary=ReportService._calculate_summary([row])
  self.assertIsNone(summary.total_cost);self.assertIsNone(summary.judge_cost);self.assertEqual(summary.known_cost,2)
  summary=ReportService._calculate_summary([row],{'callCount':1,'totalsByCurrency':{'CNY':3},'tokens':4})
  self.assertEqual(summary.total_cost,5)
  other=SimpleNamespace(**{**vars(row),'cost_currency':'USD'})
  self.assertIsNone(ReportService._calculate_summary([row,other]).known_cost)
