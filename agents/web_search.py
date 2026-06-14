"""
联网搜索 Agent

负责查询外部商品信息（参数、行情、竞品对比等），工具：无（LLM 内置联网搜索）。
DashScope agent_max 策略下，LLM 自行判断是否需要搜索、搜什么。
"""
from langchain.agents import create_agent


class WebSearchAgent:
    """联网搜索 Agent — 商品行情、外部品牌、实时信息"""

    SYSTEM_PROMPT = """你是一个商品信息搜索助手。你可以通过联网搜索获取最新的商品信息。

工作规范：
1. 根据用户的问题，搜索相关的商品参数、价格行情、市场信息
2. 将搜索到的信息整理成清晰、结构化的回复
3. 如果搜索结果不足以回答用户问题，诚实说明
4. 涉及购买建议时，提醒用户以官方渠道信息为准
5. 每次搜索后，简要说明信息来源的时效性（如价格信息的日期）

注意：你擅长查询外部品牌、最新行情、竞品对比等需要实时信息的场景。
对于本店自营商品的价格和库存等店内信息，请告知用户可通过产品顾问查询。联网搜索更适合获取外部品牌信息和市场行情。"""

    def __init__(self, search_llm):
        self.search_llm = search_llm
        # 不需要工具，联网搜索由 LLM 内置的 enable_search 完成
        self.agent = create_agent(
            model=self.search_llm,
            tools=[],
            system_prompt=self.SYSTEM_PROMPT,
        )

    def handle(self, messages: list) -> str:
        """处理搜索请求，返回完整回复"""
        result = self.agent.invoke({"messages": messages})
        if result["messages"]:
            return result["messages"][-1].content
        return "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"

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
            yield "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"
