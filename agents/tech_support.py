"""
技术支持 Agent

负责技术问题、故障排除。
- 工具：search_faq（ChromaDB FAQ 向量检索）
- Skill：support-workflow（完整工作流：FAQ 检索 → 分支 → 结构化排查）
使用 Deep Agents 框架的 SkillsMiddleware 实现渐进式披露。
"""
from langchain_core.tools import tool
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from core.config import settings


AGENT_SKILLS_DIR = settings.SKILLS_DIR + "/tech_support"


class TechSupportAgent:
    """技术支持工程师 Agent"""

    SYSTEM_PROMPT = """你是一个专业的技术支持工程师。
先用 search_faq 检索常见问题，如果检索到结果，直接回复用户。
如果未找到匹配结果，加载对应 Skill 并按其中的排查流程处理。
回复要专业、耐心、易懂。"""

    def __init__(self, llm, chroma_store):
        self.chroma_store = chroma_store

        @tool
        def search_faq(problem_type: str) -> str:
            """搜索常见技术问题解答，problem_type 为问题类型关键词（如'蓝牙连接''充电''无法开机'等）"""
            docs = self.chroma_store.similarity_search(problem_type, k=3)
            if not docs:
                return "FAQ 未找到匹配结果。"
            results = []
            for i, doc in enumerate(docs):
                answer = doc.metadata.get("answer", doc.page_content)
                category = doc.metadata.get("category", "常见问题")
                results.append(f"【{category}】{answer}")
            return "\n---\n".join(results)

        self.agent = create_deep_agent(
            model=llm,
            tools=[search_faq],
            backend=FilesystemBackend(root_dir=AGENT_SKILLS_DIR, virtual_mode=True),
            skills=[AGENT_SKILLS_DIR],
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def handle(self, messages: list) -> str:
        """处理技术支持请求，返回完整回复"""
        result = await self.agent.ainvoke({"messages": messages})
        if result["messages"]:
            return result["messages"][-1].content
        return "抱歉，技术支持服务暂时不可用。请拨打客服热线 400-xxx-xxxx 获取帮助。"

    async def handle_stream(self, messages: list):
        """流式处理（async — Deep Agent 使用 astream）"""
        had_content = False
        async for chunk in self.agent.astream(
            {"messages": messages},
            stream_mode="messages",
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                msg = chunk[0]
                if hasattr(msg, "content") and msg.content:
                    had_content = True
                    yield msg.content
        if not had_content:
            yield "抱歉，技术支持服务暂时不可用。请拨打客服热线 400-xxx-xxxx 获取帮助。"
