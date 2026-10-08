import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments'))
from run_gateway_test import read_test_inputs,verify_frozen_state
class TestSetIsolationTests(unittest.TestCase):
 def test_rejects_validation_as_test(self):
  with tempfile.TemporaryDirectory() as directory:
   Path(directory,'data.json').write_text(json.dumps([{'content':'q','expectedOutput':json.dumps({'split':'validation','task_type':'math','id':'q'})}]))
   with self.assertRaises(ValueError):read_test_inputs(Path(directory))
 def test_rejects_unpublished_profiles(self):
  with self.assertRaises(ValueError):verify_frozen_state({}, {'profilesPublished':False})
