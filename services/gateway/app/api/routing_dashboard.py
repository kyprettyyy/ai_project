"""Scoped routing analytics. Never return API secrets, questions, or answers."""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select,func,case,or_,and_,cast,String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.common.result_utils import success
from app.db.session import get_db_session
from app.middleware.auth import require_login
from app.models.user import User
from app.models.model import Model
from app.models.api_key import ApiKey
from app.models.request_log import RequestLog
from app.models.model_capability_profile import ModelCapabilityProfile
from app.models.model_profile_history import ModelProfileHistory
from app.models.answer_feedback import AnswerFeedback,SatisfactionProfile
from app.models.routing_decision import RoutingDecision
from app.api.routing_audit import _decision_payload
from app.exceptions.business_exception import BusinessException
from app.core.constants import ErrorCode
router=APIRouter(prefix='/routing-analysis',tags=['routing-analysis'])

def access_scope(user,user_id=None):
    if user.user_role=='admin':return user_id
    if user_id is not None and user_id!=user.id:
        raise BusinessException(ErrorCode.NO_AUTH_ERROR,'只能查看自己的调用数据')
    return user.id

def logical_metrics(conditions):
    # Scope the trace by owner/key; untraceable legacy records remain individual.
    request_key=case((and_(RequestLog.trace_id.is_not(None),RequestLog.trace_id!=''),
                      'trace:'+RequestLog.trace_id),else_='row:'+cast(RequestLog.id,String))
    grouped=select(func.max(RequestLog.id).label('last_id')).where(*conditions).group_by(
        RequestLog.user_id,RequestLog.api_key_id,request_key).subquery()
    terminal=aliased(RequestLog)
    return select(func.count(),
        func.sum(case((terminal.status=='success',1),else_=0)),
        func.avg(case((terminal.status=='success',terminal.duration),else_=None)),
        func.sum(case((terminal.routing_strategy=='cache',1),else_=0))
    ).select_from(grouped).join(terminal,terminal.id==grouped.c.last_id)



def iso(value):
    return (value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat() if value else None

@router.get('')
async def dashboard(days:int=Query(30,ge=1,le=90), userId:int|None=None, apiKeyId:int|None=None, traffic:str=Query("all",pattern="^(all|online|evaluation|legacy)$"),
                    user:User=Depends(require_login),db:AsyncSession=Depends(get_db_session)):
    owner=access_scope(user,userId)
    window_end=datetime.now(timezone.utc).replace(tzinfo=None)
    window_start=window_end-timedelta(days=days)
    conditions=[RequestLog.create_time>=window_start,RequestLog.create_time<=window_end]
    if owner is not None:conditions.append(RequestLog.user_id==owner)
    if apiKeyId is not None:
        key=await db.get(ApiKey,apiKeyId)
        if not key or (owner is not None and key.user_id!=owner):
            raise BusinessException(ErrorCode.NO_AUTH_ERROR,'无权限查看该 API Key')
        conditions.append(RequestLog.api_key_id==apiKeyId)
    traffic_tag=func.json_extract(RequestLog.pricing_snapshot,'$.trafficType')
    evaluation=or_(and_(RequestLog.evaluation_run_id.is_not(None),RequestLog.evaluation_run_id!=''),RequestLog.task_type=='evaluation_judge',traffic_tag.in_(['evaluation','"evaluation"']))
    # A request can have an old untagged failed attempt followed by a tagged
    # success. Classify the entire trace together, so scope totals do not overlap.
    online_evidence=or_(RequestLog.source=='web',traffic_tag.in_(['online','"online"']))
    request_key=case((and_(RequestLog.trace_id.is_not(None),RequestLog.trace_id!=''),
                      'trace:'+RequestLog.trace_id),else_='row:'+cast(RequestLog.id,String))
    partition=[RequestLog.user_id,RequestLog.api_key_id,request_key]
    if traffic in ('online','evaluation','legacy'):
        labels=select(RequestLog.id.label('log_id'),
            func.max(case((evaluation,1),else_=0)).over(partition_by=partition).label('evaluation'),
            func.max(case((online_evidence,1),else_=0)).over(partition_by=partition).label('online')
        ).where(*conditions).subquery()
        kind=labels.c.evaluation==1 if traffic=='evaluation' else and_(labels.c.evaluation==0,labels.c.online==1 if traffic=='online' else labels.c.online==0)
        conditions.append(RequestLog.id.in_(select(labels.c.log_id).where(kind)))
    task_key=func.coalesce(func.nullif(RequestLog.task_type,''),'general')
    metrics=[func.count(RequestLog.id),func.sum(case((RequestLog.status=='success',1),else_=0)),func.sum(RequestLog.total_tokens),func.avg(case((RequestLog.status=='success',RequestLog.duration),else_=None))]
    log_count,log_ok,tokens,log_latency=(await db.execute(select(*metrics).where(*conditions))).one()
    count,ok,latency,cache_count=(await db.execute(logical_metrics(conditions))).one()
    unknown_usage=await db.scalar(select(func.count()).select_from(RequestLog).where(*conditions,RequestLog.total_tokens==0,or_(RequestLog.routing_strategy.is_(None),RequestLog.routing_strategy!='cache')))
    unattributed=await db.scalar(select(func.count()).select_from(RequestLog).where(*conditions,or_(RequestLog.trace_id.is_(None),RequestLog.trace_id=='')))
    costs=(await db.execute(select(RequestLog.cost_currency,func.sum(RequestLog.catalog_cost)).where(*conditions,RequestLog.catalog_cost.is_not(None),RequestLog.cost_currency.in_(['CNY','USD'])).group_by(RequestLog.cost_currency))).all()
    missing=await db.scalar(select(func.count()).select_from(RequestLog).where(*conditions,or_(RequestLog.routing_strategy.is_(None),RequestLog.routing_strategy!='cache'),or_(RequestLog.catalog_cost.is_(None),RequestLog.cost_currency.notin_(['CNY','USD']))))
    priced_records, priced_tokens = (await db.execute(select(
        func.count(), func.coalesce(func.sum(RequestLog.total_tokens), 0)
    ).select_from(RequestLog).where(*conditions, RequestLog.catalog_cost.is_not(None),
        RequestLog.cost_currency.in_(['CNY', 'USD']),
        or_(RequestLog.routing_strategy.is_(None), RequestLog.routing_strategy != 'cache')))).one()
    model_costs=defaultdict(dict)
    for m,t,c,v in (await db.execute(select(RequestLog.model_name,task_key,RequestLog.cost_currency,func.sum(RequestLog.catalog_cost)).where(*conditions,RequestLog.catalog_cost.is_not(None),RequestLog.cost_currency.in_(['CNY','USD'])).group_by(RequestLog.model_name,task_key,RequestLog.cost_currency))).all():
        model_costs[(m,t or 'general')][c]=float(v)
    usage=[]
    for model,task,n,s,t,d in (await db.execute(select(RequestLog.model_name,task_key,*metrics).where(*conditions).group_by(RequestLog.model_name,task_key))).all():
        usage.append({'model':model,'taskType':task or 'general','count':n,'successRate':round(float(s or 0)/n*100,2),'tokens':int(t or 0),'latency':round(float(d),1) if d is not None else None})
    votes=(await db.execute(select(RequestLog.model_name,task_key,AnswerFeedback.vote,func.count()).join(AnswerFeedback,AnswerFeedback.request_log_id==RequestLog.id).where(*conditions).group_by(RequestLog.model_name,task_key,AnswerFeedback.vote))).all()
    feedback=defaultdict(lambda:{'positive':0,'negative':0})
    for m,t,v,n in votes:feedback[(m,t or 'general')]['positive' if v>0 else 'negative']+=n
    for row in usage:
        row['costs']=model_costs[(row['model'],row['taskType'])];row.update(feedback[(row['model'],row['taskType'])]);n=row['positive']+row['negative'];row['satisfaction']=round(row['positive']/n*100,1) if n else None
    history=[{'model':h.model_key,'taskType':h.task_type,'version':h.profile_version,
              'time':iso(h.recorded_at),**h.snapshot} for h in (await db.scalars(
              select(ModelProfileHistory).order_by(ModelProfileHistory.recorded_at.desc(),ModelProfileHistory.id.desc()).limit(2000))).all()]
    profile_coverage={(h['model'],h['taskType'],h['version']):h.get('coverage') for h in history}
    for h in history:
        coverage=h.get('coverage')
        if not coverage or not coverage.get('costComparable'):h['cost']=None
    profiles=[]
    satisfaction={(s.model_id,s.task_type):s for s in (await db.scalars(select(SatisfactionProfile))).all()}
    for p in (await db.scalars(select(ModelCapabilityProfile).order_by(ModelCapabilityProfile.model_key,ModelCapabilityProfile.task_type))).all():
        sp=satisfaction.get((p.model_id,p.task_type))
        coverage=profile_coverage.get((p.model_key,p.task_type,p.profile_version))
        profiles.append({'model':p.model_key,'taskType':p.task_type,'quality':float(p.quality_score)*100,'latency':float(p.latency_score)*100,'cost':float(p.cost_score)*100 if coverage and coverage.get('costComparable') else None,'coverage':coverage,'reliability':float(p.reliability_score)*100,'samples':p.sample_count,'version':p.profile_version,'updatedAt':iso(p.update_time),'source':'批量评测汇总','qualityNote':'综合质量为已有 AI/人工/正确性评分的加权均值；缺失项不参与均值。样本数以当前发布画像记录为准；训练冻结画像按有效评分样本计数，空回答通过可靠性体现。速度按同类任务、成本效率按同类任务同币种相对归一化。缺价、混合币种或不足2个可比较模型时，成本效率显示未统计。','satisfaction':round(sp.positive_count/sp.sample_count*100,1) if sp and sp.sample_count else None,'feedbackSamples':sp.sample_count if sp else 0})
    # Ownership is proven through request logs before exposing decision snapshots.
    traces=select(RequestLog.trace_id).where(*conditions,RequestLog.trace_id.is_not(None))
    decisions=[]
    for d in (await db.scalars(select(RoutingDecision).where(RoutingDecision.trace_id.in_(traces)).order_by(RoutingDecision.created_at.desc()).limit(100))).all():
        payload=_decision_payload(d);payload['createdAt']=iso(d.created_at);decisions.append(payload)
    key_conditions=[] if owner is None else [ApiKey.user_id==owner]
    keys=[{'id':str(k.id),'name':k.key_name or f'Key #{k.id}'} for k in (await db.scalars(select(ApiKey).where(*key_conditions))).all()]
    users=[]
    if user.user_role=='admin':
        users=[{'id':str(u.id),'name':u.user_name or f'用户 #{u.id}'} for u in (await db.scalars(select(User).where(User.is_delete==0))).all()]
    key_costs=defaultdict(dict)
    for kid,c,v in (await db.execute(select(RequestLog.api_key_id,RequestLog.cost_currency,func.sum(RequestLog.catalog_cost)).where(*conditions,RequestLog.catalog_cost.is_not(None),RequestLog.cost_currency.in_(['CNY','USD'])).group_by(RequestLog.api_key_id,RequestLog.cost_currency))).all():
        key_costs[kid][c]=float(v)
    key_votes=defaultdict(lambda:{'positive':0,'negative':0})
    for kid,v,n in (await db.execute(select(RequestLog.api_key_id,AnswerFeedback.vote,func.count()).join(AnswerFeedback,AnswerFeedback.request_log_id==RequestLog.id).where(*conditions).group_by(RequestLog.api_key_id,AnswerFeedback.vote))).all():
        key_votes[kid]['positive' if v>0 else 'negative']+=n
    key_usage=[]
    for kid,n,s,t,d in (await db.execute(select(RequestLog.api_key_id,*metrics).where(*conditions).group_by(RequestLog.api_key_id))).all():
        key_usage.append({'costs':key_costs[kid],**key_votes[kid],'id':str(kid) if kid is not None else None,'name':next((k['name'] for k in keys if k['id']==str(kid)),'网页 / 内部调用' if kid is None else f'Key #{kid}'),'count':n,'successRate':round(float(s or 0)/n*100,2),'tokens':int(t or 0),'latency':round(float(d),1) if d is not None else None})
    return success({'isAdmin':user.user_role=='admin','summary':{'count':count,'logCount':log_count,'cacheRequests':int(cache_count or 0),'unknownUsageRecords':unknown_usage,'untracedRecords':unattributed,'successRate':round(float(ok or 0)/count*100,2) if count else None,'tokens':int(tokens or 0),'latency':round(float(latency),1) if latency is not None else None,'costs':{c:float(v) for c,v in costs},'unpriced':missing,'pricedRecords':int(priced_records),'pricedTokens':int(priced_tokens),'costTokenCoverage':round(int(priced_tokens)/int(tokens)*100,2) if tokens else None},'profiles':profiles,'profileHistory':history,'usage':usage,'keys':keys,'keyUsage':key_usage,'users':users,'decisions':decisions,'scope':'全局' if owner is None else '用户调用','days':days,'traffic':traffic,'windowStart':iso(window_start),'windowEnd':iso(window_end),'statisticsNote':'请求数按用户/API Key/trace 去重；按最后一条日志判定请求成功/失败。无 trace 的旧日志逐条计数，无法可靠还原请求数。Token 为已记录用量；0 用量的非缓存日志标为未知。费用仅为已记录 Token 的目录价估算，不含搜索费用、免费额度和折扣。未分类历史 API 调用不能认定为线上或评测。'})

from pydantic import BaseModel
from typing import Literal
from app.models.answer_feedback import PersonalSatisfactionProfile, UserRoutingPreference

class PreferenceRequest(BaseModel):
    mode: Literal['balanced', 'quality', 'cost', 'latency']

@router.get('/personal')
async def personal_profile(userId: int | None = None, user: User = Depends(require_login), db: AsyncSession = Depends(get_db_session)):
    uid = access_scope(user, userId) or user.id
    preference = await db.get(UserRoutingPreference, uid)
    profiles = (await db.execute(select(PersonalSatisfactionProfile, Model.model_key).join(Model,
        Model.id == PersonalSatisfactionProfile.model_id).where(PersonalSatisfactionProfile.user_id == uid))).all()
    from app.services.personal_routing_service import other_users_priors
    from app.routing.bayesian_feedback import estimate_feedback, ALGORITHM_VERSION
    priors = await other_users_priors(db, uid, [p.model_id for p,_ in profiles], [p.task_type for p,_ in profiles]) if profiles else {}
    counts = (await db.execute(select(RequestLog.model_name, func.coalesce(func.nullif(RequestLog.task_type, ''), 'general'), func.count())
        .join(AnswerFeedback, AnswerFeedback.request_log_id == RequestLog.id).where(RequestLog.user_id == uid,
        RequestLog.status == 'success', RequestLog.evaluation_run_id.is_(None), AnswerFeedback.vote.in_([-1, 1]))
        .group_by(RequestLog.model_name, func.coalesce(func.nullif(RequestLog.task_type, ''), 'general')))).all()
    return success({'userId':str(uid), 'mode':preference.mode if preference else 'balanced', 'batchSize':30, 'algorithm':ALGORITHM_VERSION,
        'profiles':[{'model':model, 'taskType':p.task_type, 'samples':p.sample_count,
            'satisfaction':round(p.positive_count/p.sample_count*100,2) if p.sample_count else None,
            'version':p.version, 'estimate':estimate_feedback(p.positive_count, p.sample_count, *priors.get((p.model_id,p.task_type), (.5,2.)))} for p,model in profiles],
        'feedback':[{'model':m,'taskType':t,'samples':n} for m,t,n in counts]})

@router.post('/personal/preference')
async def save_personal_preference(body: PreferenceRequest, user: User = Depends(require_login), db: AsyncSession = Depends(get_db_session)):
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = await db.get(UserRoutingPreference, user.id)
    if row is None:
        row = UserRoutingPreference(user_id=user.id)
        db.add(row)
    row.mode = body.mode
    await db.commit()
    return success(True)
