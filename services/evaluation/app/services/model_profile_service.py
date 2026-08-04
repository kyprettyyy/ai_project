"""Aggregate benchmark outcomes and publish capability profiles to the gateway."""

from __future__ import annotations

import uuid
import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway_client import GatewayClient


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

        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in observations:
            task_type = "general"
            try:
                task_type = json.loads(row.get("task_config") or "{}").get("taskType", "general")
            except (TypeError, json.JSONDecodeError):
                pass
            groups[(row["model_name"], task_type)].append(row)

        aggregates: list[dict] = []
        for (model, task_type), items in groups.items():
            quality_values: list[float] = []
            for item in items:
                human = float(item["user_rating"]) / 5.0 if item.get("user_rating") is not None else None
                judge = None
                try:
                    judge_payload = json.loads(item.get("ai_score") or "{}")
                    judge = float(judge_payload.get("averageRating")) / 10.0 if judge_payload.get("averageRating") is not None else None
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
                if human is not None and judge is not None:
                    quality_values.append(0.4 * human + 0.6 * judge)
                elif human is not None or judge is not None:
                    quality_values.append(human if human is not None else judge)
            aggregates.append({
                "model": model, "task_type": task_type, "sample_count": len(items),
                "quality": sum(quality_values) / len(quality_values) if quality_values else 0.5,
                "latency": sum(float(item.get("latency") or 0) for item in items) / len(items),
                "cost": sum(float(item.get("cost") or 0) for item in items) / len(items),
                "reliability": sum(1 for item in items if item.get("output_text")) / len(items),
            })

        max_latency = max(row["latency"] for row in aggregates) or 1.0
        max_cost = max(row["cost"] for row in aggregates) or 0.000001
        profiles: list[dict] = []
        for row in aggregates:
            profile = {
                "model": row["model"],
                "task_type": row["task_type"],
                "quality_score": round(float(row["quality"]), 4),
                "latency_score": round(max(0.0, 1.0 - float(row["latency"] or 0) / max_latency), 4),
                "cost_score": round(max(0.0, 1.0 - float(row["cost"] or 0) / max_cost), 4),
                "reliability_score": round(float(row["reliability"] or 0), 4),
                "sample_count": int(row["sample_count"]),
                "evaluation_run_id": run_id,
                "evaluated_at": datetime.utcnow().isoformat(),
            }
            profiles.append(profile)
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
