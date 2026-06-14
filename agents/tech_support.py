"""
技术支持 Agent

负责技术问题、故障排除，工具：search_faq（ChromaDB 向量检索）。
"""
from langchain_core.tools import tool
from langchain.agents import create_agent


class TechSupportAgent:
    """技术支持工程师 Agent"""

    SYSTEM_PROMPT = """你是一个专业的技术支持工程师。你的职责是帮助用户解决产品使用中的技术问题。

工作规范：
1. 先用 search_faq 工具搜索相关常见问题
2. 基于 FAQ 结果给出清晰、步骤化的解决方案
3. 如果 FAQ 没有覆盖用户的问题，给出你的专业建议并建议联系人工客服
4. 回复要专业、耐心、易懂，避免使用过于专业的术语

注意：你只能处理技术支持和故障排除类问题。"""

    def __init__(self, llm, chroma_store):
        self.llm = llm
        self.chroma_store = chroma_store

        @tool
        def search_faq(problem_type: str) -> str:
            """搜索常见技术问题解答，problem_type 为问题类型关键词（如'蓝牙连接''充电''无法开机'等）"""
            docs = self.chroma_store.similarity_search(problem_type, k=3)
            if not docs:
                return "未找到相关FAQ，建议用户拨打客服热线或发送邮件至 support@example.com"
            results = []
            for i, doc in enumerate(docs):
                answer = doc.metadata.get("answer", doc.page_content)
                category = doc.metadata.get("category", "常见问题")
                results.append(f"【{category}】{answer}")
            return "\n---\n".join(results)

        self.agent = create_agent(
            model=self.llm,
            tools=[search_faq],
            system_prompt=self.SYSTEM_PROMPT,
        )

    def handle(self, messages: list) -> str:
        """处理技术支持请求，返回完整回复"""
        result = self.agent.invoke({"messages": messages})
        if result["messages"]:
            return result["messages"][-1].content
        return "抱歉，技术支持服务暂时不可用。请拨打客服热线 400-xxx-xxxx 获取帮助。"

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
            yield "抱歉，技术支持服务暂时不可用。请拨打客服热线 400-xxx-xxxx 获取帮助。"
