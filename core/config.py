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
    LLM_MODEL_NAME: str = "openai:qwen3-max"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL_NAME: str = "text-embedding-v4"

    # === Agent 参数 ===
    TEMPERATURE: float = 0.1
    MAX_TOKENS: int = 2000
    INTENT_CONFIDENCE_THRESHOLD: float = 0.6  # 意图置信度低于此值直接转人工
    QUALITY_SCORE_THRESHOLD: float = 0.6      # 质量评分低于此值升级人工
    FAQ_TOP_K: int = 3                        # FAQ 向量检索返回数量

    # === 存储路径（基于项目根目录） ===
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "chroma_db")
    CHECKPOINT_DB_PATH: str = str(BASE_DIR / "data" / "checkpoints.db")
    APP_DB_PATH: str = str(BASE_DIR / "data" / "app.db")

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


# 全局配置单例
settings = Settings()
