"""四个业务 Agent 共用的流式输出逻辑

把 messages 流过滤成"只有正文 token"，并在模型发起工具调用时回调一次
（供调用方在工具执行期间显示进度）。
"""
import inspect
from collections.abc import AsyncGenerator, Callable
from typing import Any


async def stream_agent_tokens(
    agent: Any,
    messages: list,
    on_tool_call: Callable[[], Any] | None = None,
) -> AsyncGenerator[str, None]:
    """逐 token 吐出正文；模型发起工具调用时回调一次 on_tool_call

    工具返回的消息（type == "tool"）跳过——那是给模型看的原始结果，不进正文。
    on_tool_call 同步/异步都支持；工具调用分多个 chunk 到达，用标志保证只回调一次。
    """
    searching = False
    async for chunk in agent.astream({"messages": messages}, stream_mode="messages"):
        if not (isinstance(chunk, tuple) and len(chunk) == 2):
            continue
        msg = chunk[0]
        if getattr(msg, "type", "") == "tool":
            continue
        if getattr(msg, "content", ""):
            searching = False
            yield msg.content
        elif getattr(msg, "tool_call_chunks", None) and not searching:
            searching = True
            if on_tool_call is not None:
                result = on_tool_call()
                if inspect.isawaitable(result):
                    await result
