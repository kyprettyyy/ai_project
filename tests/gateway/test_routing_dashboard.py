import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.api.routing_dashboard import access_scope,dashboard
from app.exceptions.business_exception import BusinessException
class DashboardPermissionTests(unittest.IsolatedAsyncioTestCase):
 def test_user_scope_cannot_be_overridden(self):
  user=NS(id=1,user_role='user')
  self.assertEqual(access_scope(user),1)
  self.assertEqual(access_scope(user,1),1)
  with self.assertRaises(BusinessException):access_scope(user,2)
  self.assertIsNone(access_scope(NS(id=1,user_role='admin')))
 async def test_foreign_key_denied_before_reading_metrics(self):
  db=NS(get=AsyncMock(return_value=NS(user_id=2)),execute=AsyncMock())
  with self.assertRaises(BusinessException):
   await dashboard(days=30,userId=None,apiKeyId=9,user=NS(id=1,user_role='user'),db=db)
  db.execute.assert_not_awaited()

from sqlalchemy import BigInteger
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.models.request_log import RequestLog
from app.models.api_key import ApiKey
from app.models.answer_feedback import AnswerFeedback,SatisfactionProfile
from app.models.model_capability_profile import ModelCapabilityProfile
from app.models.model_profile_history import ModelProfileHistory
from app.models.routing_decision import RoutingDecision
@compiles(BigInteger,'sqlite')
@compiles(TINYINT,'sqlite')
def as_integer(element,compiler,**kwargs):return 'INTEGER'
class DashboardIsolationTest(unittest.IsolatedAsyncioTestCase):
 async def test_other_user_usage_keys_feedback_and_decisions_not_returned(self):
  engine=create_async_engine('sqlite+aiosqlite://')
  try:
   tables=[m.__table__ for m in [RequestLog,ApiKey,AnswerFeedback,SatisfactionProfile,ModelCapabilityProfile,ModelProfileHistory,RoutingDecision]]
   indexes=[(i,i.name) for t in tables for i in t.indexes]
   try:
    for index,name in indexes:index.name=index.table.name+'_'+name
    async with engine.begin() as conn:
     await conn.run_sync(lambda c: RequestLog.metadata.create_all(c,tables=tables))
   finally:
    for index,name in indexes:index.name=name
   sessions=async_sessionmaker(engine,expire_on_commit=False)
   async with sessions() as db:
    for uid,key,trace in [(1,11,'mine'),(2,22,'other')]:
     db.add(ApiKey(id=key,user_id=uid,key_value=f'secret-{uid}',key_name=f'key-{uid}'))
     db.add(RequestLog(id=uid,user_id=uid,api_key_id=key,model_name=f'model-{uid}',trace_id=trace,catalog_cost=1,cost_currency='CNY'))
     db.add(AnswerFeedback(request_log_id=uid,vote=1))
     db.add(RoutingDecision(trace_id=trace,task_type='general',strategy='auto',selected_model_key=f'model-{uid}',quality_weight=.5,latency_weight=.2,cost_weight=.2,reliability_weight=.1))
    await db.commit()
    payload=(await dashboard(days=30,userId=None,apiKeyId=None,user=NS(id=1,user_role='user'),db=db)).data
    self.assertEqual(payload['summary']['count'],1)
    self.assertEqual([k['id'] for k in payload['keys']],['11'])
    self.assertEqual([d['traceId'] for d in payload['decisions']],['mine'])
    self.assertEqual(payload['usage'][0]['positive'],1)
    self.assertNotIn('secret-',str(payload))
  finally:await engine.dispose()

from datetime import datetime,timedelta,timezone
class DashboardAccuracyTest(unittest.IsolatedAsyncioTestCase):
 async def test_retries_terminal_status_traffic_tokens_costs_and_time_window(self):
  engine=create_async_engine('sqlite+aiosqlite://')
  try:
   tables=[m.__table__ for m in [RequestLog,ApiKey,AnswerFeedback,SatisfactionProfile,ModelCapabilityProfile,ModelProfileHistory,RoutingDecision]]
   indexes=[(i,i.name) for t in tables for i in t.indexes]
   try:
    for index,name in indexes:index.name=index.table.name+'_'+name
    async with engine.begin() as conn:await conn.run_sync(lambda c: RequestLog.metadata.create_all(c,tables=tables))
   finally:
    for index,name in indexes:index.name=name
   sessions=async_sessionmaker(engine,expire_on_commit=False)
   now=datetime.now(timezone.utc).replace(tzinfo=None)
   async with sessions() as db:
    rows=[
     dict(id=1,trace_id='retried',status='failed',source='api'),
     dict(id=2,trace_id='retried',status='success',prompt_tokens=6,completion_tokens=4,total_tokens=10,catalog_cost=1,cost_currency='CNY'),
     dict(id=3,trace_id='terminal-fail',status='success',prompt_tokens=10,total_tokens=10,catalog_cost=.5,cost_currency='USD'),
     dict(id=4,trace_id='terminal-fail',status='failed'),
     dict(id=5,trace_id='cache',routing_strategy='cache'),
     dict(id=6,trace_id='eval',evaluation_run_id='task',prompt_tokens=20,total_tokens=20),
     dict(id=7,trace_id='judge',task_type='evaluation_judge',prompt_tokens=30,total_tokens=30),
     dict(id=8,trace_id='legacy',source='api',task_type=None,prompt_tokens=40,total_tokens=40),
     dict(id=9,trace_id=None,routing_strategy='cache'),
     dict(id=10,trace_id='old',create_time=now-timedelta(days=31)),
     dict(id=11,trace_id='future',create_time=now+timedelta(days=1)),
    ]
    for r in rows:db.add(RequestLog(**{'user_id':1,'model_name':'m','task_type':'general','source':'web','create_time':now-timedelta(seconds=1),'status':'success',**r}))
    await db.commit()
    async def read(traffic='all'):
     return (await dashboard(days=30,userId=None,apiKeyId=None,traffic=traffic,user=NS(id=1,user_role='user'),db=db)).data
    p=await read();s=p['summary']
    self.assertEqual(s['count'],7);self.assertEqual(s['logCount'],9)
    self.assertEqual(s['successRate'],85.71)
    self.assertEqual(s['tokens'],110);self.assertEqual(s['cacheRequests'],2)
    self.assertEqual(s['unknownUsageRecords'],2);self.assertEqual(s['untracedRecords'],1)
    self.assertEqual(s['costs'],{'CNY':1.,'USD':.5})
    self.assertEqual((await read('online'))['summary']['count'],4)
    self.assertEqual((await read('evaluation'))['summary']['count'],2)
    self.assertEqual((await read('legacy'))['summary']['count'],1)
    scoped=[(await read(t))['summary'] for t in ['online','evaluation','legacy']]
    self.assertEqual(sum(x['count'] for x in scoped),s['count'])
    self.assertEqual(sum(x['logCount'] for x in scoped),s['logCount'])
    self.assertEqual(len(p['usage']),2) # NULL and general merged; judge stays separate.
  finally:await engine.dispose()
