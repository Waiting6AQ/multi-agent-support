"""
多 Agent 客服流式性能测量 — 从 SSE 事件时间线还原各阶段耗时

不需要在引擎里加代码：引擎本来就会推送 progress / intent / token / done 事件，
本脚本给每个事件的到达时刻打时间戳，反推出每个节点的耗时。

事件与阶段的对应关系（业务意图）：

    t0  请求发出
    t1  progress: 前台接待中                  → 接待员开始
    t2  event: intent                         → 接待员分类结束
    t3  引导语 token（"好的，帮您处理"）        → 首 token（用户第一次看到反馈）
    t4  progress: 技术支持工程师正在处理 …     → 专科 Agent 开始
    t5  第一个回答 token                       → 专科首 token
    t6  最后一个回答 token                     → 专科结束
    t7  progress: 正在检查回复质量             → 质量检查开始
    t8  event: done                           → 整轮完成

    接待     = t2 - t1      专科 = t6 - t4      质量 = t8 - t7
    TTFT     = t3 - t0      专科首 token = t5 - t0      总耗时 = t8 - t0

闲聊 / 转人工没有专科和质量检查阶段，对应项为空。

用法：

    # 引擎直连（默认）
    python scripts/perf_timeline.py --tag baseline

    # 打网关（端到端校验，需要登录）
    python scripts/perf_timeline.py --tag baseline-gateway \
        --url http://127.0.0.1:8082/api/chat/stream \
        --username admin --password 你的密码

说明：
- 串行发请求，每题用新的 conversation_id（首轮、无历史）
- 只依赖 Python 标准库
"""
import argparse
import json
import math
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = _SCRIPT_DIR / "perf_questions.json"

# 阶段在报告里的显示名（顺序即表格顺序）
PHASES = [
    ("receptionist", "前台接待"),
    ("specialist", "专科 Agent"),
    ("quality", "质量检查"),
    ("other", "其他/未归类"),
]
METRICS = [
    ("ttft", "首 token(TTFT)"),
    ("answer_ttft", "专科首 token"),
    ("total", "总耗时"),
]


# ==================== 终端对齐 ====================

def _disp_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _disp_width(text))


# ==================== HTTP ====================

def login(base_url: str, username: str, password: str) -> str:
    """用账号密码换 JWT（网关的 /api/auth/login 不需要鉴权）"""
    login_url = urllib.parse.urljoin(base_url, "/api/auth/login")
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(login_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise SystemExit(f"登录失败 HTTP {e.code}: {detail}")
    except Exception as e:
        raise SystemExit(f"登录失败: {e}")
    token = (data.get("data") or {}).get("token")
    if not token:
        raise SystemExit(f"登录响应里没有 token: {data}")
    return token


def one_request(url: str, field: str, prompt: str, token: str | None,
                timeout: float) -> dict:
    """发一条流式请求，返回事件时间线（t 为相对请求发出的秒数）"""
    body = json.dumps({field: prompt}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream, application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    started = time.perf_counter()
    events: list[dict] = []
    event_type = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_type, data_lines
        if data_lines:
            raw = "\n".join(data_lines)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw
            events.append({
                "t": time.perf_counter() - started,
                "event": event_type,
                "data": payload,
            })
        event_type = "message"
        data_lines = []

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    flush()
                elif line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            flush()
            return {"ok": True, "status": status, "events": events, "error": ""}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        return {"ok": False, "status": e.code, "events": events, "error": detail}
    except Exception as e:
        return {"ok": False, "status": "ERR", "events": events, "error": repr(e)[:200]}


# ==================== 时间线 → 阶段耗时 ====================

def derive_phases(result: dict) -> dict:
    """从事件时间线推导各阶段耗时（单位：秒）"""
    marks: dict[str, float] = {}
    first_token = None
    answer_first = None
    last_token = None
    intent = None

    for e in result["events"]:
        t = e["t"]
        event = e["event"]
        data = e["data"]

        if event == "progress":
            status = data.get("status", "") if isinstance(data, dict) else ""
            if status.startswith("前台接待中"):
                marks.setdefault("receptionist_start", t)
            elif status.startswith("正在检查回复质量"):
                marks.setdefault("quality_start", t)
            elif "正在处理" in status or status.startswith("正在联网搜索"):
                marks.setdefault("specialist_start", t)
        elif event == "intent":
            marks.setdefault("intent", t)
            if isinstance(data, dict):
                intent = data.get("intent")
        elif event == "message" and isinstance(data, dict) and "token" in data:
            if first_token is None:
                first_token = t
            if "specialist_start" in marks and answer_first is None and t > marks["specialist_start"]:
                answer_first = t
            last_token = t
        elif event == "done":
            marks.setdefault("done", t)

    def diff(end: str, start: str) -> float | None:
        if end in marks and start in marks:
            return marks[end] - marks[start]
        return None

    total = marks.get("done")
    if total is None and result["events"]:
        total = result["events"][-1]["t"]

    specialist = None
    if "specialist_start" in marks and last_token is not None:
        specialist = last_token - marks["specialist_start"]

    return {
        "receptionist": diff("intent", "receptionist_start"),
        "specialist": specialist,
        "quality": diff("done", "quality_start"),
        "ttft": first_token,
        "answer_ttft": answer_first,
        "total": total,
        "intent": intent,
        "has_specialist": "specialist_start" in marks,
        "has_quality": "quality_start" in marks,
    }


def add_other(phases: dict) -> None:
    """其他 = 总耗时 - 已知阶段之和"""
    known = [phases.get(k) for k in ("receptionist", "specialist", "quality")]
    if phases.get("total") is None or any(v is None for v in known):
        phases["other"] = None
        return
    phases["other"] = max(0.0, phases["total"] - sum(known))


def dump_events(events: list[dict]) -> None:
    """打印事件时间线（token 只显示首尾）"""
    token_count = 0
    last_token_t = None
    for e in events:
        data = e["data"]
        if e["event"] == "message" and isinstance(data, dict) and "token" in data:
            token_count += 1
            last_token_t = e["t"]
            if token_count == 1:
                print(f"    +{e['t']:8.3f}s  {'token':<10} 第一个 token")
            continue
        if isinstance(data, dict):
            preview = json.dumps(data, ensure_ascii=False)[:70]
        else:
            preview = str(data)[:70]
        print(f"    +{e['t']:8.3f}s  {e['event']:<10} {preview}")
    if token_count:
        print(f"    +{last_token_t:8.3f}s  {'token':<10} "
              f"最后一个 token（共 {token_count} 个）")


# ==================== 统计 ====================

def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(phases_list: list[dict]) -> dict:
    metrics = {}
    for key, _ in PHASES + METRICS:
        values = [p[key] for p in phases_list if p.get(key) is not None]
        if not values:
            metrics[key] = None
            continue
        metrics[key] = {
            "n": len(values),
            "p50": percentile(values, 0.50),
            "p95": percentile(values, 0.95),
            "mean": statistics.fmean(values),
        }

    # 占比统一用"走完整链路"的样本做分母（有专科 + 质检的业务意图）。
    # 闲聊/转人工的总耗时短得多，混进分母会让其余阶段占比失真，三项加起来超过 100%
    business = [
        p["total"] for p in phases_list
        if p.get("has_specialist") and p.get("has_quality") and p.get("total") is not None
    ]
    metrics["_base_total"] = statistics.fmean(business) if business else None
    return metrics


def fmt_seconds(value: float | None) -> str:
    return f"{value:.2f}s" if value is not None else "-"


def print_report(tag: str, metrics: dict, samples: int, failures: int,
                 sink, url: str) -> None:
    print(f"\n=== {tag} ===")
    print(f"目标: {url}")
    print(f"样本: {samples} 条" + (f"，失败 {failures} 条" if failures else ""))
    print(f"意图分布: {sink}")

    header = f"{_pad('阶段', 16)}{_pad('p50', 10)}{_pad('p95', 10)}{_pad('均值', 10)}占比"
    print("\n" + header)
    print("-" * _disp_width(header))

    total_mean = (metrics.get("total") or {}).get("mean")
    base_mean = metrics.get("_base_total") or total_mean

    def row(label: str, key: str) -> None:
        m = metrics.get(key)
        if not m:
            print(f"{_pad(label, 16)}{_pad('-', 10)}{_pad('-', 10)}{_pad('-', 10)}-")
            return
        ratio = f"{m['mean'] / base_mean * 100:.1f}%" if base_mean else "-"
        print(f"{_pad(label, 16)}{_pad(fmt_seconds(m['p50']), 10)}"
              f"{_pad(fmt_seconds(m['p95']), 10)}{_pad(fmt_seconds(m['mean']), 10)}{ratio}")

    for key, label in PHASES:
        row(label, key)
    print("-" * _disp_width(header))
    for key, label in METRICS:
        m = metrics.get(key)
        if m:
            print(f"{_pad(label, 16)}{_pad(fmt_seconds(m['p50']), 10)}"
                  f"{_pad(fmt_seconds(m['p95']), 10)}{_pad(fmt_seconds(m['mean']), 10)}")


def print_compare(previous: dict, current: dict) -> None:
    prev_tag = previous.get("tag", "上一次")
    cur_tag = current.get("tag", "本次")
    print(f"\n=== 对比 {prev_tag} → {cur_tag}（p50）===")
    header = f"{_pad('阶段', 16)}{_pad(prev_tag, 14)}{_pad(cur_tag, 14)}差值"
    print(header)
    print("-" * _disp_width(header))

    def row(label: str, key: str) -> None:
        before = (previous.get("metrics", {}).get(key) or {}).get("p50")
        after = (current.get("metrics", {}).get(key) or {}).get("p50")
        if before is None or after is None:
            print(f"{_pad(label, 16)}{_pad(fmt_seconds(before), 14)}"
                  f"{_pad(fmt_seconds(after), 14)}-")
            return
        delta = (after - before) / before * 100 if before else 0
        sign = "+" if delta >= 0 else ""
        print(f"{_pad(label, 16)}{_pad(fmt_seconds(before), 14)}"
              f"{_pad(fmt_seconds(after), 14)}{sign}{delta:.1f}%")

    for key, label in PHASES + METRICS:
        row(label, key)


# ==================== 主流程 ====================

def load_questions(path: Path, limit: int, pick: str) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    questions = [item if isinstance(item, str) else item["question"] for item in raw]
    if limit <= 0 or limit >= len(questions):
        return questions
    if pick == "first":
        return questions[:limit]
    step = len(questions) / limit
    return [questions[min(int(i * step), len(questions) - 1)] for i in range(limit)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="多 Agent 客服流式性能测量")
    # 用 127.0.0.1 而不是 localhost：Windows 上 localhost 会先解析到 IPv6 的 ::1，
    # 引擎只监听 IPv4，回退一次要多花约 2 秒
    parser.add_argument("--url", default="http://127.0.0.1:8001/api/v1/chat/stream",
                        help="流式聊天接口地址（打网关换成 :8082）")
    parser.add_argument("--field", default="message", choices=["question", "message"],
                        help="请求体字段名：客服用 message，RAG 用 question")
    parser.add_argument("--username", help="网关登录用户名")
    parser.add_argument("--password", help="网关登录密码")
    parser.add_argument("--token", help="已有 JWT（优先于账号密码）")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS),
                        help="问题集 JSON")
    parser.add_argument("--limit", type=int, default=8, help="取多少题（0 = 全部）")
    parser.add_argument("--pick", choices=["even", "first"], default="even",
                        help="选题方式：even 均匀抽样（默认），first 取前 N 条")
    parser.add_argument("--runs", type=int, default=3, help="整套问题重复几遍")
    parser.add_argument("--warmup", type=int, default=1,
                        help="热身请求数（不计入统计）")
    parser.add_argument("--tag", default="baseline", help="本次结果的名字")
    parser.add_argument("--out", help="结果文件路径（默认 perf_results/<tag>.json）")
    parser.add_argument("--compare", help="上一次的结果 JSON，跑完打印差值")
    parser.add_argument("--dump-events", action="store_true",
                        help="打印事件时间线（建议配合 --limit 1 --runs 1）")
    parser.add_argument("--timeout", type=float, default=180, help="单请求超时（秒）")
    args = parser.parse_args()

    if args.runs <= 0:
        raise SystemExit("--runs 必须大于 0")

    token = args.token
    if token is None and args.username:
        if not args.password:
            raise SystemExit("传了 --username 就要同时传 --password")
        token = login(args.url, args.username, args.password)
        print("登录成功，已获取 token")

    questions = load_questions(Path(args.questions), args.limit, args.pick)
    if not questions:
        raise SystemExit("问题集为空")

    print(f"目标: {args.url}")
    print(f"问题: {len(questions)} 题 × {args.runs} 轮，热身 {args.warmup} 次，串行执行")

    for i in range(args.warmup):
        warm = one_request(args.url, args.field, questions[0], token, args.timeout)
        if not warm["ok"]:
            raise SystemExit(f"热身请求失败（HTTP {warm['status']}）: {warm['error']}")
        print(f"热身 {i + 1}/{args.warmup} 完成（{warm['events'][-1]['t']:.2f}s）")

    records: list[dict] = []
    phases_list: list[dict] = []
    failures = 0
    total_requests = len(questions) * args.runs

    for run in range(args.runs):
        for question in questions:
            index = len(records) + 1
            result = one_request(args.url, args.field, question, token, args.timeout)
            if not result["ok"]:
                failures += 1
                print(f"[{index}/{total_requests}] 失败 HTTP {result['status']}: "
                      f"{result['error']}  ← {question[:24]}")
                continue

            phases = derive_phases(result)
            add_other(phases)
            records.append({"question": question, "phases": phases})
            phases_list.append(phases)

            print(f"[{index}/{total_requests}] "
                  f"接待 {fmt_seconds(phases['receptionist']):>7}  "
                  f"专科 {fmt_seconds(phases['specialist']):>7}  "
                  f"质检 {fmt_seconds(phases['quality']):>7}  "
                  f"TTFT {fmt_seconds(phases['ttft']):>7}  "
                  f"专科首token {fmt_seconds(phases['answer_ttft']):>7}  "
                  f"总计 {fmt_seconds(phases['total']):>7}  "
                  f"[{phases['intent'] or '?'}]")

            if args.dump_events:
                dump_events(result["events"])

    if not phases_list:
        raise SystemExit("\n没有任何有效样本")

    intent_counts: dict[str, int] = {}
    for p in phases_list:
        key = p.get("intent") or "unknown"
        intent_counts[key] = intent_counts.get(key, 0) + 1
    sink = ", ".join(f"{k}×{v}" for k, v in sorted(intent_counts.items()))

    metrics = summarize(phases_list)
    print_report(args.tag, metrics, len(phases_list), failures, sink, args.url)

    out_path = Path(args.out) if args.out else Path("perf_results") / f"{args.tag}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tag": args.tag,
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": args.url,
        "questions": len(questions),
        "runs": args.runs,
        "samples": len(phases_list),
        "failures": failures,
        "intents": intent_counts,
        "metrics": metrics,
        "raw": records,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n结果已保存: {out_path}")

    if args.compare:
        prev_path = Path(args.compare)
        if not prev_path.exists():
            print(f"\n⚠️ 对比文件不存在: {prev_path}")
        else:
            print_compare(json.loads(prev_path.read_text(encoding="utf-8")), payload)

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
