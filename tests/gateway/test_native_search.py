import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.adapter.native_search import search_extra
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from unittest.mock import AsyncMock,patch
class SearchTest(unittest.IsolatedAsyncioTestCase):
 def test_native_parameters_and_unsupported(self):
  req=ChatRequest(messages=[],enable_search=True)
  provider=NS(base_url='https://dashscope.aliyuncs.com/compatible-mode/v1')
  self.assertTrue(search_extra(NS(model_key='qwen-turbo'),provider,req)['search_options']['forced_search'])
  for key in ('kimi-k3','deepseek-v4.1-flash'):
   with self.assertRaises(ValueError):search_extra(NS(model_key=key),provider,req)
 async def test_old_web_search_does_not_call_plugin(self):
  req=ChatRequest(messages=[],plugin_key='web_search')
  with patch('app.services.chat_service.PluginService') as plugin:
   result=await ChatService._inject_plugin_context(NS(db=None),req,1)
   plugin.assert_not_called()
   self.assertTrue(result.enable_search);self.assertIsNone(result.plugin_key)
