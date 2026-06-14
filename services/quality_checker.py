"""
质量检查器

评估 Agent 回复质量，决定是否需要升级人工。
"""
from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.json_utils import safe_parse_json


class QualityChecker:
    """客服回复质量评估"""

    QUALITY_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """你是客服质量检查专家。评估客服回复的质量并判断是否需要升级人工。

评估维度（各 25 分，满分 100）：
1. 相关性：回复是否针对用户问题
2. 完整性：是否提供了足够的信息和解决方案
3. 专业性：语言是否专业得体、条理清晰
4. 有用性：是否真正能帮助用户解决问题

需要转人工的情况（needs_escalation = true）：
- 回复答非所问或敷衍了事
- 问题超出客服能力范围
- 用户情绪激动或明确要求人工
- 涉及退换货、投诉等敏感问题但未给出明确流程

返回格式（严格 JSON，不要包含其他内容）：
{{"total_score": 85, "needs_escalation": false, "reason": "评估说明"}}"""),
        ("human", """用户问题：{user_message}
客服回复：{agent_response}

请评估：""")
    ])

    def __init__(self, llm):
        self.llm = llm

    def check(self, user_message: str, agent_response: str) -> dict[str, Any]:
        """检查回复质量，返回 {total_score, needs_escalation, reason}"""
        chain = self.QUALITY_PROMPT | self.llm | StrOutputParser()
        result = chain.invoke({
            "user_message": user_message,
            "agent_response": agent_response,
        })
        default = {"total_score": 60, "needs_escalation": False, "reason": "评估完成"}
        return safe_parse_json(result, default)
