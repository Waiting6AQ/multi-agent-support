"""
订单服务 Agent

负责订单查询、物流跟踪，工具：query_order、track_shipping（SQLite 查询）。
"""
import json
import sqlite3
from langchain_core.tools import tool
from langchain.agents import create_agent


class OrderServiceAgent:
    """订单服务专员 Agent"""

    SYSTEM_PROMPT = """你是一个专业的订单服务专员。你的职责是帮助用户查询订单状态和物流信息。

工作规范：
1. 先理解用户的需求：是查订单状态还是查物流？
2. 使用对应的工具查询信息
3. 将查询结果用友好、清晰的方式告知用户
4. 如果用户没有提供订单号，主动询问订单号或物流单号

可用的订单号格式：ORD001、ORD002、ORD003"""

    def __init__(self, llm, db_path: str):
        self.llm = llm
        self.db_path = db_path

        def _query_db(sql: str, params: tuple) -> dict | None:
            """查询订单数据，返回字典或 None"""
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, params).fetchone()
            conn.close()
            return dict(row) if row else None

        @tool
        def query_order(order_id: str) -> str:
            """查询订单信息，order_id 格式如 ORD001、ORD002"""
            order = _query_db("SELECT * FROM orders WHERE id = ?", (order_id.upper(),))
            if order:
                return json.dumps(order, ensure_ascii=False, indent=2)
            return f"未找到订单 {order_id}，请确认订单号是否正确"

        @tool
        def track_shipping(tracking_number: str) -> str:
            """按物流单号查询物流信息，tracking_number 如 SF1234567890"""
            order = _query_db("SELECT * FROM orders WHERE tracking = ?", (tracking_number,))
            if not order:
                return f"未找到物流单号 {tracking_number} 对应的物流信息"
            return json.dumps({
                "tracking": order["tracking"],
                "carrier": order["shipping"],
                "status": order["status"],
                "estimated_delivery": order["estimated_delivery"],
                "order_id": order["id"],
                "product": order["product"],
            }, ensure_ascii=False, indent=2)

        self.agent = create_agent(
            model=self.llm,
            tools=[query_order, track_shipping],
            system_prompt=self.SYSTEM_PROMPT,
        )

    def handle(self, messages: list) -> str:
        """处理订单服务请求，返回完整回复"""
        result = self.agent.invoke({"messages": messages})
        if result["messages"]:
            return result["messages"][-1].content
        return "抱歉，订单查询服务暂时不可用。请稍后再试或联系人工客服。"

    def handle_stream(self, messages: list):
        """流式处理，逐 token 返回（用于 SSE 打字机效果）"""
        had_content = False
        for chunk in self.agent.stream(
            {"messages": messages},
            stream_mode="messages",
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                msg = chunk[0]
                if hasattr(msg, "content") and msg.content:
                    if getattr(msg, "type", "") != "tool":
                        had_content = True
                        yield msg.content
        if not had_content:
            yield "抱歉，订单查询服务暂时不可用。请稍后再试或联系人工客服。"
