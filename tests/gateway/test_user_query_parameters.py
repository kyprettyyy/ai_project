import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.user import router
from app.db.session import get_db_session

class UserQueryParametersTest(unittest.TestCase):
 def setUp(self):
  self.app=FastAPI();self.app.include_router(router)
  async def db(): yield None
  self.app.dependency_overrides[get_db_session]=db
  for route in router.routes:
   for dep in route.dependant.dependencies:
    if dep.name=='_': self.app.dependency_overrides[dep.call]=lambda:SimpleNamespace(id=1,user_role='admin')
  self.client=TestClient(self.app)
 def test_disable_enable_reset_accept_frontend_query(self):
  for path,method in [('disable','disable_user'),('enable','enable_user'),('quota/reset','reset_user_used_tokens')]:
   with patch('app.api.user.UserService') as service:
    mock=AsyncMock(return_value=True);setattr(service.return_value,method,mock)
    response=self.client.post('/user/'+path,params={'userId':'2'})
    self.assertEqual(response.status_code,200,response.text)
    self.assertEqual(response.json()['code'],0)
    mock.assert_awaited_once_with(2)
 def test_analysis_schema_uses_user_id_alias(self):
  schema=self.app.openapi()['paths']['/user/analysis']['get']
  self.assertIn('userId',[p['name'] for p in schema['parameters']])
  self.assertNotIn('user_id',[p['name'] for p in schema['parameters']])
 def test_invalid_id_does_not_reach_service(self):
  with patch('app.api.user.UserService') as service:
   response=self.client.post('/user/disable',params={'userId':'0'})
   self.assertEqual(response.status_code,422);service.assert_not_called()
