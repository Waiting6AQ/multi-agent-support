"""
多 Agent 客服聊天路由

提供两个端点：
- POST /api/v1/chat        → 非流式，一次返回完整结果
- POST /api/v1/chat/stream → 流式 SSE，逐步返回意图→回复→质量评分
"""
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from core.concurrency import AsyncConcurrencyLimiter
from core.dependencies import (
    get_agent_service,
    get_conversation_service,
    get_chat_limiter,
)
from models.chat import ChatRequest, ChatResponse
from services.agent_service import AgentService
from services.conversation_service import ConversationService

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="多 Agent 客服对话（非流式）",
    description="发送消息，系统自动识别意图并路由到对应 Agent，返回回复、意图、质量评分。",
)
async def chat(
    request: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
    conv: ConversationService = Depends(get_conversation_service),
    limiter: AsyncConcurrencyLimiter = Depends(get_chat_limiter),
) -> ChatResponse:
    # 并发闸门：整个多 Agent 管线算一个在途请求，排队超时抛 429
    async with limiter:
        result = await agent.chat(
            message=request.message,
            conversation_id=request.conversation_id,
        )
        # 更新对话摘要侧边栏（写入 PG）
        await conv.upsert(
            conv_id=result.conversation_id,
            title=request.message[:80],
        )
    return result


@router.post(
    "/chat/stream",
    summary="多 Agent 客服对话（流式 SSE）",
    description="与 /chat 功能相同，但以 Server-Sent Events 格式逐步返回。"
                "事件类型：progress → intent → token → done。",
)
async def chat_stream(
    request: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
    conv: ConversationService = Depends(get_conversation_service),
    limiter: AsyncConcurrencyLimiter = Depends(get_chat_limiter),
):
    # 许可必须在构造 StreamingResponse 之前拿：拿不到时还能正常返回 429 JSON；
    # 等流开始之后再拒绝，HTTP 状态码已经发出去了，前端只会看到半截流。
    await limiter.acquire()
    try:
        # 预先确定对话 ID，记录到侧边栏
        cid = request.conversation_id or str(uuid.uuid4())
        await conv.upsert(
            conv_id=cid,
            title=request.message[:80],
        )

        stream = agent.chat_stream(message=request.message, conversation_id=cid)

        async def guarded_stream():
            """流式生成器：无论正常结束、报错还是客户端断开，都归还许可"""
            try:
                async for chunk in stream:
                    yield chunk
            finally:
                limiter.release()

        return StreamingResponse(
            guarded_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except BaseException:
        # 拿到许可后、流启动前就失败（建会话 / 构造生成器抛错）：立刻归还再抛
        limiter.release()
        raise
