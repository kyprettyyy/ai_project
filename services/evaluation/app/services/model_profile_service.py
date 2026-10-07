"""Aggregate benchmark outcomes and publish capability profiles to the gateway."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway_client import GatewayClient
from app.core.config import get_settings
from app.scoring.profile_scoring import build_profiles, combined_quality, task_type_from_config


class ModelProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @asynccontextmanager
    async def _publication_lock(self):
        # Keep a dedicated connection checked out: MySQL named locks are connection
        # scoped, while saving snapshots commits/releases the service's session.
        async with self.db.bind.connect() as connection:
            acquired = await connection.scalar(text("SELECT GET_LOCK('evalroute:profile-publish', 0)"))
            try:
                yield acquired == 1
            finally:
                if acquired == 1:
                    await connection.execute(text("SELECT RELEASE_LOCK('evalroute:profile-publish')"))

    async def rebuild_and_publish(self, evaluation_run_id: str | None = None, *, automatic: bool = False) -> dict:
        async with self._publication_lock() as acquired:
            if not acquired:
                return {"evaluationRunId": evaluation_run_id, "profiles": 0, "published": 0, "busy": True}
            try:
                return await self._rebuild_and_publish(evaluation_run_id, automatic=automatic)
            except BaseException:
                await self.db.rollback()
                raise

    async def _rebuild_and_publish(self, evaluation_run_id: str | None, *, automatic: bool) -> dict:
        result = await self.db.execute(text("""
            SELECT tr.id AS result_id, tr.modelName AS model_name,
                   tr.userRating AS user_rating, tr.aiScore AS ai_score,
                   tr.responseTimeMs AS latency, tr.cost AS cost, tr.costCurrency AS cost_currency, tr.outputText AS output_text,
                   tt.config AS task_config
            FROM test_result tr
            JOIN test_task tt ON tt.id = tr.taskId
            WHERE tr.isDelete = 0 AND tt.isDelete = 0 AND tt.status = 'completed'
              AND tt.totalSubtasks > 0 AND tt.completedSubtasks >= tt.totalSubtasks
              AND (SELECT COUNT(*) FROM test_result saved
                   WHERE saved.taskId = tt.id AND saved.isDelete = 0) >= tt.totalSubtasks
            ORDER BY tr.id
        """))
        observations = [dict(row._mapping) for row in result]
        # Stable across retries/restarts; a new batch or changed score creates a new
        # generation. Never include evaluated_at in the content fingerprint.
        digest = hashlib.sha256(json.dumps({"aggregationVersion":"coverage-v3-comparable","observations":observations}, sort_keys=True, default=str).encode()).hexdigest()
        run_id = ("auto-" + digest[:59]) if automatic else (evaluation_run_id or uuid.uuid4().hex)
        if not observations:
            return {"evaluationRunId": run_id, "profiles": 0, "published": 0}

        profiles = build_profiles(observations, run_id)
        skipped = 0
        if automatic:
            scored = Counter(
                (row["model_name"], task_type_from_config(row["task_config"]))
                for row in observations
                if row.get("output_text") and combined_quality(row)["combined"] is not None
            )
            minimum = get_settings().PROFILE_AUTO_UPDATE_MIN_SAMPLES
            eligible = [p for p in profiles if scored[(p["model"], p["task_type"])] >= minimum]
            skipped = len(profiles) - len(eligible)
            profiles = eligible

        snapshots = await self.list_snapshots()
        published_keys = {(s["modelName"], s["taskType"]) for s in snapshots
                          if s["evaluationRunId"] == run_id and s["publishedAt"] is not None}
        pending = [p for p in profiles if not automatic or (p["model"], p["task_type"]) not in published_keys]
        summary = {"evaluationRunId": run_id, "profiles": len(profiles), "published": 0,
                   "skipped": skipped, "unchanged": len(profiles) - len(pending)}
        if not pending:
            return summary

        await self._save_snapshots(pending)
        published = await GatewayClient().publish_profiles(pending)
        accepted = published.get("updated", 0) + published.get("unchanged", 0)
        if accepted != len(pending):
            raise RuntimeError(f"Gateway accepted {accepted}/{len(pending)} profiles; publication will retry")
        await self.db.execute(text("""
            UPDATE model_profile_snapshot SET publishedAt=CURRENT_TIMESTAMP
            WHERE evaluationRunId=:run_id
        """), {"run_id": run_id})
        await self.db.commit()
        summary["published"] = accepted
        return summary

    async def _save_snapshots(self, profiles: list[dict]) -> None:
        # The publication lock serializes writers, including manual rebuilds.
        for profile in profiles:
            exists = await self.db.scalar(text("""
                SELECT id FROM model_profile_snapshot
                WHERE modelName=:model AND taskType=:task_type
            """), profile)
            if exists is not None:
                await self.db.execute(text("""
                    UPDATE model_profile_snapshot SET qualityScore=:quality_score,
                      latencyScore=:latency_score, costScore=:cost_score,
                      reliabilityScore=:reliability_score, sampleCount=:sample_count,
                      evaluationRunId=:evaluation_run_id, publishedAt=NULL,
                      updateTime=CURRENT_TIMESTAMP
                    WHERE modelName=:model AND taskType=:task_type
                """), profile)
                continue
            await self.db.execute(text("""
                INSERT INTO model_profile_snapshot
                  (modelName, taskType, qualityScore, latencyScore, costScore, reliabilityScore,
                   sampleCount, evaluationRunId, createTime, updateTime)
                VALUES
                  (:model, :task_type, :quality_score, :latency_score, :cost_score, :reliability_score,
                   :sample_count, :evaluation_run_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), profile)
        await self.db.commit()

    async def list_snapshots(self) -> list[dict]:
        result = await self.db.execute(text("""
            SELECT modelName, taskType, qualityScore, latencyScore, costScore,
                   reliabilityScore, sampleCount, evaluationRunId, publishedAt, updateTime
            FROM model_profile_snapshot ORDER BY updateTime DESC
        """))
        return [dict(row._mapping) for row in result]
