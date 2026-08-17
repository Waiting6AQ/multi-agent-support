"""
联网搜索 Agent

通过百度搜索 MCP 服务实现免费联网检索。
MCP Server: mcpmarket.cn 百度搜索，Streamable HTTP 协议接入。
Agent 运行时动态发现 baidu_web_search 工具，自主决定是否调用。
MCP 工具是纯异步的，因此 Agent 使用 astream/ainvoke。
"""
from langchain.agents import create_agent


class WebSearchAgent:
    """联网搜索 Agent — 商品行情、外部品牌、实时信息"""

    SYSTEM_PROMPT = """你是一个商品信息搜索助手。你可以通过百度搜索获取最新的商品信息。

工作规范：
1. 根据用户的问题，使用 baidu_web_search 工具搜索相关的商品参数、价格行情、市场信息
2. 将搜索到的信息整理成清晰、结构化的回复
3. 如果搜索结果不足以回答用户问题，诚实说明
4. 涉及购买建议时，提醒用户以官方渠道信息为准
5. 每次搜索后，简要说明信息来源的时效性（如价格信息的日期）
6. 需要获取最新实时信息时，使用 freshness 参数过滤时间

注意：你擅长查询外部品牌、最新行情、竞品对比等需要实时信息的场景。
对于本店自营商品的价格和库存等店内信息，请告知用户可通过产品顾问查询。"""

    def __init__(self, llm, tools: list):
        self.tools = tools
        self.agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def handle(self, messages: list) -> str:
        """处理搜索请求，返回完整回复"""
        if not self.tools:
            # MCP 工具加载失败（启动时降级）：直接短路，不浪费 LLM 调用
            return "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"
        try:
            result = await self.agent.ainvoke({"messages": messages})
            if result["messages"]:
                return result["messages"][-1].content
        except Exception as e:
            print(f"⚠️ 联网搜索 Agent 异常: {type(e).__name__}: {e}")
        return "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"

    async def handle_stream(self, messages: list):
        """流式处理（async — MCP 工具需要异步上下文执行 HTTP 调用）"""
        if not self.tools:
            # MCP 工具加载失败（启动时降级）：直接短路，不浪费 LLM 调用
            yield "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"
            return
        had_content = False
        try:
            async for chunk in self.agent.astream(
                {"messages": messages},
                stream_mode="messages",
            ):
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    msg = chunk[0]
                    if hasattr(msg, "content") and msg.content:
                        if getattr(msg, "type", "") != "tool":
                            had_content = True
                            yield msg.content
        except Exception as e:
            # MCP 服务中途不可用时降级：已有部分内容照常输出
            print(f"⚠️ 联网搜索 Agent 异常: {type(e).__name__}: {e}")
        if not had_content:
            yield "抱歉，联网搜索暂时不可用。请稍后再试或联系人工客服。"
