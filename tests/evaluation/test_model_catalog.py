import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/evaluation'))
from app.models.model import Base, Model
from app.services.model_service import ModelService

class CatalogTest(unittest.IsolatedAsyncioTestCase):
    async def test_enable_disable_restore_and_failed_discovery(self):
        engine = create_async_engine('sqlite+aiosqlite://')
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            response = MagicMock()
            response.json.return_value = {'data': [{'id': 'qwen-plus'}, {'id': 'glm-4.7'}]}
            client = AsyncMock()
            client.get.return_value = response
            with patch('app.services.model_service.httpx.AsyncClient') as factory:
                factory.return_value.__aenter__.return_value = client
                service = ModelService(db)
                self.assertEqual(await service.sync_models_from_gateway(), 2)
                glm = await db.get(Model, 'glm-4.7')
                glm.total_tokens = 123
                await db.commit()
                response.json.return_value = {'data': [{'id': 'qwen-plus'}]}
                await service.sync_models_from_gateway()
                self.assertEqual(glm.is_delete, 1)
                response.json.return_value = {'data': [{'id': 'glm-4.7'}]}
                await service.sync_models_from_gateway()
                self.assertEqual(glm.is_delete, 0)
                self.assertEqual(glm.total_tokens, 123)
                response.json.return_value = {'unexpected': []}
                with self.assertRaises(Exception):
                    await service.sync_models_from_gateway()
                await db.refresh(glm)
                self.assertEqual(glm.is_delete, 0)
        await engine.dispose()
