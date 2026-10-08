"""Select a provisional test configuration from matched, currently scored validation answers."""
import argparse,json,hashlib,shutil
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

def choose(replay):
 records=replay['records'];policies=sorted({r['policy'] for r in records})
 index={(r['id'],r['policy']):r for r in records}
 ids=sorted({r['id'] for r in records})
 common=[qid for qid in ids if all(index[qid,p].get('quality') is not None for p in policies)]
 if not common:raise ValueError('当前没有可公平比较的共同已评分题目')
 task_counts=Counter(index[qid,policies[0]]['task'] for qid in common)
 summaries=[]
 for policy in policies:
  rows=[index[qid,policy] for qid in ids];paired=[index[qid,policy] for qid in common]
  per_task={task:sum(r['quality'] for r in paired if r['task']==task)/count for task,count in task_counts.items()}
  known=[r['currentCatalogAnswerEstimateCny'] for r in rows if r.get('currentCatalogAnswerEstimateCny') is not None]
  summaries.append({'policy':policy,'matchedQuestions':len(common),'matchedQualityByTask':per_task,
    'matchedMacroQuality':sum(per_task.values())/len(per_task),
    'allQuestionCount':len(rows),'qualityCoverage':sum(r.get('quality') is not None for r in rows)/len(rows),
    'successRate':sum(r['success'] for r in rows)/len(rows),'meanLatencySeconds':sum(r['latencyMs'] for r in rows)/len(rows)/1000,
    'catalogAnswerEstimateCny':sum(known) if len(known)==len(rows) else None,
    'modelSelections':dict(Counter(r['model'] for r in rows))})
 best=max(r['matchedMacroQuality'] for r in summaries)
 eligible=[r for r in summaries if r['matchedMacroQuality']>=best-.02 and r['successRate']>=.98 and r['catalogAnswerEstimateCny'] is not None]
 if not eligible:raise ValueError('当前没有满足明确筛选规则的策略')
 selected=min(eligible,key=lambda r:(r['catalogAnswerEstimateCny'],r['meanLatencySeconds']))
 return selected,summaries,common,dict(task_counts)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args();folder=args.folder
 replay=json.loads((folder/'offline_replay.json').read_text());audit=json.loads((folder/'audited_summary.json').read_text())
 selected,summaries,common,counts=choose(replay)
 now=datetime.now(timezone.utc);snapshot=folder/('当前评分冻结_'+now.strftime('%Y%m%d_%H%M%S'));snapshot.mkdir()
 for filename in ['audited_answers.json','audited_summary.json','offline_replay.json']:shutil.copy2(folder/filename,snapshot/filename)
 files={name:hashlib.sha256((snapshot/name).read_bytes()).hexdigest() for name in ['audited_answers.json','audited_summary.json','offline_replay.json']}
 frozen={'status':'provisional_configuration_frozen_from_current_scores','method':'offline replay of existing answers; not live gateway validation',
  'capturedAt':now.isoformat(),'selectedPolicy':selected['policy'],'selectionRule':'same scored questions across all six policies, equal task weights; within 2 percentage points of best macro quality, success >=98%, minimize catalog answer estimate, then latency',
  'matchedQuestionIds':common,'matchedCountsByTask':counts,'summaries':summaries,'profiles':replay['profiles'],
  'trainingTasks':audit['trainingTasks'],'validationTasks':audit['validationTasks'],'catalogPrices':audit['prices'],
  'weights':replay['weights'],'fileHashes':files,'autoUpdate':False,'profilesPublished':False,'testSetTouched':False,
  'limitations':replay['limitations']+['Selection bias from excluding missing scores; small per-category matched sample; provisional selection only']}
 (snapshot/'frozen_for_test.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2))
 names={'math':'数学','classification':'分类','code':'编程','summarization':'摘要'}
 lines=['# 按当前评分进行验证对比','',f'已冻结当前数据快照；候选策略：**{selected["policy"]}**。','',
 f'80道验证题、3个模型，共240条已有答案，回放6种策略共480次选择。没有额外生成答案或评分，也未发布平台画像。六种策略都能取得有效分数的共同题目为{len(common)}/80；按类别分别计算均分后等权平均，避免某种策略靠缺分题更少获得优势。','',
 '共同已评分题目：'+ '、'.join(f'{names[t]} {n}/20' for t,n in counts.items())+'。','',
 '| 策略 | 共同题目质量均分（0–100） | 成功回答 | 复用答案平均耗时 | 80条回答目录价估算 |',
 '|---|---:|---:|---:|---:|']
 for r in summaries:lines.append(f'| {r["policy"]} | {r["matchedMacroQuality"]*100:.2f} | {round(r["successRate"]*80)}/80 | {r["meanLatencySeconds"]:.2f}秒 | ¥{r["catalogAnswerEstimateCny"]:.6f} |')
 lines+=['','筛选规则：先在同一批共同已评分题目上比较各类别的归一化质量；保留距最佳均分不超过2个百分点、成功回答率至少98%的策略，再优先选择目录价估算回答费最低者，费用相同则比较耗时。此规则为探索性筛选，不是统计显著性检验。','',
 '数学和分类使用标准答案客观评分；编程和摘要使用已保存AI总分，编程分数不是执行代码的通过率。缺分保持未知，不当作0或满分。不同模型可能由不同评委打分，存在评委偏差；共同题目数量小的类别只能作初步观察。','',
 '目录价估算使用当前平台配置的人民币单价和原Token，未包含评分费，不是历史账单。平均耗时来自已有回答，未计入本次线上路由开销。缺分条目被排除可能产生选择偏差，不能以此宣称正式线上提升。','',
 '当前测试配置只用于下一阶段最终验证：候选模型、训练来源、价格、当前画像数据、路由权重与文件哈希已保存到 frozen_for_test.json。后台后续补评分不会修改该快照。配置未写入平台；测试集未调用。','',
 '文件位置：'+str(snapshot),'']
 (snapshot/'对比结果与冻结说明.md').write_text('\n'.join(lines))
 (folder/'current_score_freeze_pointer.json').write_text(json.dumps({'snapshot':str(snapshot),'selectedPolicy':selected['policy'],'matchedQuestions':len(common),'capturedAt':now.isoformat()},ensure_ascii=False,indent=2))
 (folder/'workflow-state.json').write_text(json.dumps({'stage':'current_score_replay_frozen','snapshot':str(snapshot),'selectedPolicy':selected['policy'],'matchedQuestions':len(common),'updatedAt':now.isoformat()},ensure_ascii=False,indent=2))
 (folder/'实验进度.md').write_text('# 验证集实验进度\n\n已按当前评分完成离线对比并冻结候选配置。\n\n候选策略：'+selected['policy']+'\n\n共同已评分题目：'+str(len(common))+'/80。\n\n后续评分保存在原任务，当前快照不变。平台画像未发布，测试集未调用。\n\n[查看对比结果与冻结说明]('+str(snapshot/'对比结果与冻结说明.md')+')\n')
 print(json.dumps({'selected':selected,'matchedCounts':counts,'snapshot':str(snapshot)},ensure_ascii=False))
if __name__=='__main__':main()
