"""
意图分类器

使用 LLM 分析用户消息，识别意图并返回置信度。
"""
from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.json_utils import safe_parse_json


class IntentClassifier:
    """意图分类：tech_support | order_service | product_consult | web_search | escalate"""

    INTENT_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """你是一个意图分类专家。分析用户消息并返回意图分类。

可选意图：
- tech_support: 技术问题、故障排除、使用帮助、设备问题
- order_service: 订单查询、物流跟踪、退换货、发票
- product_consult: 购物咨询、商品推荐、按预算选品、价格询问、功能对比（购物场景）
- web_search: 查询商品的详细参数规格、市场行情、竞品深度对比、最新价格走势、外部品牌信息（研究场景，需联网搜索才能回答）
- escalate: 投诉、抱怨、无法理解、需要人工客服

区分 product_consult 和 web_search 的关键：
- 用户带着购买意图、在选购商品 → product_consult
- 用户在做研究对比、查询深度信息、了解市场行情 → web_search

返回格式（严格 JSON，不要包含其他内容）：
{{"intent": "意图类型", "confidence": 0.95, "reason": "分类原因简述"}}

confidence 取值参考：
- 0.9-1.0：消息清晰明确，有典型特征词
- 0.7-0.9：基本能判断但略有歧义
- 0.5-0.7：模糊，可能在两个类别之间
- 0.0-0.5：难以判断"""),
        ("human", "{message}")
    ])

    def __init__(self, llm):
        self.llm = llm

    def classify(self, message: str) -> dict[str, Any]:
        """分类用户意图，返回 {intent, confidence, reason}"""
        chain = self.INTENT_PROMPT | self.llm | StrOutputParser()
        result = chain.invoke({"message": message})
        default = {"intent": "escalate", "confidence": 0.5, "reason": "解析失败，默认转人工"}
        parsed = safe_parse_json(result, default)
        if "intent" not in parsed:
            return default
        try:
            parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))
        except (ValueError, TypeError):
            parsed["confidence"] = 0.5
        return parsed
