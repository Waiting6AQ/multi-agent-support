"""
FAQ 管理相关 Pydantic 模型

只服务管理接口（增删改查）；技术支持 Agent 的检索走 services/faq_service.py 的 search()。
"""
from typing import Annotated

from pydantic import BaseModel, StringConstraints

# 去首尾空白并拒绝空串："   " 不该被当成一条 FAQ
FaqText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FaqInfo(BaseModel):
    """一条 FAQ（不含向量）"""
    id: int
    question: str
    answer: str
    category: str


class FaqListResponse(BaseModel):
    """FAQ 列表响应"""
    total: int
    faqs: list[FaqInfo]


class FaqRequest(BaseModel):
    """新增 / 修改 FAQ 的请求体"""
    question: FaqText
    answer: FaqText
    category: FaqText = "常见问题"


class FaqDeleteResponse(BaseModel):
    """删除 FAQ 的响应"""
    id: int
    status: str = "deleted"
