import sys,unittest,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.services.request_log_service import RequestLogService
class UsageAccountingTest(unittest.IsolatedAsyncioTestCase):
 async def test_missing_usage_is_unknown_cache_is_zero_byok_preserves_estimate(self):
  model=NS(input_price=Decimal('.02'),output_price=Decimal('.1'),price_currency='CNY',pricing_config=None)
  db=NS(get=AsyncMock(return_value=model),add=Mock(),commit=AsyncMock(),refresh=AsyncMock())
  service=RequestLogService(db)
  async def log(**extra):
   return await service.log_request(**dict(user_id=1,api_key_id=None,model_id=1,model_name='m',prompt_tokens=0,completion_tokens=0,total_tokens=0,duration=1,status='success',error_message=None,cost=Decimal('0'),**extra))
  missing=await log()
  self.assertIsNone(missing.catalog_cost);self.assertFalse(json.loads(missing.pricing_snapshot)['usageKnown'])
  cache=await log(routing_strategy='cache')
  self.assertEqual(cache.catalog_cost,0);self.assertTrue(json.loads(cache.pricing_snapshot)['usageKnown'])
  row=await service.log_request(user_id=1,api_key_id=None,model_id=1,model_name='m',prompt_tokens=1000,completion_tokens=1000,total_tokens=2000,duration=1,status='success',error_message=None,cost=Decimal('0'),is_byok=True,search_enabled=True,evaluation_run_id='task')
  self.assertEqual(row.catalog_cost,Decimal('.120000'))
  snap=json.loads(row.pricing_snapshot)
  self.assertEqual(snap['credentialSource'],'byok');self.assertEqual(snap['trafficType'],'evaluation');self.assertTrue(snap['nativeSearch'])
