"""
LLM 工厂

统一创建大语言模型实例，所有配置从 config 读取。
"""
from langchain.chat_models import init_chat_model
from core.config import settings


def create_llm(temperature: float | None = None):
    """创建 LLM 实例，temperature 为 None 则使用默认配置"""
    return init_chat_model(
        settings.LLM_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
    )


def create_json_llm():
    """创建 JSON Mode 的 LLM 实例（用于 Coordinator，保证输出为合法 JSON）"""
    return init_chat_model(
        settings.LLM_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
