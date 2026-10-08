import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.advance_validation import training_profiles,TRAINING_IDS,MODELS
class TrainingPublicationTests(unittest.TestCase):
 def rows(self):
  return [{'split':'train','task':t,'model':m,'taskId':tid,'quality':.8,'latencyMs':1000,
    'currentCatalogAnswerEstimateCny':.001,'empty':False,'resultId':f'{t}-{m}-{i}'}
    for t,tid in TRAINING_IDS.items() for m in MODELS for i in range(30)]
 def test_training_only_sources_and_no_validation_leakage(self):
  prices={m:{'priceCurrency':'CNY'} for m in MODELS};rows=self.rows()
  first=training_profiles(rows,prices)
  rows.append({'split':'validation','quality':0})
  second=training_profiles(rows,prices)
  self.assertEqual([p['quality_score'] for p in first[0]],[p['quality_score'] for p in second[0]])
  self.assertTrue(all(p['evaluation_run_id'].startswith('train-only-') for p in second[0]))
 def test_missing_training_scores_block_publication(self):
  rows=self.rows();rows[0]['quality']=None
  with self.assertRaises(ValueError):training_profiles(rows,{m:{'priceCurrency':'CNY'} for m in MODELS})
 def test_wrong_task_source_blocks_publication(self):
  rows=self.rows();rows[0]['taskId']='validation-id'
  with self.assertRaises(ValueError):training_profiles(rows,{m:{'priceCurrency':'CNY'} for m in MODELS})
 def test_explicit_partial_mode_uses_neutral_unknown_not_full_credit(self):
  rows=self.rows()
  for row in rows:
   if row['task']=='summarization':row['quality']=None
  profiles,_=training_profiles(rows,{m:{'priceCurrency':'CNY'} for m in MODELS},allow_partial=True)
  summary=[p for p in profiles if p['task_type']=='summarization']
  self.assertTrue(all(p['quality_score']==.5 and p['sample_count']==0 and p['coverage']['qualityUnknown'] for p in summary))
