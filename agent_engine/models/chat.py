"""
聊天 / 多 Agent 客服相关 Pydantic 模型
"""
from pydantic import BaseModel, Field


# ---------- 请求 ----------
class ChatRequest(BaseModel):
    """客服对话请求体"""
    message: str = Field(
        ...,
        min_length=1,
        description="用户消息",
    )
    conversation_id: str | None = Field(
        None,
        description="对话ID，不传则新建对话",
    )


# ---------- 响应 ----------
class ChatResponse(BaseModel):
    """客服对话完整响应"""
    conversation_id: str
    reply: str                                    # Agent 最终回复
    intent: str                                   # 识别的意图
    confidence: float                             # 意图置信度 0-1
    quality_score: float                          # 质量评分 0-1
    escalated: bool                               # 是否转人工
    escalation_reason: str | None = None          # 转人工原因
