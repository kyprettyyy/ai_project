import sys,unittest
from pathlib import Path
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.services.routing_service import RoutingService
from app.services.chat_service import ChatService
class AutoMergeTest(unittest.IsolatedAsyncioTestCase):
 async def test_auto_uses_feedback_ranking_and_fallback(self):
  for strategy in ('auto','adaptive',None):
   service=RoutingService(None)
   first,second=object(),object()
   service.adaptive.rank_models=AsyncMock(return_value=[(first,.9,{}),(second,.8,{})])
   service.adaptive.persist_decision=AsyncMock()
   self.assertIs(await service.select_model(strategy,'chat',None,trace_id='t'),first)
   self.assertEqual(await service.get_fallback_models(strategy,'chat',None),[second])
   service.adaptive.persist_decision.assert_awaited_once()
 def test_default_and_legacy_normalize_to_auto(self):
  self.assertEqual(ChatService._determine_strategy_type(None,None),'auto')
  self.assertEqual(ChatService._determine_strategy_type('adaptive',None),'auto')
  self.assertEqual(ChatService._determine_strategy_type(None,'qwen'),'fixed')
