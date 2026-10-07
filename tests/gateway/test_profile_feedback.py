from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import BigInteger, select
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from app.api.model_profile import upsert_profiles
from app.models.model_profile_history import ModelProfileHistory
from app.models.model import Model
from app.models.model_capability_profile import ModelCapabilityProfile
from app.schemas.model_profile import ModelProfileBatch


@compiles(TINYINT, "sqlite")
@compiles(BigInteger, "sqlite")
def sqlite_integer(element, compiler, **kwargs):
    return "INTEGER"


class GatewayProfileFeedbackTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda conn: Model.metadata.create_all(
                conn, tables=[Model.__table__, ModelCapabilityProfile.__table__, ModelProfileHistory.__table__]))
        async with self.sessions() as db:
            db.add(Model(id=1, provider_id=1, model_key="model-a", model_name="Model A"))
            await db.commit()
        self.settings = patch("app.api.model_profile.get_settings", return_value=SimpleNamespace(
            internal_service_token="test-token"))
        self.settings.start()

    async def asyncTearDown(self):
        self.settings.stop()
        await self.engine.dispose()

    def payload(self, run_id="auto-run1", quality=0.8, model="model-a"):
        return ModelProfileBatch(profiles=[{
            "model": model, "task_type": "code", "quality_score": quality,
            "latency_score": 0.7, "cost_score": 0.5, "reliability_score": 1.0,
            "sample_count": 30, "evaluation_run_id": run_id,
        }])

    async def publish(self, payload):
        async with self.sessions() as db:
            return await upsert_profiles(payload, "test-token", db)

    async def test_history_records_versions_without_retry_duplicates(self):
        await self.publish(self.payload())
        await self.publish(self.payload())
        await self.publish(self.payload(run_id="auto-run2", quality=0.9))
        async with self.sessions() as db:
            history=list((await db.scalars(select(ModelProfileHistory).order_by(ModelProfileHistory.profile_version))).all())
            self.assertEqual([h.snapshot["quality"] for h in history],[80.0,90.0])

    async def test_retry_does_not_increment_version(self):
        first = await self.publish(self.payload())
        second = await self.publish(self.payload())
        self.assertEqual((first["updated"], second["unchanged"]), (1, 1))
        async with self.sessions() as db:
            profile = await db.scalar(select(ModelCapabilityProfile))
            self.assertEqual(profile.profile_version, 1)

    async def test_new_generation_updates_existing_profile(self):
        await self.publish(self.payload())
        await self.publish(self.payload("auto-run2", quality=0.4))
        async with self.sessions() as db:
            profile = await db.scalar(select(ModelCapabilityProfile))
            self.assertEqual(profile.profile_version, 2)
            self.assertAlmostEqual(float(profile.quality_score), 0.4)

    async def test_manual_reused_run_id_can_update_changed_scores(self):
        await self.publish(self.payload("manual-run"))
        result = await self.publish(self.payload("manual-run", quality=0.2))
        self.assertEqual(result["updated"], 1)

    async def test_unknown_model_is_reported_as_unaccepted(self):
        result = await self.publish(self.payload(model="missing"))
        self.assertEqual(result["updated"] + result["unchanged"], 0)
        self.assertEqual(result["missing"], ["missing"])


if __name__ == "__main__":
    unittest.main()
