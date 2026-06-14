# 项目需求文档

## 项目概述

基于 FastAPI + LangGraph 的多 Agent 智能客服系统，支持多 Agent 协作、意图识别、智能路由、质量监控、联网搜索和 Token 级流式输出。

## 核心需求

1. **智能前台接待**：ReceptionistAgent + JSON Mode，同时完成意图分类和自然语言接待
2. **多 Agent 协作**：前台接待 + 4 个专科 Agent（技术支持、订单服务、产品咨询、联网搜索）
3. **服务质量监控**：LLM 评估回复质量，低分自动升级人工（联网搜索跳过质量检查）
4. **多轮对话**：AsyncSqliteSaver 持久化对话状态，支持上下文连续对话
5. **流式输出**：SSE 格式逐步返回接待语、意图、回复、质量评分

## 功能需求

### Agent
- 前台接待 Agent：JSON Mode 意图分类 + 闲聊/转人工自然语言回复
- 技术支持 Agent：FAQ 向量检索（ChromaDB）
- 订单服务 Agent：订单查询、物流跟踪（SQLite）
- 产品咨询 Agent：产品搜索、预算推荐（SQLite）
- 联网搜索 Agent：DashScope agent_max 内置搜索，外部品牌/参数/行情
- 质量检查 + 人工升级（联网搜索跳过质量检查）

### API
- POST `/api/v1/chat` — 非流式对话
- POST `/api/v1/chat/stream` — 流式 SSE 对话
- GET `/api/v1/conversations/` — 对话列表
- GET `/api/v1/conversations/{id}` — 对话详情
- DELETE `/api/v1/conversations/{id}` — 删除对话

### Web UI
- 客服风格的聊天界面
- 意图标签实时显示
- 转人工横幅提示
- 快速体验按钮

## 非功能需求

- 数据持久化（ChromaDB + SQLite + AsyncSqliteSaver）
- 模块化分层架构（core/models/routers/services/agents/utils）
- 中文注释和文档
- 环境变量配置（pydantic-settings）
