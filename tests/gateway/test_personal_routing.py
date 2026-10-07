import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.services.personal_routing_service import feedback_for_user,preference_weights
from app.routing.explainable_router import normalize_weights

class PersonalRoutingTest(unittest.TestCase):
 def test_own_batch_preferred_and_sparse_feedback_falls_back(self):
  shared={(1,'code'):SimpleNamespace(sample_count=50,positive_count=25)}
  own={(1,'code'):SimpleNamespace(sample_count=30,positive_count=30)}
  self.assertEqual(feedback_for_user(shared,own,1,'code')[1],'个人反馈')
  self.assertEqual(feedback_for_user(shared,{},1,'code')[0].positive_count,25)
  own[(1,'code')].sample_count=29
  self.assertEqual(feedback_for_user(shared,own,1,'code')[1],'共享反馈')
 def test_explicit_preferences_change_only_requested_weight(self):
  base=normalize_weights(preference_weights('balanced'))
  for mode in ['quality','cost','latency']:
   weights=normalize_weights(preference_weights(mode))
   self.assertGreater(weights[mode],base[mode]);self.assertAlmostEqual(sum(weights.values()),1)
