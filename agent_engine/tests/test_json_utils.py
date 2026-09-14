"""json_utils 单元测试：LLM 输出的 JSON 解析与兜底

背景：标准 LLM（非 JSON Mode）常把 JSON 包在 Markdown 代码块里返回，
解析失败必须有默认值兜底，否则整条管线崩掉。
"""
from utils.json_utils import safe_parse_json


class TestSafeParseJson:
    def test_plain_json(self):
        assert safe_parse_json('{"intent": "order_service", "confidence": 0.9}') == {
            "intent": "order_service",
            "confidence": 0.9,
        }

    def test_strips_json_code_fence(self):
        text = '```json\n{"intent": "chitchat"}\n```'
        assert safe_parse_json(text) == {"intent": "chitchat"}

    def test_strips_plain_code_fence(self):
        text = '```\n{"intent": "escalate"}\n```'
        assert safe_parse_json(text) == {"intent": "escalate"}

    def test_handles_surrounding_whitespace(self):
        assert safe_parse_json('\n\n  {"a": 1}  \n') == {"a": 1}

    def test_returns_default_on_invalid_json(self):
        default = {"total_score": 60, "needs_escalation": False}

        assert safe_parse_json("模型输出了一段自然语言，不是 JSON", default=default) == default

    def test_returns_empty_dict_when_default_omitted(self):
        assert safe_parse_json("not json at all") == {}

    def test_parses_nested_quality_payload(self):
        text = '```json\n{"total_score": 88, "needs_escalation": false, "reason": "回答完整"}\n```'

        parsed = safe_parse_json(text)

        assert parsed["total_score"] == 88
        assert parsed["needs_escalation"] is False
        assert parsed["reason"] == "回答完整"
