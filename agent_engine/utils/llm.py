"""
LLM 工厂

统一创建大语言模型实例，所有配置从 config 读取。
所有 LLM 实例统一带容错：
1. with_retry：网络类异常与限流自动重试（指数退避 + 抖动）
2. with_fallbacks：重试耗尽后切换备用模型（额度 403 按模型计，备用模型可续命）
"""
from langchain.chat_models import init_chat_model
from openai import APIConnectionError, RateLimitError
from core.config import settings

# 统一注入思考开关，具体模型由 .env 的 LLM_MODEL_NAME 决定
_EXTRA_BODY = {"enable_thinking": settings.ENABLE_THINKING}


def _with_retry(model):
    """给 LLM 实例挂重试：网络/限流类异常指数退避重试 3 次"""
    return model.with_retry(
        retry_if_exception_type=(APIConnectionError, RateLimitError),
        wait_exponential_jitter=True,
        stop_after_attempt=3,
    )


def _with_fallback(model, temperature: float | None = None, model_kwargs: dict | None = None,
                   reasoning_effort: str | None = None, extra_body: dict | None = None):
    """挂备用模型：主模型重试耗尽后自动切换

    温度、思考强度、额外参数必须一起传：备用模型不带同样的设置，
    降级后的行为和速度会突然变化，JSON 模式也可能失效。
    """
    backup = init_chat_model(
        settings.LLM_BACKUP_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        model_kwargs=model_kwargs or {},
        reasoning_effort=reasoning_effort,
        extra_body=extra_body or _EXTRA_BODY,
    )
    return model.with_fallbacks([backup])


def _create(model_name: str, temperature: float | None = None):
    """按模型名创建实例，统一挂重试与备用模型"""
    model = init_chat_model(
        model_name,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        reasoning_effort=settings.REASONING_EFFORT,
        extra_body=_EXTRA_BODY,
    )
    return _with_fallback(_with_retry(model), temperature,
                          reasoning_effort=settings.REASONING_EFFORT,
                          extra_body=_EXTRA_BODY)


def create_llm(temperature: float | None = None):
    """创建 LLM 实例，temperature 为 None 则使用默认配置"""
    return _create(settings.LLM_MODEL_NAME, temperature)


def create_fast_llm(temperature: float | None = None):
    """创建轻量模型实例（分类 / 打分这类短输出任务）

    LLM_FAST_MODEL_NAME 未配置时回落到主模型，行为与改造前完全一致。
    """
    return _create(settings.LLM_FAST_MODEL_NAME or settings.LLM_MODEL_NAME, temperature)


def create_fast_json_llm():
    """JSON Mode 的轻量模型（前台接待：意图分类 + 回复，输出短 JSON）"""
    kwargs = {"response_format": {"type": "json_object"}}
    model = init_chat_model(
        settings.LLM_FAST_MODEL_NAME or settings.LLM_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        model_kwargs=kwargs,
        reasoning_effort=settings.REASONING_EFFORT,
        extra_body=_EXTRA_BODY,
    )
    return _with_fallback(_with_retry(model), model_kwargs=kwargs,
                          reasoning_effort=settings.REASONING_EFFORT,
                          extra_body=_EXTRA_BODY)


def create_raw_llm(temperature: float | None = None):
    """创建不带 retry/fallback 包装的原始模型实例

    用于 create_agent / create_deep_agent：Agent 框架的 model 参数
    要求 BaseChatModel（需要 bind_tools），with_retry 包装的
    RunnableRetry 类型不兼容。Agent 场景的重试改用
    ModelRetryMiddleware 中间件，在框架内部包装模型调用。
    """
    return init_chat_model(
        settings.LLM_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        reasoning_effort=settings.REASONING_EFFORT,
        extra_body=_EXTRA_BODY,
    )


def create_json_llm():
    """创建 JSON Mode 的 LLM 实例（用于 Coordinator，保证输出为合法 JSON）"""
    kwargs = {"response_format": {"type": "json_object"}}
    model = init_chat_model(
        settings.LLM_MODEL_NAME,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        model_kwargs=kwargs,
        reasoning_effort=settings.REASONING_EFFORT,
        extra_body=_EXTRA_BODY,
    )
    return _with_fallback(_with_retry(model), model_kwargs=kwargs,
                          reasoning_effort=settings.REASONING_EFFORT,
                          extra_body=_EXTRA_BODY)
