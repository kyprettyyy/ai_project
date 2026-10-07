import sys,unittest
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/gateway'))
from app.services.balance_service import BalanceService
from app.schemas.payment import AdminCreditRequest
from app.exceptions.business_exception import BusinessException
from pydantic import ValidationError

class AdminCreditTest(unittest.IsolatedAsyncioTestCase):
 async def test_credit_records_operator_and_keeps_recharge_separate(self):
  user=SimpleNamespace(balance=Decimal('2'))
  db=MagicMock();db.scalar=AsyncMock(return_value=user);db.commit=AsyncMock()
  balance=await BalanceService(db).admin_credit(2,Decimal('10'),'测试额度',1)
  self.assertEqual(balance,Decimal('12'))
  record=db.add.call_args.args[0]
  self.assertEqual(record.billing_type,'admin_credit')
  self.assertEqual(record.balance_before,Decimal('2'))
  self.assertEqual(record.balance_after,Decimal('12'))
  self.assertIn('管理员 1',record.description)
  self.assertIn('FOR UPDATE',str(db.scalar.call_args.args[0]))
  db.commit.assert_awaited_once()
 async def test_missing_user_no_commit(self):
  db=MagicMock();db.scalar=AsyncMock(return_value=None);db.commit=AsyncMock()
  with self.assertRaises(BusinessException): await BalanceService(db).admin_credit(2,Decimal('10'),'测试',1)
  db.commit.assert_not_awaited()
 def test_invalid_amount_rejected(self):
  for amount in ['0','-1','NaN','1.001','1000001']:
   with self.assertRaises(ValidationError): AdminCreditRequest(userId=2,amount=amount,reason='测试')
 async def test_normal_user_cannot_credit(self):
  from app.api.balance import router
  from app.middleware.auth import get_login_user
  from unittest.mock import patch
  route=next(r for r in router.routes if r.path=='/balance/admin/credit')
  dependency=next(d for d in route.dependant.dependencies if d.name=='admin').call
  with patch('app.middleware.auth.get_login_user',AsyncMock(return_value=SimpleNamespace(user_role='user'))):
   with self.assertRaises(BusinessException) as error: await dependency(None,None,None)
   self.assertEqual(error.exception.code,40101)
