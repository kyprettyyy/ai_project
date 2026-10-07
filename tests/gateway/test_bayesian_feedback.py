import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.routing.bayesian_feedback import estimate_feedback,published_prior

class BayesianFeedbackTest(unittest.TestCase):
 def test_no_feedback_no_influence(self):
  e=estimate_feedback(0,0);self.assertEqual(e['posteriorMean'],.5);self.assertEqual(e['routingWeight'],0)
 def test_extremes_are_smoothed(self):
  self.assertAlmostEqual(estimate_feedback(30,30)['posteriorMean'],31/32)
  self.assertAlmostEqual(estimate_feedback(0,30)['posteriorMean'],1/32)
 def test_published_batch_weight_grows_but_is_capped(self):
  self.assertEqual(estimate_feedback(29,29)['routingWeight'],0)
  self.assertAlmostEqual(estimate_feedback(15,30)['routingWeight'],.1)
  self.assertLess(estimate_feedback(300,300)['routingWeight'],.2)
  self.assertGreater(estimate_feedback(150,300)['routingWeight'],.1)
 def test_uncertainty_decreases_with_more_evidence(self):
  self.assertLess(estimate_feedback(150,300)['posteriorStdDev'],estimate_feedback(15,30)['posteriorStdDev'])
 def test_other_user_prior_bounded_and_personal_evidence_dominates(self):
  mean,strength=published_prior(800,1000);self.assertEqual(strength,20)
  early=estimate_feedback(0,30,mean,strength)['posteriorMean']
  later=estimate_feedback(0,300,mean,strength)['posteriorMean']
  self.assertLess(later,early);self.assertLess(later,.1)
  self.assertTrue(estimate_feedback(0,30,mean,strength)['priorConflict'])
  self.assertEqual(estimate_feedback(0,30,mean,strength)['priorStrength'],2.)
 def test_invalid_counts_rejected(self):
  for positive,samples in [(31,30),(-1,30),(0,-1)]:
   with self.assertRaises(ValueError):estimate_feedback(positive,samples)
