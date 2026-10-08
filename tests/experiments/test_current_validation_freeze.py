import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments'))
from freeze_current_validation import choose
class MatchedQuestionSelectionTests(unittest.TestCase):
 def test_unmatched_score_cannot_boost_policy(self):
  def row(q,p,quality,cost):
   return {'id':q,'policy':p,'quality':quality,'task':'math','success':True,'latencyMs':1000,'currentCatalogAnswerEstimateCny':cost,'model':p}
  records=[row('q1','a',.9,2),row('q2','a',None,2),row('q1','b',.85,1),row('q2','b',1,1)]
  selected,_,common,_=choose({'records':records})
  self.assertEqual(common,['q1']);self.assertEqual(selected['policy'],'a')
  records[-1]['quality']=0
  self.assertEqual(choose({'records':records})[0]['policy'],'a')
 def test_no_common_scores_is_not_reported_as_zero_quality(self):
  row={'id':'q1','policy':'a','quality':None}
  with self.assertRaises(ValueError):choose({'records':[row]})
