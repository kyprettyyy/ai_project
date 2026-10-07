from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import threading
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "evaluation"))

from app.core.config import get_settings
from app.jobs.model_profile_job import update_model_profiles_job
from app.schemas.batch_test import CreateBatchTestRequest
from app.scoring.profile_scoring import parse_ai_scores
from app.services.batch_test_runner import run_batch
from app.services.batch_task_state import COMPLETE_SUBTASK_SQL
from app.services.model_profile_service import ModelProfileService


class SQLiteProfileService(ModelProfileService):
    """Only replace the MySQL advisory lock; queries and persistence are real SQL."""

    @asynccontextmanager
    async def _publication_lock(self):
        yield True


class AutomaticProfileTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            for ddl in (
                """CREATE TABLE test_task (id TEXT PRIMARY KEY, config TEXT,
                   status TEXT, isDelete INTEGER DEFAULT 0, totalSubtasks INTEGER,
                   completedSubtasks INTEGER)""",
                """CREATE TABLE test_result (id TEXT PRIMARY KEY, taskId TEXT, modelName TEXT,
                   userRating INTEGER, aiScore TEXT, responseTimeMs INTEGER, cost REAL, costCurrency TEXT DEFAULT 'CNY',
                   outputText TEXT, isDelete INTEGER DEFAULT 0)""",
                """CREATE TABLE model_profile_snapshot (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   modelName TEXT, taskType TEXT, qualityScore REAL, latencyScore REAL,
                   costScore REAL, reliabilityScore REAL, sampleCount INTEGER, evaluationRunId TEXT,
                   publishedAt TEXT, createTime TEXT, updateTime TEXT,
                   UNIQUE(modelName, taskType))""",
            ):
                await connection.execute(text(ddl))
        self.publisher = AsyncMock(side_effect=lambda profiles: {"updated": len(profiles), "unchanged": 0})
        self.publisher_patch = patch("app.services.model_profile_service.GatewayClient.publish_profiles", self.publisher)
        self.publisher_patch.start()
        self.settings_patch = patch.object(get_settings(), "PROFILE_AUTO_UPDATE_MIN_SAMPLES", 3)
        self.settings_patch.start()

    async def asyncTearDown(self):
        self.publisher_patch.stop()
        self.settings_patch.stop()
        await self.engine.dispose()

    async def add_batch(self, task_id, count=3, *, model="model-a", task_type="code",
                        status="completed", deleted=0, rating=5, total=None, completed=None):
        async with self.sessions() as db:
            await db.execute(text("""INSERT INTO test_task
                (id, config, status, isDelete, totalSubtasks, completedSubtasks)
                VALUES (:id, :config, :status, :deleted, :total, :completed)"""), {
                    "id": task_id, "config": json.dumps({"taskType": task_type}),
                    "status": status, "deleted": deleted,
                    "total": count if total is None else total,
                    "completed": count if completed is None else completed,
                })
            for index in range(count):
                await db.execute(text("""INSERT INTO test_result
                    (id, taskId, modelName, userRating, responseTimeMs, cost, outputText)
                    VALUES (:id, :task, :model, :rating, 100, 0.01, 'answer')"""), {
                        "id": f"{task_id}-{index}", "task": task_id, "model": model, "rating": rating,
                    })
            await db.commit()

    async def rebuild(self, automatic=True):
        async with self.sessions() as db:
            return await SQLiteProfileService(db).rebuild_and_publish(automatic=automatic)

    async def snapshots(self):
        async with self.sessions() as db:
            return await SQLiteProfileService(db).list_snapshots()

    async def test_complete_batch_publishes_once_and_survives_new_session(self):
        await self.add_batch("first")
        first = await self.rebuild()
        second = await self.rebuild()
        self.assertEqual(first["published"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.publisher.assert_awaited_once()
        self.assertIsNotNone((await self.snapshots())[0]["publishedAt"])

    async def test_small_batches_accumulate_per_model_and_task_type(self):
        await self.add_batch("code1", count=2)
        await self.add_batch("math", count=2, task_type="math")
        await self.add_batch("other", count=2, model="model-b")
        self.assertEqual((await self.rebuild())["published"], 0)
        await self.add_batch("code2", count=1)
        self.assertEqual((await self.rebuild())["published"], 1)
        payload = self.publisher.call_args.args[0]
        self.assertEqual([(p["model"], p["task_type"], p["sample_count"]) for p in payload],
                         [("model-a", "code", 3)])

    async def test_running_failed_cancelled_deleted_and_incomplete_batches_are_excluded(self):
        for status in ("pending", "running", "failed", "cancelled"):
            await self.add_batch(status, status=status)
        await self.add_batch("deleted", deleted=1)
        await self.add_batch("missing-result", count=2, total=3, completed=3)
        await self.add_batch("early-status", count=3, total=3, completed=2)
        self.assertEqual((await self.rebuild())["published"], 0)
        self.publisher.assert_not_awaited()

    async def test_unscored_results_wait_for_later_ratings(self):
        await self.add_batch("unscored", rating=None)
        self.assertEqual((await self.rebuild())["published"], 0)
        async with self.sessions() as db:
            await db.execute(text("UPDATE test_result SET userRating=4"))
            await db.commit()
        self.assertEqual((await self.rebuild())["published"], 1)

    async def test_timeout_retries_same_generation_and_accepts_gateway_noop(self):
        await self.add_batch("batch")
        self.publisher.side_effect = [TimeoutError("ack lost"), {"updated": 0, "unchanged": 1}]
        with self.assertRaises(TimeoutError):
            await self.rebuild()
        self.assertIsNone((await self.snapshots())[0]["publishedAt"])
        self.assertEqual((await self.rebuild())["published"], 1)
        sent = [call.args[0][0]["evaluation_run_id"] for call in self.publisher.call_args_list]
        self.assertEqual(sent[0], sent[1])
        self.assertIsNotNone((await self.snapshots())[0]["publishedAt"])

    async def test_partial_gateway_acceptance_is_not_marked_published(self):
        await self.add_batch("batch")
        self.publisher.return_value = {"updated": 0, "unchanged": 0, "missing": ["model-a"]}
        self.publisher.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "accepted 0/1"):
            await self.rebuild()
        self.assertIsNone((await self.snapshots())[0]["publishedAt"])

    async def test_rating_change_creates_generation_and_clears_old_publish_marker(self):
        await self.add_batch("batch")
        old = await self.rebuild()
        async with self.sessions() as db:
            await db.execute(text("UPDATE test_result SET userRating=1"))
            await db.commit()
        self.publisher.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            await self.rebuild()
        snapshot = (await self.snapshots())[0]
        self.assertNotEqual(snapshot["evaluationRunId"], old["evaluationRunId"])
        self.assertAlmostEqual(snapshot["qualityScore"], 0.2)
        self.assertIsNone(snapshot["publishedAt"])

    async def test_manual_rebuild_bypasses_automatic_sample_gate(self):
        await self.add_batch("small", count=1)
        self.assertEqual((await self.rebuild())["published"], 0)
        self.assertEqual((await self.rebuild(automatic=False))["published"], 1)


class BatchCoordinatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_all_workers_before_single_feedback(self):
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = threading.Event()

        def worker(data):
            if data["slow"]:
                loop.call_soon_threadsafe(started.set)
                release.wait(timeout=5)
            return {"resultId": "saved-with-score"}

        with patch("app.jobs.model_profile_job.update_model_profiles_job", new_callable=AsyncMock) as publish:
            task = asyncio.create_task(run_batch("batch", [{"slow": False}, {"slow": True}], worker))
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                publish.assert_not_awaited()
            finally:
                release.set()
                await task
            publish.assert_awaited_once()

    async def test_failed_and_skipped_workers_do_not_publish(self):
        for result in (ValueError("provider failed"), {"skipped": True}, {"error": "missing task"}):
            def worker(data):
                if isinstance(result, Exception):
                    raise result
                return result
            with patch("app.jobs.model_profile_job.update_model_profiles_job", new_callable=AsyncMock) as publish:
                await run_batch("batch", [{}], worker)
                publish.assert_not_awaited()

    async def test_disabled_auto_update_does_not_open_database(self):
        with patch.object(get_settings(), "PROFILE_AUTO_UPDATE_ENABLED", False), \
             patch("app.jobs.model_profile_job.AsyncSessionLocal") as sessions:
            await update_model_profiles_job()
            sessions.assert_not_called()

    async def test_feedback_failure_is_isolated_from_batch(self):
        session = AsyncMock()
        with patch("app.jobs.model_profile_job.AsyncSessionLocal", return_value=session), \
             patch("app.jobs.model_profile_job.ModelProfileService") as service, \
             patch("app.jobs.model_profile_job.logger"):
            service.return_value.rebuild_and_publish = AsyncMock(side_effect=TimeoutError())
            await update_model_profiles_job()
            service.return_value.rebuild_and_publish.assert_awaited_once_with(automatic=True)

    async def test_mysql_publication_lock_is_released_on_failure(self):
        db = MagicMock()
        connection = AsyncMock()
        connection.scalar.return_value = 1
        db.bind.connect.return_value.__aenter__.return_value = connection
        service = ModelProfileService(db)
        with self.assertRaises(ValueError):
            async with service._publication_lock() as acquired:
                self.assertTrue(acquired)
                raise ValueError("failed publish")
        self.assertIn("RELEASE_LOCK", str(connection.execute.call_args.args[0]))

    async def test_busy_mysql_lock_defers_without_querying_results(self):
        db = MagicMock()
        connection = AsyncMock()
        connection.scalar.return_value = 0
        db.bind.connect.return_value.__aenter__.return_value = connection
        result = await ModelProfileService(db).rebuild_and_publish(automatic=True)
        self.assertTrue(result["busy"])
        db.execute.assert_not_called()
        connection.execute.assert_not_awaited()


class ProfileInputTest(unittest.TestCase):
    def test_task_type_alias_survives_request_parsing(self):
        request = CreateBatchTestRequest(sceneId="scene", models=["model"], taskType="code")
        self.assertEqual(request.model_dump()["task_type"], "code")

    def test_zero_score_counts_but_nonfinite_score_does_not(self):
        self.assertEqual(parse_ai_scores('{"averageRating": 0}')[0], 0)
        self.assertIsNone(parse_ai_scores('{"averageRating": "NaN"}')[0])


class BatchCompletionTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""CREATE TABLE test_task (id TEXT, status TEXT, completedSubtasks INTEGER,
            totalSubtasks INTEGER, startedAt TEXT, completedAt TEXT, isDelete INTEGER DEFAULT 0)""")
        self.addCleanup(self.db.close)

    def test_only_final_result_completes_the_batch(self):
        self.db.execute("INSERT INTO test_task VALUES ('batch', 'pending', 0, 3, NULL, NULL, 0)")
        for completed in range(1, 4):
            self.db.execute(str(COMPLETE_SUBTASK_SQL), {"task_id": "batch"})
            status, count, timestamp = self.db.execute(
                "SELECT status, completedSubtasks, completedAt FROM test_task").fetchone()
            self.assertEqual(count, completed)
            self.assertEqual(status, "completed" if completed == 3 else "running")
            self.assertEqual(timestamp is not None, completed == 3)

    def test_late_success_does_not_overwrite_failure_or_cancellation(self):
        for status in ("failed", "cancelled"):
            self.db.execute("INSERT INTO test_task VALUES (?, ?, 2, 3, NULL, NULL, 0)", (status, status))
            self.db.execute(str(COMPLETE_SUBTASK_SQL), {"task_id": status})
            row = self.db.execute("SELECT status, completedAt FROM test_task WHERE id=?", (status,)).fetchone()
            self.assertEqual(row, (status, None))


if __name__ == "__main__":
    unittest.main()
