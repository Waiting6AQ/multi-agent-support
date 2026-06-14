"""
前台接待 Agent（ReceptionistAgent）

统一接待用户，同时完成意图识别和自然语言回复。
利用 DashScope JSON Mode 保证输出为合法 JSON，一次 LLM 调用完成分类 + 闲聊。
"""
import json


class ReceptionistAgent:
    """前台接待员：判断意图 + 生成回复，JSON Mode 保证结构化输出"""

    SYSTEM_PROMPT = """你是客服前台接待员。分析用户消息并返回 JSON。

可选意图：
- chitchat: 问候、闲聊、自我介绍、表示感谢
- tech_support: 技术问题、故障排除、使用帮助
- order_service: 订单查询、物流跟踪、退换货
- product_consult: 产品咨询、价格询问、购买推荐
- web_search: 外部品牌查询、详细参数、市场行情、竞品对比
- escalate: 投诉、抱怨、非本店业务、无法理解

返回格式（严格 JSON）：
{"intent": "意图类型", "reply": "你的自然语言回复", "confidence": 0.0-1.0, "reason": "判断依据"}

规则：
- chitchat: reply 要友好、自然、简短，引导用户说明需求
- 业务意图（tech_support/order_service/product_consult/web_search）: reply 为一句简短安抚话术如"好的，帮您处理"
- escalate: reply 要表达歉意和转人工说明
- confidence 准确反映你的把握，不确定时低于 0.6"""

    def __init__(self, json_llm):
        self.llm = json_llm  # JSON Mode 的 LLM 实例

    def classify(self, messages: list) -> dict:
        """一次调用完成意图分类 + 回复生成，返回 {intent, reply, confidence, reason}"""
        result = self.llm.invoke(messages)
        data = json.loads(result.content)
        return {
            "intent": data.get("intent", "escalate"),
            "reply": data.get("reply", ""),
            "confidence": data.get("confidence", 0.5),
            "reason": data.get("reason", ""),
        }
