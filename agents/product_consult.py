"""
产品咨询 Agent

负责产品搜索、推荐，工具：search_product、get_recommendations（SQLite 查询）。
"""
import json
import sqlite3
from langchain_core.tools import tool
from langchain.agents import create_agent


class ProductConsultAgent:
    """产品顾问 Agent"""

    SYSTEM_PROMPT = """你是一个热情的产品顾问。你的职责是帮助用户了解和选购产品。

工作规范：
1. 理解用户的需求和预算
2. 使用 search_product 搜索具体产品信息
3. 使用 get_recommendations 根据预算推荐合适产品
4. 回复要突出产品亮点，帮助用户做出购买决策
5. 如果用户预算有限，优先推荐高性价比产品

注意：所有产品信息以工具查询结果为准，不要编造产品信息。如果本地数据库查不到用户要找的商品，诚实告知后必须在回复末尾明确建议：
"您可以说联网搜索XXXX，我会帮您转接联网搜索Agent查询该商品的外部信息。"""

    def __init__(self, llm, db_path: str):
        self.llm = llm
        self.db_path = db_path

        @tool
        def search_product(keyword: str) -> str:
            """搜索产品信息，keyword: 产品名称关键词"""
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM products WHERE name LIKE ?", (f"%{keyword}%",)
            ).fetchall()
            conn.close()
            if rows:
                results = []
                for r in rows:
                    item = dict(r)
                    if isinstance(item.get("features"), str):
                        item["features"] = json.loads(item["features"])
                    results.append(item)
                return json.dumps(results, ensure_ascii=False, indent=2)
            return f"未找到包含 '{keyword}' 的产品，试试搜索'手表'、'耳机'、'充电宝'、'音箱'"

        @tool
        def get_recommendations(budget: float, category: str = "") -> str:
            """根据预算和品类推荐产品，budget: 预算金额（元），category: 品类如'穿戴设备''音频''电源''智能家居'（可选）"""
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    "SELECT * FROM products WHERE price <= ? AND category = ? ORDER BY rating DESC LIMIT 3",
                    (budget, category),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM products WHERE price <= ? ORDER BY rating DESC LIMIT 3",
                    (budget,),
                ).fetchall()
            conn.close()
            if rows:
                results = []
                for r in rows:
                    item = dict(r)
                    if isinstance(item.get("features"), str):
                        item["features"] = json.loads(item["features"])
                    results.append(item)
                return json.dumps(results, ensure_ascii=False, indent=2)
            return f"在预算 ¥{budget} 内暂无推荐产品，建议适当提高预算或换个品类看看"

        self.agent = create_agent(
            model=self.llm,
            tools=[search_product, get_recommendations],
            system_prompt=self.SYSTEM_PROMPT,
        )

    def handle(self, messages: list) -> str:
        """处理产品咨询请求，返回完整回复"""
        result = self.agent.invoke({"messages": messages})
        if result["messages"]:
            return result["messages"][-1].content
        return "抱歉，产品咨询服务暂时不可用。请稍后再试或联系人工客服。"

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
            yield "抱歉，产品咨询服务暂时不可用。请稍后再试或联系人工客服。"
