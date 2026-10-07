import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.scoring.profile_scoring import build_profiles
class CoverageTest(unittest.TestCase):
 def test_missing_cost_not_free_and_quality_coverage(self):
  rows=[{'model_name':'a','output_text':'answer','user_rating':5,'latency':100,'cost':None,'cost_currency':'UNKNOWN'},
        {'model_name':'a','output_text':'','latency':None,'cost':0,'cost_currency':'UNKNOWN'}]
  p=build_profiles(rows,'run')[0]
  self.assertEqual(p['cost_score'],.5)
  self.assertFalse(p['coverage']['costComplete'])
  self.assertEqual(p['coverage']['ratedSamples'],1)
  self.assertEqual(p['coverage']['emptySamples'],1)
  self.assertEqual(p['reliability_score'],.5)
 def test_mixed_currency_and_cross_task_not_compared(self):
  rows=[{'model_name':'a','output_text':'ok','cost':1,'cost_currency':'CNY','task_config':{'taskType':'code'}},
        {'model_name':'a','output_text':'ok','cost':1,'cost_currency':'USD','task_config':{'taskType':'code'}},
        {'model_name':'b','output_text':'ok','cost':100,'cost_currency':'CNY','task_config':{'taskType':'math'}}]
  profiles={p['model']:p for p in build_profiles(rows,'run')}
  self.assertFalse(profiles['a']['coverage']['costComplete'])
  self.assertEqual(profiles['b']['cost_score'],.5)
  self.assertFalse(profiles['b']['coverage']['costComparable'])
