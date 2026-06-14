"""
依赖注入模块

管理所有单例组件的创建和注入。FastAPI 的 Depends() 支持 sync/async 函数，
async 依赖会自动被 await。

单例模式：通过模块级缓存变量确保昂贵资源只初始化一次。
"""
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_chroma import Chroma

from core.config import settings
from utils.llm import create_llm, create_json_llm, create_search_llm
from utils.embeddings import AliyunEmbeddings
from services.quality_checker import QualityChecker
from services.conversation_service import ConversationService
from services.agent_service import AgentService
from agents.tech_support import TechSupportAgent
from agents.order_service import OrderServiceAgent
from agents.product_consult import ProductConsultAgent
from agents.receptionist import ReceptionistAgent
from agents.web_search import WebSearchAgent

# ==================== 模块级缓存 ====================

_embeddings = None
_llm = None
_chroma_for_faq = None
_checkpointer = None
_json_llm = None
_receptionist = None
_quality_checker = None
_tech_agent = None
_order_agent = None
_product_agent = None
_search_llm = None
_web_agent = None
_agent_service = None
_conversation_service = None


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
    """FAQ 检索用 ChromaDB 实例"""
    global _chroma_for_faq
    if _chroma_for_faq is None:
        _chroma_for_faq = Chroma(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            embedding_function=get_embeddings(),
        )
    return _chroma_for_faq


async def get_checkpointer() -> AsyncSqliteSaver:
    """AsyncSqliteSaver 单例，支持 astream/ainvoke 等异步操作"""
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect(settings.CHECKPOINT_DB_PATH)
        _checkpointer = AsyncSqliteSaver(conn)
    return _checkpointer


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
            llm=get_llm(),
            chroma_store=get_chroma_for_faq(),
        )
    return _tech_agent


def get_order_agent() -> OrderServiceAgent:
    """订单服务 Agent 单例"""
    global _order_agent
    if _order_agent is None:
        _order_agent = OrderServiceAgent(
            llm=get_llm(),
            db_path=settings.APP_DB_PATH,
        )
    return _order_agent


def get_product_agent() -> ProductConsultAgent:
    """产品咨询 Agent 单例"""
    global _product_agent
    if _product_agent is None:
        _product_agent = ProductConsultAgent(
            llm=get_llm(),
            db_path=settings.APP_DB_PATH,
        )
    return _product_agent


def get_search_llm():
    """联网搜索专用 LLM 单例（开启 enable_search + agent_max）"""
    global _search_llm
    if _search_llm is None:
        _search_llm = create_search_llm()
    return _search_llm


def get_web_agent() -> WebSearchAgent:
    """联网搜索 Agent 单例"""
    global _web_agent
    if _web_agent is None:
        _web_agent = WebSearchAgent(search_llm=get_search_llm())
    return _web_agent


async def get_agent_service() -> AgentService:
    """多 Agent 服务单例（依赖异步 checkpointer）"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(
            llm=get_llm(),
            checkpointer=await get_checkpointer(),
            receptionist=get_receptionist(),
            quality_checker=get_quality_checker(),
            tech_agent=get_tech_agent(),
            order_agent=get_order_agent(),
            product_agent=get_product_agent(),
            web_agent=get_web_agent(),
        )
    return _agent_service


def get_conversation_service() -> ConversationService:
    """对话元数据服务单例"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService(db_path=settings.APP_DB_PATH)
    return _conversation_service
