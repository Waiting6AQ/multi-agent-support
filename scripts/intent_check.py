"""
意图分类质量检查 — 换轻量模型前后跑同一批用例，确认路由没退化

前台接待（receptionist）决定了每个请求交给哪个专科 Agent。它换模型的风险
不是"回答变差"，而是"路由错了"——技术问题被送去查订单，用户会明显感到答非所问。

用法：

    python scripts/intent_check.py
    python scripts/intent_check.py --url http://127.0.0.1:8001/api/v1/chat
"""
import argparse
import json
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = _SCRIPT_DIR / "intent_cases.json"


def _disp_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _disp_width(text))


def ask(url: str, message: str, timeout: float) -> dict:
    body = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise SystemExit(f"请求失败 HTTP {e.code}: {detail}")
    except Exception as e:
        raise SystemExit(f"请求失败: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="意图分类质量检查")
    # 127.0.0.1 而不是 localhost：Windows 上 IPv6 回退会多花约 2 秒
    parser.add_argument("--url", default="http://127.0.0.1:8001/api/v1/chat",
                        help="非流式聊天接口地址")
    parser.add_argument("--cases", default=str(DEFAULT_CASES),
                        help="用例 JSON 路径")
    parser.add_argument("--timeout", type=float, default=180, help="单请求超时（秒）")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit("用例为空")

    print("=== 意图分类质量检查 ===")
    print(f"目标: {args.url}")
    print(f"用例: {len(cases)} 条\n")

    header = (f"{_pad('#', 4)}{_pad('期望', 16)}{_pad('实际', 16)}"
              f"{_pad('置信度', 10)}{_pad('质量分', 10)}{_pad('转人工', 10)}结论")
    print(header)
    print("-" * _disp_width(header))

    passed = 0
    failures: list[tuple[str, str, str, str]] = []

    for i, case in enumerate(cases, start=1):
        expected = case["expected"]
        try:
            data = ask(args.url, case["message"], args.timeout)
        except SystemExit as e:
            print(f"{_pad(str(i), 4)}{_pad(expected, 16)}{_pad('ERR', 16)}"
                  f"{_pad('-', 10)}{_pad('-', 10)}FAIL")
            failures.append((case["message"], expected, "ERR", str(e)))
            continue

        actual = data.get("intent", "?")
        confidence = data.get("confidence")
        quality = data.get("quality_score")
        escalated = data.get("escalated")
        ok = actual == expected
        passed += ok

        print(f"{_pad(str(i), 4)}{_pad(expected, 16)}{_pad(actual, 16)}"
              f"{_pad(f'{confidence:.2f}' if isinstance(confidence, (int, float)) else '-', 10)}"
              f"{_pad(f'{quality:.2f}' if isinstance(quality, (int, float)) else '-', 10)}"
              f"{_pad('是' if escalated else '否', 10)}"
              f"{'PASS' if ok else 'FAIL'}  {case['message'][:24]}")

        if not ok:
            failures.append((case["message"], expected, actual, data.get("reply", "")[:100]))

    print(f"\n通过 {passed}/{len(cases)}")
    if failures:
        print("\n失败详情：")
        for message, expected, actual, detail in failures:
            print(f"  · {message}\n    期望 {expected}，实际 {actual}；{detail}")

    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
