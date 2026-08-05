"""Aggregate benchmark outcomes and publish capability profiles to the gateway."""

from __future__ import annotations

import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway_client import GatewayClient
from app.scoring.profile_scoring import build_profiles


class ModelProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def rebuild_and_publish(self, evaluation_run_id: str | None = None) -> dict:
        run_id = evaluation_run_id or uuid.uuid4().hex
        result = await self.db.execute(text("""
            SELECT tr.modelName AS model_name, tr.userRating AS user_rating, tr.aiScore AS ai_score,
                   tr.responseTimeMs AS latency, tr.cost AS cost, tr.outputText AS output_text,
                   tt.config AS task_config
            FROM test_result tr
            LEFT JOIN test_task tt ON tt.id = tr.taskId
            WHERE tr.isDelete = 0
        """))
        observations = [dict(row._mapping) for row in result]
        if not observations:
            return {"evaluationRunId": run_id, "profiles": 0, "published": 0}

        profiles = build_profiles(observations, run_id)
        for profile in profiles:
            await self.db.execute(text("""
                INSERT INTO model_profile_snapshot
                  (modelName, taskType, qualityScore, latencyScore, costScore, reliabilityScore,
                   sampleCount, evaluationRunId, createTime, updateTime)
                VALUES
                  (:model, :task_type, :quality_score, :latency_score, :cost_score, :reliability_score,
                   :sample_count, :evaluation_run_id, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                  qualityScore=VALUES(qualityScore), latencyScore=VALUES(latencyScore),
                  costScore=VALUES(costScore), reliabilityScore=VALUES(reliabilityScore),
                  sampleCount=VALUES(sampleCount), evaluationRunId=VALUES(evaluationRunId), updateTime=NOW()
            """), profile)
        await self.db.commit()
        published = await GatewayClient().publish_profiles(profiles)
        await self.db.execute(text("""
            UPDATE model_profile_snapshot SET publishedAt=NOW()
            WHERE evaluationRunId=:run_id
        """), {"run_id": run_id})
        await self.db.commit()
        return {"evaluationRunId": run_id, "profiles": len(profiles), "published": published.get("updated", 0)}

    async def list_snapshots(self) -> list[dict]:
        result = await self.db.execute(text("""
            SELECT modelName, taskType, qualityScore, latencyScore, costScore,
                   reliabilityScore, sampleCount, evaluationRunId, publishedAt, updateTime
            FROM model_profile_snapshot ORDER BY updateTime DESC
        """))
        return [dict(row._mapping) for row in result]
