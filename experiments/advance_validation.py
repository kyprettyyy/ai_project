"""One-shot local workflow: wait for scoring, publish audited train-only profiles, run validation only."""
import argparse,fcntl,json,os,sys,time,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services/evaluation')]
from dotenv import dotenv_values
import pymysql,httpx
from experiments.run_gateway_validation import MODELS,VALIDATION_IDS,digest
TRAINING_IDS={'math':'e66b42fa-2859-498a-a0f7-6ba3b6e04fc6','classification':'f7bbbda2-4b71-4a52-b397-090263db6ebe','code':'518a98b0-48fc-4a9b-a6e4-a84466f50792','summarization':'9289069f-beed-4850-8e21-19ca80188c39'}

def connect(e):
 return pymysql.connect(host=e['DB_HOST'],port=int(e['DB_PORT']),user=e['DB_USER'],password=e['DB_PASSWORD'],database=e['DB_NAME'],cursorclass=pymysql.cursors.DictCursor)

def state(output,stage,**extra):
 value={'stage':stage,'updatedAt':datetime.now(timezone.utc).isoformat(),**extra}
 temp=output/'workflow-state.tmp';temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));temp.replace(output/'workflow-state.json')
 labels={'waiting_for_existing_scores':'等待已有补评分完成','training_profiles_verified':'训练画像来源已核验','checking_live_smoke':'正在做小样本联通检查','running_live_validation':'正在运行正式验证集对比','validation_complete_configuration_frozen':'验证完成，测试配置已冻结','blocked':'流程暂停，需要检查'}
 lines=['# 验证集实验进度','',labels.get(stage,stage),'',f'更新时间：{value["updatedAt"]}','']
 if 'jobs' in extra:
  lines+=['| 任务 | 已处理 | 总数 | 失败 |','|---|---:|---:|---:|']
  for job in extra['jobs']:lines.append(f'| {job["name"]} | {job["processed"]} | {job["total"]} | {job["failed"]} |')
 if extra.get('reason'):lines.append('原因：'+extra['reason'])
 if extra.get('selectedPolicy'):lines.append('选定策略：'+extra['selectedPolicy'])
 lines+=['','流程：等待补评分 → 核验训练专用画像 → 6次联通检查 → 6种策略正式验证对比 → 保存冻结配置。','测试集不会在此流程中调用。']
 (output/'实验进度.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(value,ensure_ascii=False),flush=True)

def training_profiles(records,prices, *, allow_partial=False):
 profiles=[];snapshot=[];run_id='train-only-'+digest([r for r in records if r['split']=='train'])[:48]
 for task in TRAINING_IDS:
  for model in MODELS:
   items=[r for r in records if r['split']=='train' and r['task']==task and r['model']==model]
   if any(r['taskId']!=TRAINING_IDS[task] for r in items):raise ValueError('训练结果来源任务不一致')
   scores=[r['quality'] for r in items if r['quality'] is not None]
   if len(items)<30 or (len(scores)<30 and not allow_partial):raise ValueError(f'{task}/{model} 有效训练评分不足30条（{len(scores)}），不发布画像')
   latencies=[r['latencyMs'] for r in items if r['latencyMs'] and r['latencyMs']>0]
   costs=[r['currentCatalogAnswerEstimateCny'] for r in items if r['currentCatalogAnswerEstimateCny'] is not None]
   if len(latencies)!=len(items) or len(costs)!=len(items):raise ValueError('训练成本或延迟覆盖不足')
   if prices[model]['priceCurrency']!='CNY':raise ValueError('训练价格不是人民币')
   latency=sum(latencies)/len(latencies);cost=sum(costs)/len(costs)
   profiles.append({'model':model,'task_type':task,'quality_score':round(sum(scores)/len(scores),4) if scores else .5,
     'latency_score':round(1/(1+latency/1000),4),'cost_score':round(1/(1+cost/.01),4),
     'reliability_score':round(sum(not r['empty'] for r in items)/50,4),'sample_count':len(scores),
     'evaluation_run_id':run_id,'evaluated_at':datetime.now(timezone.utc).isoformat(),
     'coverage':{'ratedSamples':len(scores),'emptySamples':sum(r['empty'] for r in items),
       'qualityUnknown':not bool(scores),'smallQualitySample':len(scores)<30,'partialScoringAccepted':allow_partial,'missingAnswers':50-len(items),'latencySamples':len(latencies),'costSamples':len(costs),
       'costCurrency':'CNY','costSource':'current configured catalog estimate; answer only',
       'sourceTaskId':TRAINING_IDS[task],'split':'train'}})
   snapshot.append({'task':task,'model':model,'resultIds':[r['resultId'] for r in items]})
 return profiles,snapshot

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--run',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 with (a.output/'workflow.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('该验证流程已在运行，不重复调用')
  e=dotenv_values(ROOT/'services/evaluation/.env')
  if str(e.get('PROFILE_AUTO_UPDATE_ENABLED')).lower()!='false':raise ValueError('必须关闭画像自动更新')
  for attempt in range(480):
   c=connect(e)
   try:
    with c.cursor() as cur:
     ids=list(TRAINING_IDS.values())+list(VALIDATION_IDS.values())
     cur.execute('SELECT id,name,config,isDelete FROM test_task WHERE id IN ('+','.join(['%s']*len(ids))+')',ids);tasks=cur.fetchall()
   finally:c.close()
   if len(tasks)!=8 or any(t['isDelete'] for t in tasks):raise ValueError('实验来源任务已删除或缺失，停止')
   running=[]
   for task in tasks:
    progress=json.loads(task['config'] or '{}').get('aiScoringProgress',{})
    if progress.get('status')=='running':running.append({'name':task['name'],'processed':progress.get('processed',0),'total':progress.get('total',0),'failed':progress.get('failed',0)})
   if not running:break
   state(a.output,'waiting_for_existing_scores',jobs=running)
   if not a.run:return
   time.sleep(15)
  else:raise RuntimeError('补评分等待超过2小时；未发布画像或执行新实验')
  subprocess.run([sys.executable,str(ROOT/'.runtime/prepare_validation_results.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
  records=json.loads((a.output/'audited_answers.json').read_text());audit=json.loads((a.output/'audited_summary.json').read_text())
  # Primary validation outcomes must have sufficient coverage before more paid calls.
  for task in ('code','summarization'):
   for model in MODELS:
    rs=[r for r in records if r['split']=='validation' and r['task']==task and r['model']==model]
    if len(rs)!=20 or sum(r['quality'] is not None for r in rs)<18:
     raise ValueError(f'验证 {task}/{model} 评分覆盖不足90%，先修复缺分；不启动重复回答实验')
  profiles,sources=training_profiles(records,audit['prices'])
  (a.output/'train_only_profiles.json').write_text(json.dumps({'profiles':profiles,'sources':sources,'prices':audit['prices']},ensure_ascii=False,default=str,indent=2))
  state(a.output,'training_profiles_verified',profiles=len(profiles))
  if not a.run:return
  base=e['GATEWAY_BASE_URL'].rstrip('/');headers={'X-Internal-Token':e['GATEWAY_INTERNAL_TOKEN']}
  with httpx.Client(timeout=30) as client:
   old=client.get(base+'/internal/model-profiles',headers=headers);old.raise_for_status()
   backup=a.output/'profiles_before_train_only.json'
   if not backup.exists():backup.write_text(json.dumps(old.json(),ensure_ascii=False,indent=2))
   response=client.put(base+'/internal/model-profiles',headers=headers,json={'profiles':profiles});response.raise_for_status();accepted=response.json()
   if accepted.get('updated',0)+accepted.get('unchanged',0)!=12:raise ValueError('训练画像发布不完整，停止')
  state(a.output,'checking_live_smoke',profilesPublished=12)
  subprocess.run([sys.executable,str(ROOT/'experiments/run_gateway_validation.py'),'--dataset',str(a.dataset),'--output',str(a.output/'live_smoke'),'--run','--limit','6'],cwd=ROOT,check=True)
  smoke=json.loads((a.output/'live_smoke/summary.json').read_text())
  if sum(x['requests'] for x in smoke['results'].values())!=6 or any(x['successRate']!=1 or x['qualityCoverage']!=1 for x in smoke['results'].values()):
   raise ValueError('小样本联通或评分检查未全部通过，不启动完整收费实验')
  state(a.output,'running_live_validation',profilesPublished=12,answerCalls=480,maxJudgeCalls=480)
  subprocess.run([sys.executable,str(ROOT/'experiments/run_gateway_validation.py'),'--dataset',str(a.dataset),'--output',str(a.output/'live'),'--run','--concurrency','3'],cwd=ROOT,check=True)
  summary=json.loads((a.output/'live/summary.json').read_text())
  if not summary['complete']:raise ValueError('正式验证实验未完成')
  eligible={name:result for name,result in summary['results'].items() if result['qualityCoverage']>=.95 and result['successRate']>=.98 and result['pricedAnswers']==80}
  if not eligible:raise ValueError('没有满足评分覆盖、成功率和费用覆盖要求的策略，暂不冻结测试配置')
  best=max(result['meanQuality'] for result in eligible.values())
  choices={name:r for name,r in eligible.items() if r['meanQuality']>=best-.02}
  selected=min(choices,key=lambda name:(choices[name]['answerCostCny'],choices[name]['meanLatencyMs']))
  manifest=json.loads((a.output/'live/manifest.json').read_text())
  frozen={'selectedPolicy':selected,'selectionRule':'quality coverage >=95%, success >=98%, full answer cost coverage; within 2pp of best normalized quality, minimize answer catalog cost, then latency',
   'validationResults':summary['results'],'manifest':manifest,'testSetTouched':False,'autoUpdate':False}
  (a.output/'frozen_for_test.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2))
  state(a.output,'validation_complete_configuration_frozen',selectedPolicy=selected,summary=str(a.output/'live/summary.json'),testSetTouched=False)

if __name__=='__main__':
 args_output=None
 try:main()
 except Exception as error:
  # Do not expose credentials or server payloads in the persisted error.
  try:
   idx=sys.argv.index('--output');folder=Path(sys.argv[idx+1]);folder.mkdir(parents=True,exist_ok=True)
   state(folder,'blocked',errorType=type(error).__name__,reason=str(error)[:500])
  finally:raise
