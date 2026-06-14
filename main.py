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

from core.config import settings
from routers import chat, conversations


# ==================== 初始化数据目录 ====================

for dir_path in [
    settings.CHROMA_PERSIST_DIR,
    str(Path(settings.APP_DB_PATH).parent),
]:
    os.makedirs(dir_path, exist_ok=True)


# ==================== 启动预加载 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化种子数据（FAQ + 订单/产品模拟数据）"""
    from utils.embeddings import AliyunEmbeddings
    from utils.db_init import seed_all
    embeddings = AliyunEmbeddings(model=settings.EMBEDDING_MODEL_NAME)
    seed_all(
        db_path=settings.APP_DB_PATH,
        chroma_persist_dir=settings.CHROMA_PERSIST_DIR,
        embeddings=embeddings,
    )
    yield


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
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
