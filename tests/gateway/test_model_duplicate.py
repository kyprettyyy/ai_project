import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from sqlalchemy.exc import IntegrityError
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/gateway'))
from app.models.model import Model
from app.services.model_service import ModelService
from app.exceptions.business_exception import BusinessException

class ModelDuplicateTest(unittest.IsolatedAsyncioTestCase):
    async def test_active_duplicate_across_providers_is_business_error(self):
        db=AsyncMock();db.add=Mock()
        db.scalar.return_value=Model(id=4,model_key='same',provider_id=1,is_delete=0)
        with self.assertRaisesRegex(BusinessException,'不同供应商'):
            await ModelService(db).add_model(Model(model_key=' same ',provider_id=2))
        db.add.assert_not_called();db.commit.assert_not_awaited()

    async def test_deleted_identifier_can_be_readded_with_new_provider(self):
        db=AsyncMock();db.add=Mock()
        old=Model(id=4,is_delete=1,model_key='same',provider_id=1)
        db.scalar.return_value=old
        new=Model(id=5,model_key='same',provider_id=2)
        self.assertEqual(await ModelService(db).add_model(new),5)
        self.assertIn('~deleted~4~',old.model_key)
        self.assertEqual(old.provider_id,1)
        self.assertEqual(new.model_key,'same');self.assertEqual(new.provider_id,2)
        db.flush.assert_awaited_once();db.commit.assert_awaited_once()

    async def test_delete_releases_identifier_and_preserves_row(self):
        db=AsyncMock();old=Model(id=4,is_delete=0,model_key='x'*128)
        db.scalar.return_value=old
        self.assertTrue(await ModelService(db).delete_model(4))
        self.assertEqual(old.is_delete,1);self.assertLessEqual(len(old.model_key),128)
        self.assertIn('~deleted~4~',old.model_key);db.commit.assert_awaited_once()

    async def test_concurrent_duplicate_rolls_back(self):
        db=AsyncMock();db.add=Mock()
        db.scalar.side_effect=[None,Model(id=4,is_delete=0)]
        db.commit.side_effect=IntegrityError('insert',{},Exception('duplicate'))
        with self.assertRaisesRegex(BusinessException,'已存在'):
            await ModelService(db).add_model(Model(model_key='same',provider_id=2))
        db.rollback.assert_awaited_once()

    async def test_unrelated_integrity_error_is_not_mislabelled(self):
        db=AsyncMock();db.add=Mock();db.scalar.return_value=None
        db.commit.side_effect=IntegrityError('insert',{},Exception('other'))
        with self.assertRaises(IntegrityError):
            await ModelService(db).add_model(Model(model_key='new',provider_id=2))

    async def test_new_identifier_is_committed(self):
        db=AsyncMock();db.add=Mock();db.scalar.return_value=None
        m=Model(id=5,model_key=' new ',provider_id=2)
        self.assertEqual(await ModelService(db).add_model(m),5)
        self.assertEqual(m.model_key,'new');db.commit.assert_awaited_once()
