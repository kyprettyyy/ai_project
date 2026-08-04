"""
AI 评分相关请求/响应模型
"""
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """
    单次 AI 评分结果（单评委）
    """
    scores: Dict[str, int] = Field(default_factory=dict, description="各维度分数 accuracy/relevance/completeness/clarity/creativity")
    total_score: int = Field(..., alias="total_score", description="总分(100分制)")
    rating: int = Field(..., description="评级(1-10)")
    comment: str = Field("", description="简短评价")

    class Config:
        populate_by_name = True


class JudgeScore(BaseModel):
    """
    评委评分结果（多评委时每个评委一条）
    """
    model: str = Field(..., description="评委模型名称")
    scores: Dict[str, int] = Field(default_factory=dict, description="各维度分数")
    total_score: int = Field(..., alias="totalScore", description="总分")
    rating: int = Field(..., description="评级(1-10)")
    comment: str = Field("", description="评委评语")

    class Config:
        populate_by_name = True


class AIScoreResult(BaseModel):
    """
    AI 评分结果（多评委汇总）
    """
    judges: List[JudgeScore] = Field(default_factory=list, description="各评委评分列表")
    average_rating: float = Field(..., alias="averageRating", description="平均评级")
    consistency: float = Field(0.0, description="一致性(标准差)")

    class Config:
        populate_by_name = True


def ai_score_result_to_json(ai_score_result: AIScoreResult) -> str:
    """
    将 AIScoreResult 序列化为 JSON 字符串，用于写入 test_result.aiScore。
    """
    return json.dumps(ai_score_result.model_dump(by_alias=True), ensure_ascii=False)
