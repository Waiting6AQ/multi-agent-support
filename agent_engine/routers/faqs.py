"""
FAQ 管理路由

只服务后台维护（增删改查）；技术支持 Agent 的检索走 services 层，不经过这里。
鉴权在 Java 网关上做（四个接口都标了 @RequireAdmin），引擎不暴露端口。
"""
from fastapi import APIRouter, Depends

from core.dependencies import get_faq_service
from models.faq import (
    FaqDeleteResponse,
    FaqInfo,
    FaqListResponse,
    FaqRequest,
)
from services.faq_service import FaqService

router = APIRouter()


@router.get(
    "/",
    response_model=FaqListResponse,
    summary="列出全部 FAQ",
)
async def list_faqs(
    service: FaqService = Depends(get_faq_service),
) -> FaqListResponse:
    faqs = await service.list_all()
    return FaqListResponse(total=len(faqs), faqs=faqs)


@router.post(
    "/",
    response_model=FaqInfo,
    status_code=201,
    summary="新增 FAQ",
    description="问题文本是业务唯一标识，重复时返回 409。",
)
async def create_faq(
    req: FaqRequest,
    service: FaqService = Depends(get_faq_service),
) -> FaqInfo:
    faq_id = await service.create(req.question, req.answer, req.category)
    return FaqInfo(
        id=faq_id, question=req.question, answer=req.answer, category=req.category
    )


@router.put(
    "/{faq_id}",
    response_model=FaqInfo,
    summary="修改 FAQ",
    description="问题变了会重算向量；id 不存在返回 404。",
)
async def update_faq(
    faq_id: int,
    req: FaqRequest,
    service: FaqService = Depends(get_faq_service),
) -> FaqInfo:
    await service.update(faq_id, req.question, req.answer, req.category)
    return FaqInfo(
        id=faq_id, question=req.question, answer=req.answer, category=req.category
    )


@router.delete(
    "/{faq_id}",
    response_model=FaqDeleteResponse,
    summary="删除 FAQ",
)
async def delete_faq(
    faq_id: int,
    service: FaqService = Depends(get_faq_service),
) -> FaqDeleteResponse:
    await service.delete(faq_id)
    return FaqDeleteResponse(id=faq_id)
