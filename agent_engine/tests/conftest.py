"""pytest 共用配置

1. 把引擎根目录加入模块搜索路径，使测试里可以直接 `from utils.xxx import ...`
2. 提供无 .env 也能跑测试的兜底（Settings 的 DASHSCOPE_API_KEY 为必填项）
3. 把 POSTGRES_DSN 重定向到独立的测试库，避免测试清空开发库的数据
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

# 单元测试不访问真实 API：未配置 .env 时给一个占位值，避免 Settings 校验失败
os.environ.setdefault("DASHSCOPE_API_KEY", "test-placeholder-key")


# ==================== 测试库隔离 ====================
# test_db_seed / test_faq_service 会清空 orders / products / faqs 表。
# 直接连开发库的话，跑一次 pytest 就把本地种子数据删了。这里在导入 core.config
# 之前把 POSTGRES_DSN 改成 <库名>_test（不存在就自动建），开发库完全不参与测试。

def _read_dsn() -> str | None:
    """读开发库 DSN：优先环境变量，其次 .env（不打印内容）"""
    dsn = os.environ.get("POSTGRES_DSN")
    if dsn:
        return dsn
    env_file = ENGINE_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_DSN="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    return None


def _use_test_database() -> None:
    dsn = _read_dsn()
    if not dsn:
        return

    parsed = urlparse(dsn)
    dev_db = parsed.path.lstrip("/")
    if not dev_db or dev_db.endswith("_test"):
        return

    test_db = f"{dev_db}_test"
    test_dsn = urlunparse(parsed._replace(path="/" + test_db))
    os.environ["POSTGRES_DSN"] = test_dsn

    try:
        import psycopg

        admin_dsn = urlunparse(parsed._replace(path="/postgres"))
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (test_db,)
            ).fetchone()
            if not exists:
                conn.execute(f'CREATE DATABASE "{test_db}"')
    except Exception as e:
        # 不把开发库当兜底：测试宁可连不上测试库而失败，也不能悄悄清空开发数据
        print(f"⚠️ 无法准备测试库 {test_db}（{type(e).__name__}: {e}）；"
              f"数据库相关测试会失败，请先手动创建该库")


_use_test_database()
