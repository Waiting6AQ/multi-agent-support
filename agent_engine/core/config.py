"""
应用配置模块

通过 pydantic-settings 自动加载 .env 文件和环境变量，
所有配置集中管理，其他模块导入 settings 单例即可。
"""
from pathlib import Path
from pydantic_settings import BaseSettings

# 项目根目录，基于当前文件位置推算，不受启动位置影响
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置，属性名与 .env 变量名一一对应"""

    # === DashScope API（阿里云） ===
    DASHSCOPE_API_KEY: str
    LLM_MODEL_NAME: str = "openai:qwen3.7-max-2026-06-08"
    LLM_BACKUP_MODEL_NAME: str = "openai:qwen3.7-max-2026-05-20"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL_NAME: str = "qwen3.7-text-embedding"

    # === 百度千帆 API（联网搜索 MCP 鉴权） ===
    # 默认空串：未配置时 MCP 连不上走降级，不影响服务启动
    QIANFAN_API_KEY: str = ""

    # === Agent 参数 ===
    TEMPERATURE: float = 0.1
    MAX_TOKENS: int = 2000
    INTENT_CONFIDENCE_THRESHOLD: float = 0.6  # 意图置信度低于此值直接转人工
    QUALITY_SCORE_THRESHOLD: float = 0.6      # 质量评分低于此值升级人工
    FAQ_TOP_K: int = 3                        # FAQ 向量检索返回数量

    # === PostgreSQL（会话状态 + 业务数据） ===
    # 必填：不配则启动即报错（fail-fast，与 DASHSCOPE_API_KEY 一致）
    # 本地开发连 localhost；容器内由 compose 注入服务名 postgres（见 docker-compose.yml）
    POSTGRES_DSN: str
    PG_POOL_MIN: int = 2           # psycopg 池下限（LangGraph checkpoint 用）
    PG_POOL_MAX: int = 10          # psycopg 池上限

    # === 存储路径（基于项目根目录） ===
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "chroma_db")
    SKILLS_DIR: str = str(BASE_DIR / "skills")

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


# 全局配置单例
settings = Settings()

# MCP Server 注册表 — 所有接入的 MCP 服务统一在此配置
# 新增服务只需加一个条目，无需改依赖注入代码
# 注："baidu_search" 是本地服务别名（仅用于筛选连接哪个服务），不是工具名
MCP_SERVERS = {
    "baidu_search": {
        "transport": "streamable_http",
        "url": "https://qianfan.baidubce.com/v2/tools/web-search/mcp",
        # 千帆官方 MCP 需 Bearer 鉴权；Key 从 .env 读取，不写死在代码里
        "headers": {"Authorization": f"Bearer {settings.QIANFAN_API_KEY}"},
    },
}
