"""
JSON 解析工具

安全解析 LLM 返回的 JSON，处理 Markdown 代码块包裹的情况。
"""
import json


def safe_parse_json(text: str, default: dict | None = None) -> dict:
    """安全解析 JSON，自动剥离 ```json ... ``` 包裹"""
    if default is None:
        default = {}
    content = text.strip()
    if "```json" in content:
        try:
            content = content.split("```json")[1].split("```")[0]
        except IndexError:
            pass
    elif "```" in content:
        try:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
        except IndexError:
            pass
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default
