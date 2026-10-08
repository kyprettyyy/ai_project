"""Run an untouched test set using the existing frozen validation configuration."""
import argparse,json,sys
from pathlib import Path
from decimal import Decimal
from collections import Counter
import run_gateway_validation as experiment

def read_test_inputs(folder):
 rows=[]
 for file in sorted(folder.glob('*.json')):
  for item in json.loads(file.read_text()):
   gold=json.loads(item['expectedOutput'])
   if gold.get('split')!='test':raise ValueError('测试集不得混入训练或验证数据')
   rows.append({'id':gold['id'],'task':gold['task_type'],'prompt':item['content'],'gold':gold})
 if len(rows)!=120 or Counter(r['task'] for r in rows)!=Counter({t:30 for t in experiment.TASKS}):raise ValueError('测试集必须四类各30题')
 if len({r['id'] for r in rows})!=120:raise ValueError('测试题ID重复')
 return rows

def verify_frozen_state(state,frozen):
 if not frozen.get('profilesPublished') or not frozen.get('partialScoringAccepted'):raise ValueError('缺少已批准的当前评分冻结画像')
 if frozen['selectedPolicy']!='balanced':raise ValueError('脚本只执行本轮选定的均衡策略')
 for model in state['models']:
  saved=frozen['catalogPrices'].get(model['modelKey'])
  if saved is None:raise ValueError('候选模型变更')
  for key in ('inputPrice','outputPrice','contextLength','priority'):
   if Decimal(str(model[key]))!=Decimal(str(saved[key])):raise ValueError('冻结目录价格或模型配置变更')
  if model['priceCurrency']!=saved['priceCurrency']:raise ValueError('计价币种变更')
 profiles={(p['modelKey'],p['taskType']):p for p in state['profiles']}
 for saved in frozen['publishedProfiles']:
  current=profiles.get((saved['model'],saved['taskType']))
  if current is None:raise ValueError('冻结画像缺失')
  for key in ('qualityScore','latencyScore','costScore','reliabilityScore','sampleCount','profileVersion'):
   if Decimal(str(current[key]))!=Decimal(str(saved[key])):raise ValueError('画像分数或版本已改变，停止测试')
  if current['evaluationRunId']!=saved['evaluationRunId']:raise ValueError('训练来源版本变更')
 return state

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--frozen',type=Path,required=True);args,remaining=p.parse_known_args()
 frozen=json.loads(args.frozen.read_text());snapshot=args.frozen.parent
 for name,digest in frozen['fileHashes'].items():
  import hashlib
  if hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=digest:raise ValueError('原训练/验证冻结数据被修改')
 original_state=experiment.frozen_state
 experiment.frozen_state=lambda:verify_frozen_state(original_state(allow_partial=True),frozen)
 experiment.read_inputs=read_test_inputs
 experiment.POLICIES={'balanced':frozen['routingRequest'],**{'fixed:'+m:{'model':m,'routing_strategy':'fixed'} for m in experiment.MODELS}}
 experiment.EXPERIMENT_SPLIT='test';experiment.SOURCE_FREEZE_HASH=experiment.digest(frozen)
 sys.argv=[sys.argv[0],*remaining];experiment.main()
