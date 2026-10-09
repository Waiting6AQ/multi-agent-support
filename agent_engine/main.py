"""
多 Agent 智能客服系统 — 应用入口

启动方式：
    python main.py
    或
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload

访问：
    API 文档   http://localhost:8001/docs
    Web 界面   http://localhost:8001
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import sys

from core.config import settings
from routers import chat, conversations

# ==================== 控制台编码兼容 ====================

# Windows 控制台默认 GBK，日志里的 ⚠️ / ✅ 会让 print 抛 UnicodeEncodeError。
# 后果不只是日志乱码：节点里"打印警告后降级"的写法会变成打印本身崩掉，降级失效。
# 保留控制台原本的编码，只把编不出来的字符换成 ?（Linux/Docker 是 UTF-8，这行是空操作）
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")


# ==================== 初始化数据目录 ====================

# 只剩 ChromaDB 需要本地目录（会话状态和业务数据都已迁到 PostgreSQL）
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)


# ==================== 启动预加载 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：初始化 PostgreSQL + 灌种子数据；关闭：释放数据库连接"""
    # ---- ① PostgreSQL ----
    # 顺序：先 init_checkpointer（自带重试，会一直等到 PG 就绪），再 init_database 建业务表
    # checkpointer 必须在事件循环里构造 —— AsyncPostgresSaver.__init__ 会取 running loop
    from core.database import dispose_engine, get_session_factory, init_database
    from core.postgres import close_pool, init_checkpointer

    await init_checkpointer()
    await init_database()
    print("✅ PostgreSQL 初始化完成（checkpoint 表 + 业务表）")

    # ---- ② 种子数据（FAQ 向量库 + 订单/产品）----
    # seed_all 是幂等的：已有数据会跳过，重启不会重复灌
    from utils.embeddings import AliyunEmbeddings
    from utils.db_init import seed_all
    embeddings = AliyunEmbeddings(model=settings.EMBEDDING_MODEL_NAME)
    await seed_all(
        session_factory=get_session_factory(),
        chroma_persist_dir=settings.CHROMA_PERSIST_DIR,
        embeddings=embeddings,
    )

    # ---- ③ 联网搜索 MCP 工具 ----
    # 外部服务，主动预热而不是留给首次请求：
    #   - 连不上会立刻出现在启动日志里，不会混在访问日志中难以察觉
    #   - 不让用户第一次提问额外承担一次 MCP 握手
    # 失败不影响启动：get_web_agent 内部降级，并在冷却期后自动重试
    from core.dependencies import get_web_agent
    web_agent = await get_web_agent()
    if web_agent.tools:
        print(f"✅ 联网搜索 MCP 已就绪（{len(web_agent.tools)} 个工具）")

    yield

    # ---- 关闭：释放连接（顺序与建立时相反）----
    await dispose_engine()
    await close_pool()
    print("👋 PostgreSQL 连接已释放")


# ==================== 创建应用 ====================

app = FastAPI(
    title="多 Agent 智能客服系统",
    description="基于 LangGraph 的多 Agent 智能客服系统，支持意图识别、"
                "智能路由、专业 Agent、质量检查、人工升级。",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 注册路由 ====================

app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["Conversations"])

# ==================== 静态文件 ====================

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Web 聊天界面"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "service": "Multi-Agent Customer Service API", "docs": "/docs"}


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import sys
    import uvicorn

    reload = os.getenv("DISABLE_RELOAD", "").lower() != "true"

    # Windows 必须显式指定事件循环工厂：uvicorn 在 win32 上硬编码用 ProactorEventLoop，
    # 而 psycopg 的异步模式不支持它。Linux 容器不传，保留 uvicorn 默认（uvloop）。
    extra = (
        {"loop": "core.compat:selector_loop_factory"}
        if sys.platform == "win32"
        else {}
    )
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=reload, **extra)
