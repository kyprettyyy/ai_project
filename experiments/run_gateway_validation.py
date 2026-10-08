"""Live, resumable gateway comparison. Defaults to free preflight, never a paid run."""
from __future__ import annotations
import argparse, hashlib, json, os, random, re, sys, time, uuid
from decimal import Decimal
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_SPLIT = 'validation'
SOURCE_FREEZE_HASH = None
MODELS = ['mimo-v2.6-flash', 'hy3', 'glm-5.3-flash']
TASKS = ['code', 'classification', 'math', 'summarization']
VALIDATION_IDS = {
    'math': 'bfd76ebb-a315-43f8-9393-2d4f778071fb',
    'classification': '6d626a6d-68e5-4673-bde5-7c07819db9c2',
    'code': 'ecd947d9-5402-4ef6-9538-dcb6acf05df3',
    'summarization': '89560001-8a48-4ade-833b-696e662d63ed',
}
POLICIES = {
    'balanced': {'routing_strategy': 'auto', 'routing_weights': {'quality':.30,'latency':.15,'cost':.15,'reliability':.15,'task':.10,'context':.075,'budget':.075}},
    'quality_first': {'routing_strategy': 'auto', 'routing_weights':
        {'quality': .60, 'latency': .05, 'cost': .05, 'reliability': .15, 'task': .10, 'context': .025, 'budget': .025}},
    'cost_first': {'routing_strategy': 'cost_first'},
    **{'fixed:'+m: {'model': m, 'routing_strategy': 'fixed'} for m in MODELS},
}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

def read_inputs(folder):
    rows = []
    for file in sorted(folder.glob('*.json')):
        for item in json.loads(file.read_text()):
            gold = json.loads(item['expectedOutput'])
            if gold['split'] != 'validation': raise ValueError('只允许验证集，拒绝混入训练集或测试集')
            rows.append({'id': gold['id'], 'task': gold['task_type'], 'prompt': item['content'], 'gold': gold})
    if len(rows) != 80 or Counter(r['task'] for r in rows) != Counter({t:20 for t in TASKS}):
        raise ValueError('验证集必须包含四类各20题，共80题')
    if len({r['id'] for r in rows}) != 80: raise ValueError('题目ID重复')
    return rows

def frozen_state(*, allow_partial=False):
    from dotenv import dotenv_values
    import pymysql
    ee = dotenv_values(ROOT/'services/evaluation/.env')
    if str(ee.get('PROFILE_AUTO_UPDATE_ENABLED','')).lower() != 'false':
        raise ValueError('请先关闭 PROFILE_AUTO_UPDATE_ENABLED')
    ge = dotenv_values(ROOT/'services/gateway/.env')
    connection = pymysql.connect(host=ge['MYSQL_HOST'],port=int(ge['MYSQL_PORT']),user=ge['MYSQL_USER'],password=ge['MYSQL_PASSWORD'],database=ge['MYSQL_DB'],cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id,modelKey,providerId,modelType,inputPrice,outputPrice,priceCurrency,pricingConfig,contextLength,priority FROM model WHERE isDelete=0 AND status='active' ORDER BY modelKey")
            models=cursor.fetchall()
            if {m['modelKey'] for m in models} != set(MODELS):
                raise ValueError('启用模型必须恰好为三个候选模型，避免路由选到集合之外的模型')
            for m in models:
                if m['modelType'] != 'chat' or m['priceCurrency'] != 'CNY' or float(m['inputPrice'])<=0 or float(m['outputPrice'])<=0:
                    raise ValueError(m['modelKey']+' 缺少正数人民币输入/输出单价（元/千Token）')
                if m['pricingConfig']: raise ValueError('此脚本暂不支持分时/阶梯价格，请先实现对应计价规则')
            cursor.execute('SELECT * FROM model_capability_profile ORDER BY modelKey,taskType')
            profiles=[p for p in cursor.fetchall() if p['modelKey'] in MODELS and p['taskType'] in TASKS]
            pairs={(p['modelKey'],p['taskType']) for p in profiles if allow_partial or p['sampleCount']>=30}
            if pairs != {(m,t) for m in MODELS for t in TASKS}:
                raise ValueError('每个候选模型在四类任务上都需至少30条训练样本画像')
            if any(not str(p['evaluationRunId'] or '').startswith('train-only-') for p in profiles):
                raise ValueError('当前画像没有训练集专用来源标记，请先建立经核验的 train-only 画像，不能使用混合历史聚合画像')
            if any(p['evaluationRunId'] in VALIDATION_IDS.values() for p in profiles):
                raise ValueError('当前画像包含验证任务来源，不能直接用作训练画像')
            provider_ids=sorted({m['providerId'] for m in models})
            cursor.execute('SELECT id,providerName,baseUrl,status FROM model_provider WHERE id IN ('+','.join(['%s']*len(provider_ids))+') ORDER BY id',provider_ids)
            providers=cursor.fetchall()
        return json.loads(json.dumps({'models':models,'profiles':profiles,'providers':providers},default=str))
    finally: connection.close()

def score_exact(output, gold):
    if not output.strip(): return 0.0
    if gold['task_type']=='classification': return float(output.strip()==str(gold['reference_answer']).strip())
    if gold['task_type']=='math':
        try:
            # Extra prose is a format violation, even when it contains a correct number.
            return float(abs(Decimal(output.strip())-Decimal(str(gold['numeric_answer'])))<=Decimal(str(gold.get('absolute_tolerance',1e-6))))
        except Exception: return 0.0
    return None

def usage_tokens(response):
    u=response.get('usage') or {}
    return int(u.get('prompt_tokens',u.get('promptTokens',0))),int(u.get('completion_tokens',u.get('completionTokens',0)))

def price(response, state):
    inp,out=usage_tokens(response)
    if not (inp+out): return None
    m=next((x for x in state['models'] if x['modelKey']==response.get('model')),None)
    if not m:return None
    return float((Decimal(m['inputPrice'])*inp+Decimal(m['outputPrice'])*out)/1000)

def summarize(records):
    result={}
    for policy in POLICIES:
        rows=[r for r in records if r['policy']==policy]
        if not rows:continue
        latency=sorted(r['latencyMs'] for r in rows)
        quality=[r['quality'] for r in rows if r.get('quality') is not None]
        result[policy]={'requests':len(rows),'successRate':sum(r['success'] for r in rows)/len(rows),
            'qualityCoverage':len(quality)/len(rows),'meanQuality':sum(quality)/len(quality) if quality else None,
            'meanLatencyMs':sum(latency)/len(latency),'p95LatencyMs':latency[max(0,__import__('math').ceil(.95*len(latency))-1)],
            'answerCostCny':sum(r['answerCostCny'] for r in rows if r.get('answerCostCny') is not None),
            'pricedAnswers':sum(r.get('answerCostCny') is not None for r in rows),
            'judgeCostCny':sum(r.get('judgeCostCny',0) for r in rows),
            'models':dict(Counter(r.get('model','failed') for r in rows))}
    return result

def main():
    import httpx
    from dotenv import dotenv_values
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run',action='store_true',help='Explicitly starts paid API calls')
    parser.add_argument('--limit',type=int,default=0,help='Smoke test only; never a complete evaluation')
    parser.add_argument('--concurrency',type=int,default=1,choices=(1,2,3))
    args=parser.parse_args()
    rows=read_inputs(args.dataset);state=frozen_state()
    max_input=max((len(row['prompt'])+2)//3 for row in rows)
    output_limit=min(4096,min(int(m['contextLength']) for m in state['models'])-max_input-128)
    if output_limit<512:raise ValueError('模型上下文空间不足以执行统一回答参数')
    # Excludes secrets; includes profile versions, suppliers, prices and immutable dataset.
    manifest={'routerCodeHash':hashlib.sha256((ROOT/'services/gateway/app/routing/explainable_router.py').read_bytes()).hexdigest(),'scorerCodeHash':hashlib.sha256((ROOT/'services/evaluation/app/services/ai_scoring_service.py').read_bytes()).hexdigest(),'datasetHash':digest(rows),'stateHash':digest(state),'state':state,'policies':POLICIES,
        'temperature':0,'max_tokens':output_limit,'concurrency':args.concurrency,'scoring':'exact for math/classification; two other candidates AI judge for code/summary (not code execution)',
        'validationTaskIds':VALIDATION_IDS,'split':EXPERIMENT_SPLIT,'sourceFreezeHash':SOURCE_FREEZE_HASH,'seed':20261008,'smokeLimit':args.limit}
    args.output.mkdir(parents=True,exist_ok=True);manifest_path=args.output/'manifest.json'
    if manifest_path.exists():
        existing=json.loads(manifest_path.read_text())
        if any(existing.get(k)!=v for k,v in manifest.items()):raise ValueError('冻结配置已改变，请使用新输出目录')
        run_id=existing['runId']
    else:
        run_id=EXPERIMENT_SPLIT+'-'+str(uuid.uuid4());manifest['runId']=run_id
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('前置检查通过。完整实验：480次回答调用，编程/摘要最多480次AI评分调用。')
    print('实验类型：'+EXPERIMENT_SPLIT+'；保持画像冻结，不发布实验评分。')
    if not args.run:
        print('只检查和保存配置，未调用模型。正式运行需 --run。');return
    sys.path.insert(0,str(ROOT/'services/evaluation'))
    from app.services.ai_scoring_service import build_scoring_prompt, _parse_evaluation_result
    env=dotenv_values(ROOT/'services/evaluation/.env')
    key=os.environ.get('EVALROUTE_API_KEY') or env.get('GATEWAY_API_KEY')
    if not key:raise ValueError('缺少网关 API Key')
    base=env.get('GATEWAY_BASE_URL','http://127.0.0.1:8123').rstrip('/')
    if base.endswith('/v1'):base=base[:-3]
    log=args.output/'results.jsonl'
    records=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    done={(r['id'],r['policy']) for r in records}
    jobs=[(r,p) for r in rows for p in POLICIES];random.Random(20261008).shuffle(jobs)
    if args.limit:jobs=jobs[:args.limit]
    with httpx.Client(timeout=300,headers={'Authorization':'Bearer '+key}) as client:
        def evaluate(job):
            row,policy=job
            if digest(frozen_state())!=manifest['stateHash']:raise ValueError('候选模型、价格或画像变化，实验停止')
            payload={'messages':[{'role':'user','content':row['prompt']}],'stream':False,
                'temperature':0,'max_tokens':output_limit,'task_type':row['task'],'evaluation_run_id':run_id,**POLICIES[policy]}
            start=time.perf_counter();record={'id':row['id'],'task':row['task'],'policy':policy,'runId':run_id,'split':EXPERIMENT_SPLIT,'quality':None,'judgeCostCny':0}
            try:
                response=client.post(base+'/v1/chat/completions',json=payload);response.raise_for_status();answer=response.json()
                if answer.get('code',0)!=0:raise ValueError(answer.get('message','网关调用失败'))
                model=answer.get('model')
                if model not in MODELS or (policy.startswith('fixed:') and model!=policy[6:]):raise ValueError('响应模型不符合候选或固定模型要求')
                output=answer['choices'][0]['message']['content'] or ''
                record.update(model=model,output=output,usage=answer.get('usage'),gateway=answer.get('gateway'),answerCostCny=price(answer,state),success=bool(output.strip()))
                record['quality']=score_exact(output,row['gold'])
                record['latencyMs']=(time.perf_counter()-start)*1000
                if row['task'] in ('code','summarization') and output.strip():
                    scores=[];judge_records=[];record['judges']=judge_records
                    prompt=build_scoring_prompt(row['prompt'],output)+'\n参考答案与评分规则：'+json.dumps(row['gold'],ensure_ascii=False)
                    for judge in [m for m in MODELS if m!=model]:
                        jr=client.post(base+'/v1/chat/completions',json={'model':judge,'routing_strategy':'fixed','messages':[{'role':'user','content':prompt}],'temperature':0,'max_tokens':4096,'evaluation_run_id':run_id,'task_type':row['task']},headers={'X-Eval-Purpose':'evaluation_judge'})
                        jr.raise_for_status();jo=jr.json()
                        if jo.get('model')!=judge:raise ValueError('评分模型发生替代')
                        parsed=_parse_evaluation_result(jo['choices'][0]['message']['content'])
                        if parsed is not None:scores.append(float(parsed.total_score)/100)
                        cost=price(jo,state)
                        if cost is None:raise ValueError('评分调用缺少usage，费用无法完整统计')
                        record['judgeCostCny']+=cost;judge_records.append({'model':judge,'result':parsed.model_dump() if parsed else None,'costCny':cost})
                    record['judges']=judge_records
                    if len(scores)==2:record['quality']=sum(scores)/2
            except Exception as error:
                record['error']=str(error)[:300];record.setdefault('success',False)
            record.setdefault('latencyMs',(time.perf_counter()-start)*1000)
            return record
        from concurrent.futures import ThreadPoolExecutor, as_completed
        remaining=[job for job in jobs if (job[0]['id'],job[1]) not in done]
        failures=0
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for offset in range(0,len(remaining),args.concurrency):
                futures=[pool.submit(evaluate,job) for job in remaining[offset:offset+args.concurrency]]
                for future in as_completed(futures):
                    record=future.result()
                    with log.open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
                    records.append(record)
                    (args.output/'summary.json').write_text(json.dumps({'complete':len(records)==len(rows)*len(POLICIES),'smoke':bool(args.limit),'results':summarize(records)},ensure_ascii=False,indent=2))
                    print(record['id'],record['policy'],'OK' if record['success'] else '失败','评分',record['quality'],flush=True)
                    failures=failures+1 if not record['success'] else 0
                    if failures>=3:raise ValueError('连续三个回答失败，停止收费调用并保留已有结果')
                time.sleep(1)
    if digest(frozen_state())!=manifest['stateHash']:raise ValueError('运行结束时冻结配置变化，结果不可视为固定配置实验')
if __name__=='__main__':main()
