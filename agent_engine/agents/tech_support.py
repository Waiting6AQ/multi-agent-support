"""
技术支持 Agent

负责技术问题、故障排除。
- 工具：search_faq（ChromaDB FAQ 向量检索）
- Skill：support-workflow（完整工作流：FAQ 检索 → 分支 → 结构化排查）
使用 Deep Agents 框架的 SkillsMiddleware 实现渐进式披露。
"""
from langchain_core.tools import tool
from langchain.agents.middleware import ModelRetryMiddleware
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from core.config import settings
from agents._stream import stream_agent_tokens


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
            # skills 的路径必须相对于 backend 的 root，不能传绝对路径：
            # 虚拟模式下 backend 会对路径做 lstrip("/")，绝对路径的斜杠被削掉后
            # 降级成相对路径、拼到 root 后面变成不存在的嵌套路径（Linux 上必然失败）。
            # Windows 上因为 pathlib 拼接时"右边是绝对路径则丢弃左边"而侥幸能用，
            # 所以本地测不出来。root_dir 本身就是 tech_support 技能目录，用 "/" 指向它
            skills=["/"],
            system_prompt=self.SYSTEM_PROMPT,
            middleware=[
                ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
            ],
        )

    async def handle(self, messages: list) -> str:
        """处理技术支持请求，返回完整回复"""
        try:
            result = await self.agent.ainvoke({"messages": messages})
            if result["messages"]:
                return result["messages"][-1].content
        except Exception as e:
            print(f"⚠️ 技术支持 Agent 异常: {type(e).__name__}: {e}")
        return "抱歉，技术支持服务暂时不可用。请稍后重试，或拨打客服热线 400-xxx-xxxx 获取帮助。"

    async def handle_stream(self, messages: list, on_tool_call=None):
        """流式处理（async — Deep Agent 使用 astream）"""
        had_content = False
        try:
            async for text in stream_agent_tokens(self.agent, messages, on_tool_call):
                had_content = True
                yield text
        except Exception as e:
            print(f"⚠️ 技术支持 Agent 异常: {type(e).__name__}: {e}")
        if not had_content:
            yield "抱歉，技术支持服务暂时不可用。请稍后重试，或拨打客服热线 400-xxx-xxxx 获取帮助。"
