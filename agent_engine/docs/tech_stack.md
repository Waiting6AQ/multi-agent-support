# 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 语言 | CPython 3.12 | 运行时 |
| 框架 | FastAPI | Web 框架，APIRouter 模块化路由 |
| 服务器 | Uvicorn | ASGI 服务器 |
| LLM 编排 | LangChain 1.x | LLM 调用、提示词模板、Agent 创建 |
| 工作流编排 | LangGraph 1.2.x | StateGraph + AsyncPostgresSaver 持久化 |
| LLM 模型 | 通义千问 Qwen3-Max (DashScope) | 通用 LLM |
| JSON Mode | DashScope response_format | ReceptionistAgent 结构化输出 |
| 联网搜索 | MCP (百度千帆 web-search) | WebSearchAgent 通过 MCP 协议接入，每日 50 次免费额度 |
| Agent Skills | Deep Agents SkillsMiddleware | TechSupportAgent FAQ 未命中时渐进式加载排查规范 |
| Embeddings | DashScope text-embedding-v4 | FAQ 向量嵌入 |
| 向量数据库 | ChromaDB | FAQ 本地持久化向量检索 |
| 关系数据库 | PostgreSQL 18 | 订单、产品、对话元数据，SQLAlchemy 2.0 async ORM + psycopg 驱动 |
| 对话持久化 | LangGraph AsyncPostgresSaver | 多轮对话状态持久化 |
| 数据验证 | Pydantic 2.x | 请求/响应模型 |
| 配置 | pydantic-settings | .env 环境变量加载 |
| 前端 | 原生 HTML + JS (SSE) | 引擎自带的调试页 `static/index.html`——只起引擎就能自测，不需要 Java 与 MySQL；正式入口是仓库的 Vue 后台 |
