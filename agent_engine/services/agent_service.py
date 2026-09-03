"""
多 Agent 客服系统 — 核心服务

用 LangGraph 编排完整的多 Agent 客服流程：
  用户消息 → 意图分类 → 条件路由 → 专业 Agent → 质量检查 → 转人工判断

特性：
- 多 Agent 协作：3 个专业 Agent 各配工具，自动路由
- 多轮对话：add_messages 自动追加 + AsyncSqliteSaver 持久化
- 流式输出：SSE 格式，逐阶段返回（意图 → 回复 → 质量评分 → 完成）
"""
import json
import uuid
from typing import TypedDict, Annotated, Any, AsyncGenerator, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.config import get_stream_writer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from core.config import settings
from models.chat import ChatResponse

class AgentState(TypedDict):
    """LangGraph 多 Agent 客服系统状态"""
    messages: Annotated[list, add_messages]      # add_messages 自动管理对话历史
    intent: str                                  # tech_support | order_service | product_consult | escalate
    confidence: float                            # 意图分类置信度 0-1
    agent_response: str                          # 专业 Agent 的回答
    quality_score: float                         # 质量评分 0-1
    needs_escalation: bool                       # 是否需要转人工
    escalation_reason: str                       # 转人工原因


# ==================== Agent 服务类 ====================

class AgentService:
    """
    多 Agent 客服系统总控

    LangGraph 流程：
      START → receptionist → route
        → respond(chitchat/escalate) / tech_support / order_service / product_consult / web_search
        → quality_check → should_escalate → escalate_final / respond → END
    """

    def __init__(self, llm, checkpointer: AsyncSqliteSaver,
                 receptionist, quality_checker,
                 tech_agent, order_agent, product_agent, web_agent):
        self.llm = llm
        self.checkpointer = checkpointer
        self.receptionist = receptionist
        self.quality_checker = quality_checker
        self.tech_agent = tech_agent
        self.order_agent = order_agent
        self.product_agent = product_agent
        self.web_agent = web_agent
        self.graph = self._build_graph()

    # ==================== 构建 LangGraph ====================

    def _build_graph(self):
        """构建多 Agent 客服管线，add_messages 自动管理对话历史"""
        builder = StateGraph(AgentState)

        builder.add_node("receptionist", self._node_receptionist)
        builder.add_node("tech_support", self._node_tech_support)
        builder.add_node("order_service", self._node_order_service)
        builder.add_node("product_consult", self._node_product_consult)
        builder.add_node("web_search", self._node_web_search)
        builder.add_node("quality_check", self._node_quality_check)
        builder.add_node("escalate_final", self._node_escalate_final)
        builder.add_node("respond", self._node_respond)

        builder.add_edge(START, "receptionist")

        builder.add_conditional_edges(
            "receptionist",
            self._route_by_receptionist,
            {
                "tech_support": "tech_support",
                "order_service": "order_service",
                "product_consult": "product_consult",
                "web_search": "web_search",
                "respond": "respond",
            }
        )

        builder.add_edge("tech_support", "quality_check")
        builder.add_edge("order_service", "quality_check")
        builder.add_edge("product_consult", "quality_check")
        builder.add_edge("web_search", "respond")  # 联网搜索结果无法被本地 LLM 验证，跳过质量检查

        builder.add_conditional_edges(
            "quality_check",
            self._should_escalate,
            {
                "escalate_final": "escalate_final",
                "respond": "respond",
            }
        )

        builder.add_edge("escalate_final", END)
        builder.add_edge("respond", END)

        return builder.compile(checkpointer=self.checkpointer)

    # ==================== 节点函数 ====================

    def _node_receptionist(self, state: AgentState) -> dict:
        """节点1：前台接待 — 意图分类 + 闲聊/转人工时直接生成回复"""
        user_msg = state["messages"][-1].content
        writer = get_stream_writer()
        writer({"event": "progress", "data": "前台接待中..."})

        # 构建消息：system + 上一条 AI 回复（帮助理解用户简短的指代追问） + 当前用户消息
        messages = [
            {"role": "system", "content": self.receptionist.SYSTEM_PROMPT},
        ]
        if len(state["messages"]) >= 2:
            prev_ai = state["messages"][-2]  # 上一条是 AIMessage
            messages.append({"role": "assistant", "content": prev_ai.content})
        messages.append({"role": "user", "content": user_msg})
        result = self.receptionist.classify(messages)
        intent = result["intent"]
        confidence = result["confidence"]
        reply = result["reply"]

        writer({"event": "intent", "data": {"intent": intent, "confidence": confidence}})

        # chitchat/escalate：接待员已生成回复，直接返回
        if intent in ("chitchat", "escalate"):
            writer(reply)
            return {
                "intent": intent,
                "confidence": confidence,
                "agent_response": reply,
                "needs_escalation": (intent == "escalate"),
                "escalation_reason": result.get("reason", ""),
                "messages": [AIMessage(content=reply)],
            }

        # 业务意图：reply 是指导语，加换行和后续专业 Agent 回复分隔
        writer(reply + "\n\n")
        return {
            "intent": intent,
            "confidence": confidence,
            "agent_response": reply,  # 指导语，后续专业 Agent 追加
        }

    def _route_by_receptionist(self, state: AgentState) -> Literal[
        "tech_support", "order_service", "product_consult", "web_search", "respond"
    ]:
        """条件路由：chitchat/escalate 已由接待员回复，直接走 respond；业务意图路由到专业 Agent"""
        intent = state["intent"]
        if intent in ("chitchat", "escalate"):
            return "respond"
        if intent in ("tech_support", "order_service", "product_consult", "web_search"):
            return intent
        return "respond"

    async def _node_tech_support(self, state: AgentState) -> dict:
        """节点2a：技术支持 Agent 处理（async — Deep Agent 使用 astream）"""
        writer = get_stream_writer()
        writer({"event": "progress", "data": "技术支持工程师正在处理..."})

        recent = state["messages"][-11:]  # 保留 5 个完整轮次 + 当前问题，防止多轮历史过长
        reply = ""
        async for token in self.tech_agent.handle_stream(recent):
            reply += token
            writer(token)
        return {
            "agent_response": reply,
            "messages": [AIMessage(content=reply)],
        }

    def _node_order_service(self, state: AgentState) -> dict:
        """节点2b：订单服务 Agent 处理（流式逐 token）"""
        writer = get_stream_writer()
        writer({"event": "progress", "data": "订单服务专员正在处理..."})

        recent = state["messages"][-11:]
        reply = ""
        for token in self.order_agent.handle_stream(recent):
            reply += token
            writer(token)
        return {
            "agent_response": reply,
            "messages": [AIMessage(content=reply)],
        }

    def _node_product_consult(self, state: AgentState) -> dict:
        """节点2c：产品咨询 Agent 处理（流式逐 token）"""
        writer = get_stream_writer()
        writer({"event": "progress", "data": "产品顾问正在处理..."})

        recent = state["messages"][-11:]
        reply = ""
        for token in self.product_agent.handle_stream(recent):
            reply += token
            writer(token)
        return {
            "agent_response": reply,
            "messages": [AIMessage(content=reply)],
            "needs_escalation": False,  # 每轮重置，防止上一轮的转人工标记残留
        }

    async def _node_web_search(self, state: AgentState) -> dict:
        """节点2d：联网搜索 Agent 处理（异步 — MCP 工具需要 async 上下文）"""
        writer = get_stream_writer()
        writer({"event": "progress", "data": "正在联网搜索..."})

        recent = state["messages"][-11:]
        reply = ""
        async for token in self.web_agent.handle_stream(recent):
            reply += token
            writer(token)
        return {
            "agent_response": reply,
            "messages": [AIMessage(content=reply)],
            "needs_escalation": False,  # 联网搜索跳过质量检查，手动重置
            "quality_score": 0.0,
        }

    def _node_quality_check(self, state: AgentState) -> dict:
        """节点4：评估 Agent 回复质量"""
        writer = get_stream_writer()
        writer({"event": "progress", "data": "正在检查回复质量..."})

        # messages[-1] 是 Agent 刚追加的 AIMessage，-2 才是用户消息
        user_msg = state["messages"][-2].content
        result = self.quality_checker.check(
            user_msg, state["agent_response"]
        )
        total_score = result.get("total_score", 60)
        # 将百分制转为 0-1
        quality_score = max(0.0, min(1.0, total_score / 100.0))
        needs_escalation = result.get("needs_escalation", False)
        reason = result.get("reason", "")

        return {
            "quality_score": quality_score,
            "needs_escalation": needs_escalation,
            "escalation_reason": reason,
        }

    def _should_escalate(self, state: AgentState) -> Literal[
        "escalate_final", "respond"
    ]:
        """条件路由：质量不达标或 LLM 标记转人工 → escalate_final，否则正常回复"""
        if state.get("needs_escalation", False):
            return "escalate_final"
        if state.get("quality_score", 0.0) < settings.QUALITY_SCORE_THRESHOLD:
            return "escalate_final"
        return "respond"

    def _node_escalate_final(self, state: AgentState) -> dict:
        """节点5a：标记转人工（前端展示横幅，后端不修改回复文字）"""
        return {
            "needs_escalation": True,
        }

    def _node_respond(self, state: AgentState) -> dict:
        """节点5b：正常回复，透传不做修改"""
        return {"needs_escalation": False}

    # ==================== 公开接口 ====================

    async def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        """从 checkpoints 中读取对话消息，转为前端可用格式"""
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.graph.aget_state(config)
        if state and state.values:
            messages = state.values.get("messages", [])
            result = []
            for m in messages:
                entry = {
                    "role": "user" if isinstance(m, HumanMessage) else "assistant",
                    "content": m.content,
                }
                result.append(entry)
            return result
        return []

    async def delete_history(self, thread_id: str):
        """删除对话的 checkpoint 数据，配合 ConversationService 的元数据删除"""
        await self.checkpointer.conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
        )
        await self.checkpointer.conn.execute(
            "DELETE FROM writes WHERE thread_id = ?", (thread_id,)
        )
        await self.checkpointer.conn.commit()

    async def chat(self, message: str, conversation_id: str | None = None
                   ) -> ChatResponse:
        """
        非流式多 Agent 对话

        完整执行管线，返回最终结果。
        AsyncSqliteSaver 自动保存对话状态，同 conversation_id 即可多轮对话。
        """
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": conversation_id}}
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config,
        )

        return ChatResponse(
            conversation_id=conversation_id,
            reply=result.get("agent_response", ""),
            intent=result.get("intent", "unknown"),
            confidence=result.get("confidence", 0.0),
            quality_score=result.get("quality_score", 0.0),
            escalated=result.get("needs_escalation", False),
            escalation_reason=result.get("escalation_reason"),
        )

    async def chat_stream(self, message: str, conversation_id: str | None = None
                          ) -> AsyncGenerator[str, None]:
        """
        流式多 Agent 对话（token 级），返回 SSE 事件流

        事件类型：
          event: progress     → 进度提示
          event: intent       → 意图分类结果
          data: {"token":"x"} → 逐 token 输出
          event: done         → 对话完成（含 conversation_id + intent + quality_score + escalated）
        """
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": conversation_id}}
        input_data = {"messages": [HumanMessage(content=message)]}

        intent_seen = False
        async for chunk in self.graph.astream(input_data, config, stream_mode="custom"):
            if isinstance(chunk, dict):
                event = chunk.get("event")
                if event == "progress":
                    yield f"event: progress\ndata: {json.dumps({'status': chunk['data']}, ensure_ascii=False)}\n\n"
                elif event == "intent":
                    intent_seen = True
                    yield f"event: intent\ndata: {json.dumps(chunk['data'], ensure_ascii=False)}\n\n"
            elif isinstance(chunk, str):
                yield f"data: {json.dumps({'token': chunk})}\n\n"

        # 流结束后取最终状态
        state = await self.graph.aget_state(config)
        intent = "unknown"
        confidence = 0.0
        quality_score = 0.0
        escalated = False
        escalation_reason = ""
        if state and state.values:
            intent = state.values.get("intent", "unknown")
            confidence = state.values.get("confidence", 0.0)
            quality_score = state.values.get("quality_score", 0.0)
            escalated = state.values.get("needs_escalation", False)
            escalation_reason = state.values.get("escalation_reason", "")

        yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id, 'intent': intent, 'confidence': confidence, 'quality_score': quality_score, 'escalated': escalated, 'escalation_reason': escalation_reason}, ensure_ascii=False)}\n\n"
