import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments'))
from replay_validation_matrix import training_signals,MODELS
class TrainingIsolationTests(unittest.TestCase):
 def test_validation_scores_cannot_change_training_profile(self):
  prices={m:{'inputPrice':'.001','outputPrice':'.002','priceCurrency':'CNY'} for m in MODELS}
  rows=[{'split':'train','task':'math','model':m,'quality':.9,'latencyMs':1000,'currentCatalogAnswerEstimateCny':.001,'empty':False} for m in MODELS]
  before=training_signals(rows,prices,'math')[1]
  polluted=rows+[{'split':'validation','task':'math','model':m,'quality':0,'latencyMs':99999,'currentCatalogAnswerEstimateCny':999,'empty':True} for m in MODELS]
  self.assertEqual(before,training_signals(polluted,prices,'math')[1])
 def test_missing_quality_is_explicit_and_not_full_credit(self):
  prices={m:{'inputPrice':'.001','outputPrice':'.002'} for m in MODELS}
  rows=[{'split':'train','task':'code','model':m,'quality':None,'latencyMs':1000,'currentCatalogAnswerEstimateCny':None,'empty':False} for m in MODELS]
  signals,profiles=training_signals(rows,prices,'code')
  self.assertTrue(all(p['qualityFallback'] and p['quality'] is None for p in profiles))
  self.assertTrue(all(s.sample_count==0 for s in signals))
