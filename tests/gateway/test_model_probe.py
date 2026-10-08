import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.services.model_probe_service import probe_model

class ProbeTest(unittest.IsolatedAsyncioTestCase):
 async def test_success_and_failure_keep_stats_unchanged(self):
  for failure in (False,True):
   model=NS(id=1,model_key='kimi',model_type='chat',provider_id=2,health_status='unknown',avg_latency=123,success_rate=77)
   provider=NS(api_key='private-key')
   db=NS(scalar=AsyncMock(side_effect=[model,provider]),commit=AsyncMock())
   invoke=AsyncMock(return_value=NS(model='kimi',choices=[NS(message=NS(content='OK'))]))
   if failure: invoke.side_effect=RuntimeError('invalid private-key')
   with patch('app.services.model_probe_service.ModelInvokeService') as factory:
    factory.return_value.invoke=invoke
    result=await probe_model(db,1)
   self.assertEqual(result['healthy'],not failure)
   self.assertEqual(model.health_status,'unhealthy' if failure else 'healthy')
   self.assertEqual((model.avg_latency,model.success_rate),(123,77))
   if failure: self.assertNotIn('private-key',result['error'])
   db.commit.assert_awaited_once()
