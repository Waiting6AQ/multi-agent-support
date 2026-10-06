"""
依赖注入模块

管理所有单例组件的创建和注入。FastAPI 的 Depends() 支持 sync/async 函数，
async 依赖会自动被 await。

单例模式：通过模块级缓存变量确保昂贵资源只初始化一次。
"""
import asyncio
import threading
import time

from langchain_chroma import Chroma

from core.config import settings, MCP_SERVERS
from core.database import get_session_factory
# checkpointer 的实现与连接池在 core/postgres.py（这里只做转发，保持依赖注入入口统一）
from core.postgres import get_checkpointer  # noqa: F401
from utils.llm import create_llm, create_json_llm, create_raw_llm
from utils.embeddings import AliyunEmbeddings
from services.quality_checker import QualityChecker
from services.conversation_service import ConversationService
from services.agent_service import AgentService
from agents.tech_support import TechSupportAgent
from agents.order_service import OrderServiceAgent
from agents.product_consult import ProductConsultAgent
from agents.receptionist import ReceptionistAgent
from agents.web_search import WebSearchAgent
from langchain_mcp_adapters.client import MultiServerMCPClient

# ==================== 模块级缓存 ====================

_embeddings = None
_llm = None
_chroma_for_faq = None
_json_llm = None
_receptionist = None
_quality_checker = None
_tech_agent = None
_order_agent = None
_product_agent = None
_web_agent = None
_agent_service = None
_conversation_service = None

# MCP 加载失败后的冷却：冷却期内直接用降级实例，不再去撞网络
_web_agent_retry_after = 0.0
MCP_RETRY_COOLDOWN = 60.0       # 秒

# 两种锁各管一类，不能混用：
# - threading.Lock 给同步单例（Chroma 的 PersistentClient 并发创建会破坏其进程级注册表）
# - asyncio.Lock 给异步单例（构造里有 await，用 threading.Lock 会阻塞事件循环）
_singleton_lock = threading.Lock()
_service_init_lock = asyncio.Lock()


# ==================== 基础组件 ====================

def get_embeddings() -> AliyunEmbeddings:
    """嵌入模型单例"""
    global _embeddings
    if _embeddings is None:
        _embeddings = AliyunEmbeddings(model=settings.EMBEDDING_MODEL_NAME)
    return _embeddings


def get_llm():
    """LLM 单例"""
    global _llm
    if _llm is None:
        _llm = create_llm()
    return _llm


def get_chroma_for_faq():
    """FAQ 检索用 ChromaDB 实例

    双重检查 + 锁：sync 依赖跑在线程池里，并发首次请求会同时走到 check-then-act，
    两个线程对同一路径并发创建 PersistentClient 会破坏 chromadb 的进程级注册表
    （此后进程内所有 Chroma 操作全废）。
    """
    global _chroma_for_faq
    if _chroma_for_faq is None:
        with _singleton_lock:
            if _chroma_for_faq is None:
                _chroma_for_faq = Chroma(
                    persist_directory=settings.CHROMA_PERSIST_DIR,
                    embedding_function=get_embeddings(),
                )
    return _chroma_for_faq


# ==================== 业务组件 ====================

def get_json_llm():
    """JSON Mode LLM 单例（用于 ReceptionistAgent）"""
    global _json_llm
    if _json_llm is None:
        _json_llm = create_json_llm()
    return _json_llm


def get_receptionist() -> ReceptionistAgent:
    """前台接待 Agent 单例"""
    global _receptionist
    if _receptionist is None:
        _receptionist = ReceptionistAgent(json_llm=get_json_llm())
    return _receptionist


def get_quality_checker() -> QualityChecker:
    """质量检查器单例"""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = QualityChecker(llm=get_llm())
    return _quality_checker


def get_tech_agent() -> TechSupportAgent:
    """技术支持 Agent 单例"""
    global _tech_agent
    if _tech_agent is None:
        _tech_agent = TechSupportAgent(
            # create_deep_agent 不兼容 with_retry 包装对象，
            # 用原始模型实例，重试由 Deep Agents 内置机制处理
            llm=create_raw_llm(),
            chroma_store=get_chroma_for_faq(),
        )
    return _tech_agent


def get_order_agent() -> OrderServiceAgent:
    """订单服务 Agent 单例"""
    global _order_agent
    if _order_agent is None:
        _order_agent = OrderServiceAgent(
            # Agent 框架需要模型支持 bind_tools，retry 包装对象不支持
            llm=create_raw_llm(),
            session_factory=get_session_factory(),
        )
    return _order_agent


def get_product_agent() -> ProductConsultAgent:
    """产品咨询 Agent 单例"""
    global _product_agent
    if _product_agent is None:
        _product_agent = ProductConsultAgent(
            llm=create_raw_llm(),
            session_factory=get_session_factory(),
        )
    return _product_agent


def _describe_exc(e: BaseException) -> str:
    """把异常压成一行可读文本。

    MCP 客户端用 anyio 的 TaskGroup 并发连接，失败时抛的是 ExceptionGroup——
    直接 str() 只会得到 "unhandled errors in a TaskGroup (1 sub-exception)"，
    看不出真因，所以要把子异常递归挖出来。
    """
    subs = getattr(e, "exceptions", None)
    if subs:
        return "; ".join(_describe_exc(s) for s in subs)
    return f"{type(e).__name__}: {e}"


async def _get_mcp_tools(server_names: list[str] | None = None) -> list:
    """获取指定 MCP Server 的工具列表

    不做模块级缓存——get_web_agent 自身已有单例缓存。
    server_names：None 获取全部，传列表则只连指定服务。
    """
    servers = {
        k: v
        for k, v in MCP_SERVERS.items()
        if server_names is None or k in server_names
    }
    client = MultiServerMCPClient(servers)
    return await client.get_tools()


async def get_web_agent() -> WebSearchAgent:
    """联网搜索 Agent 单例（注入百度搜索 MCP 工具）

    MCP 是外部服务，连不上时降级为空工具列表（Agent 会告知用户无法搜索）。
    但降级**不是永久的**：失败后只冷却 MCP_RETRY_COOLDOWN 秒，
    之后的下一次调用会重新去连——否则一次网络抖动就让整个进程生命周期内
    都失去联网搜索，只能重启恢复。
    """
    global _web_agent, _web_agent_retry_after

    # 正常路径：已拿到带工具的实例
    if _web_agent is not None and _web_agent.tools:
        return _web_agent

    # 降级中且还在冷却期：先用现成的降级实例顶着，不打网络
    if _web_agent is not None and time.monotonic() < _web_agent_retry_after:
        return _web_agent

    try:
        mcp_tools = await _get_mcp_tools(server_names=["baidu_search"])
    except Exception as e:
        # 降级而非抛出：Agent 按系统提示词告知用户无法搜索，整个管线不崩
        _web_agent_retry_after = time.monotonic() + MCP_RETRY_COOLDOWN
        print(f"⚠️ MCP 工具加载失败，联网搜索降级"
              f"（{MCP_RETRY_COOLDOWN:.0f}s 后重试）: {_describe_exc(e)}")
        mcp_tools = []

    _web_agent = WebSearchAgent(llm=create_raw_llm(), tools=mcp_tools)
    return _web_agent


async def get_agent_service() -> AgentService:
    """多 Agent 服务单例（依赖异步 checkpointer）

    双重检查 + 异步锁：构造过程里有 await（取 checkpointer、MCP 握手），
    事件循环会在 await 处切走，并发首次请求就会各建一整套
    ——每个都做一次 MCP 握手，表现为请求被莫名拖慢。
    """
    global _agent_service
    if _agent_service is None:
        async with _service_init_lock:
            if _agent_service is None:      # 等锁期间可能已被别的请求建好
                _agent_service = AgentService(
                    llm=get_llm(),
                    checkpointer=await get_checkpointer(),
                    receptionist=get_receptionist(),
                    quality_checker=get_quality_checker(),
                    tech_agent=get_tech_agent(),
                    order_agent=get_order_agent(),
                    product_agent=get_product_agent(),
                    web_agent=await get_web_agent(),
                )
    return _agent_service


def get_conversation_service() -> ConversationService:
    """对话元数据服务单例（会话工厂由 lifespan 初始化的引擎提供）"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService(session_factory=get_session_factory())
    return _conversation_service
