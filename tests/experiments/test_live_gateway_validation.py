import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments'))
from run_gateway_validation import score_exact, price, summarize, POLICIES
class LiveValidationTest(unittest.TestCase):
 def test_numeric_format_and_tolerance(self):
  gold={'task_type':'math','numeric_answer':51,'absolute_tolerance':1e-6}
  self.assertEqual(score_exact('51.0000005',gold),1)
  self.assertEqual(score_exact('答案是51',gold),0)
 def test_unknown_code_quality_is_not_assumed_correct(self):
  self.assertIsNone(score_exact('def f(): pass',{'task_type':'code'}))
  self.assertEqual(score_exact('',{'task_type':'code'}),0)
 def test_per_thousand_price(self):
  state={'models':[{'modelKey':'m','inputPrice':'0.001','outputPrice':'0.004'}]}
  self.assertAlmostEqual(price({'model':'m','usage':{'promptTokens':1000,'completionTokens':1000}},state),.005)
  self.assertIsNone(price({'model':'m','usage':{}},state))
 def test_summary_marks_incomplete_quality(self):
  result=summarize([{'policy':'balanced','success':True,'latencyMs':100,'quality':None,'model':'hy3'}])['balanced']
  self.assertEqual(result['qualityCoverage'],0)
  self.assertIsNone(result['meanQuality'])
 def test_three_fixed_baselines(self):
  self.assertEqual(len(POLICIES),6)
  self.assertEqual(len([x for x in POLICIES if x.startswith('fixed:')]),3)
