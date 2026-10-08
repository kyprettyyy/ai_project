"""Offline validation replay: reuses measured answers, never calls models or publishes profiles."""
import argparse,hashlib,json,sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/gateway'))
from app.routing.explainable_router import CandidateSignals,ExplainableRouter,RoutingContext,estimate_message_tokens,DEFAULT_WEIGHTS
MODELS=['mimo-v2.6-flash','hy3','glm-5.3-flash']
QUALITY_WEIGHTS={'quality':.60,'latency':.05,'cost':.05,'reliability':.15,'task':.10,'context':.025,'budget':.025}

def fingerprint(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()

def training_signals(rows,prices,task):
 signals=[];profiles=[]
 for index,model in enumerate(MODELS):
  items=[r for r in rows if r['split']=='train' and r['task']==task and r['model']==model]
  quality=[r['quality'] for r in items if r['quality'] is not None]
  latency=[r['latencyMs'] for r in items if r.get('latencyMs') and r['latencyMs']>0]
  costs=[r['currentCatalogAnswerEstimateCny'] for r in items if r.get('currentCatalogAnswerEstimateCny') is not None]
  if not items or not latency:raise ValueError('训练样本或延迟缺失：'+task+'/'+model)
  mean_latency=sum(latency)/len(latency);mean_cost=sum(costs)/len(costs) if len(costs)==len(items) else None
  reliability=sum(not r['empty'] for r in items)/50 # Missing training answers count against coverage, not success.
  p=prices[model]
  signal=CandidateSignals(model_id=index+1,model_key=model,context_length=int(p.get('contextLength') or 4096),
    input_price=Decimal(str(p['inputPrice'])),output_price=Decimal(str(p['outputPrice'])),
    avg_latency_ms=round(mean_latency),live_success_rate=reliability,
    priority=int(p.get('priority') or 100),quality_score=sum(quality)/len(quality) if quality else .5,
    profile_latency_score=1/(1+mean_latency/1000),profile_cost_score=1/(1+mean_cost/.01) if mean_cost is not None else .5,
    profile_reliability_score=reliability,sample_count=min(len(items),len(quality)),profile_task_type=task)
  signals.append(signal)
  profiles.append({'model':model,'task':task,'trainingAnswers':len(items),'qualitySamples':len(quality),
    'quality':signal.quality_score if quality else None,'qualityFallback':not bool(quality),
    'meanLatencyMs':mean_latency,'currentCatalogMeanAnswerEstimateCny':mean_cost,'reliability':reliability})
 return signals,profiles

def replay(rows,prices):
 if {r['model'] for r in rows} != set(MODELS):raise ValueError('候选模型集合不一致')
 training=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation']
 if len(validation)!=240:raise ValueError('验证数据需80题乘3模型')
 lookup={(r['id'],r['model']):r for r in validation}
 if len(lookup)!=240:raise ValueError('验证模型/题目重复')
 jobs={r['id']:r for r in validation};router=ExplainableRouter();records=[];all_profiles=[]
 for task in sorted({r['task'] for r in validation}):
  signals,profiles=training_signals(training,prices,task);all_profiles+=profiles
  for row in sorted((r for r in jobs.values() if r['task']==task),key=lambda r:r['id']):
   context=RoutingContext(task_type=task,estimated_input_tokens=estimate_message_tokens([row['prompt']]),expected_output_tokens=1024)
   plan=router.rank(signals,context,DEFAULT_WEIGHTS);quality_plan=router.rank(signals,context,QUALITY_WEIGHTS)
   selections={'balanced':plan.selected.model_key,'quality_first':quality_plan.selected.model_key,
      # Mirrors CostFirstRoutingStrategy's input+output catalog price ordering.
      'cost_first':min(signals,key=lambda s:(s.input_price+s.output_price,s.model_id)).model_key,
      **{'fixed:'+m:m for m in MODELS}}
   for policy,model in selections.items():
    answer=lookup[row['id'],model]
    records.append({'id':row['id'],'task':task,'policy':policy,'model':model,'quality':answer['quality'],
      'latencyMs':answer['latencyMs'],'success':not answer['empty'],
      'currentCatalogAnswerEstimateCny':answer['currentCatalogAnswerEstimateCny'],
      'sourceResultId':answer['resultId'],'ranking':plan.snapshot() if policy=='balanced' else quality_plan.snapshot() if policy=='quality_first' else None})
 summary=[]
 for task in ['all','math','classification','code','summarization']:
  for policy in selections:
   group=[r for r in records if r['policy']==policy and (task=='all' or r['task']==task)]
   quality=[r['quality'] for r in group if r['quality'] is not None];cost=[r['currentCatalogAnswerEstimateCny'] for r in group if r['currentCatalogAnswerEstimateCny'] is not None]
   summary.append({'task':task,'policy':policy,'questions':len(group),'qualitySamples':len(quality),'meanQuality':sum(quality)/len(quality) if quality else None,
      'successRate':sum(r['success'] for r in group)/len(group),'meanLatencySeconds':sum(r['latencyMs'] for r in group)/len(group)/1000,
      'currentCatalogAnswerEstimateCny':sum(cost) if len(cost)==len(group) else None,'models':dict(Counter(r['model'] for r in group))})
 return {'method':'OFFLINE_REPLAY_NOT_LIVE_GATEWAY','trainingHash':fingerprint(training),'validationHash':fingerprint(validation),
  'catalogPrices':prices,'weights':{'balanced':DEFAULT_WEIGHTS,'quality_first':QUALITY_WEIGHTS},
  'profiles':all_profiles,'summary':summary,'records':records,
  'limitations':['No new model calls; no gateway overhead or fallback measurement',
     'Incomplete AI scores; compare quality only on matched scored questions',
     'Catalog estimates at current configured prices, not historical billed cost; judge costs excluded',
     'Missing training AI scores use neutral prior; experimental rankings are provisional',
     'Historical answer generation parameters were not normalized; replay is exploratory only',
     'Task type determined from dataset, not user-entered general label; no profiles published']}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--audit',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 result=replay(json.loads(args.input.read_text()),json.loads(args.audit.read_text())['prices']);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['summary'],ensure_ascii=False))
