# 多 Agent 智能客服系统

基于 FastAPI + LangGraph 构建的多 Agent 协作客服系统，支持前台接待、智能路由、专科 Agent、质量监控、联网搜索和 Token 级流式输出。

## 特性

- **Coordinator 模式**：ReceptionistAgent 统一接待，JSON Mode 结构化输出，一次调用同时完成意图分类和自然语言回复
- **多 Agent 协作**：5 个 Agent 各司其职 — 前台接待、技术支持（向量检索 FAQ + Agent Skills 兜底）、订单服务（SQLite）、产品咨询（SQLite）、联网搜索（百度搜索 MCP）
- **智能路由**：基于意图的条件路由，闲聊/转人工直接回复，业务意图转专业 Agent
- **混合数据源**：FAQ 用 ChromaDB 向量检索（非结构化语义匹配），订单/产品用 SQLite（结构化精确查询），外部信息走 MCP 百度搜索
- **质量监控**：LLM 四维度评估回复质量，低分自动升级人工（联网搜索结果跳过质量检查）
- **多轮对话**：AsyncSqliteSaver 持久化 + `add_messages` 自动管理，上下文截断防止无限增长
- **Token 级流式输出**：SSE 格式，实时意图反馈 + 打字机效果 + 质量评分
- **客服风格 UI**：紫色渐变界面、气泡动画、意图标签、转人工横幅、快速体验按钮

## 技术栈

| 层         | 技术                                                                      |
| ---------- | ------------------------------------------------------------------------- |
| Web 框架   | FastAPI + Uvicorn                                                         |
| LLM 编排   | LangGraph StateGraph（7 节点管线）                                        |
| Agent 创建 | `create_agent`（工具型 Agent）+ `create_deep_agent`（Skill Agent）+ JSON Mode（接待员） |
| LLM        | 通义千问 Qwen3-Max (DashScope)                                            |
| JSON Mode  | DashScope `response_format={"type": "json_object"}`                       |
| 联网搜索   | MCP (mcpmarket.cn 百度搜索)                                               |
| Agent Skill | Deep Agents SkillsMiddleware + FilesystemBackend，渐进式披露              |
| Embeddings | DashScope `text-embedding-v4`                                             |
| 向量存储   | ChromaDB 本地持久化（FAQ）                                                |
| 关系数据库 | SQLite（订单、产品、对话元数据）                                          |
| 对话持久化 | LangGraph AsyncSqliteSaver                                                |
| 流式输出   | `get_stream_writer()` + `stream_mode="custom"` + `stream_mode="messages"` |
| 数据验证   | Pydantic v2                                                               |
| 配置管理   | pydantic-settings (.env)                                                  |

## 项目结构

```
multi_agent_fastapi/
├── main.py                     # FastAPI 入口（lifespan 种子数据、port 8001）
├── core/
│   ├── config.py               # 配置管理（pydantic-settings）
│   └── dependencies.py         # 依赖注入（模块级缓存单例）
├── models/
│   ├── chat.py                 # 聊天请求/响应模型
│   └── conversation.py         # 对话管理模型
├── routers/
│   ├── chat.py                 # 流式 + 非流式聊天接口
│   └── conversations.py        # 对话管理接口（列表/详情/删除）
├── services/
│   ├── agent_service.py        # LangGraph 多 Agent 编排核心
│   ├── intent_classifier.py    # 原意图分类器（已被 ReceptionistAgent 替代，保留供参考）
│   ├── quality_checker.py      # 回复质量评估（4 维度打分）
│   └── conversation_service.py # 对话元数据 CRUD
├── agents/
│   ├── receptionist.py         # 前台接待 Agent（JSON Mode）
│   ├── tech_support.py         # 技术支持 Agent（ChromaDB FAQ + Agent Skill 兜底）
│   ├── order_service.py        # 订单服务 Agent（SQLite 查询）
│   ├── product_consult.py      # 产品咨询 Agent（SQLite 查询 + 推荐）
│   └── web_search.py           # 联网搜索 Agent（MCP 百度搜索）
├── skills/                     # Agent Skills 目录
│   └── tech_support/           # 技术支持 Agent 专属 Skill 分组
├── utils/
│   ├── embeddings.py           # 向量模型封装（AliyunEmbeddings）
│   ├── llm.py                  # LLM 工厂（标准/JSON 两种模式）
│   ├── db_schema.py            # 数据库 DDL
│   ├── db_seed.py              # 种子数据（FAQ/订单/产品）
│   ├── db_init.py              # 数据初始化入口
│   └── json_utils.py           # JSON 安全解析
├── static/
│   └── index.html              # 客服风格 Web 聊天界面
├── docs/                       # 项目文档
├── Dockerfile                  # Docker 镜像构建
├── .dockerignore
├── .gitignore
├── .env.example
├── requirements.txt
└── README.md
```

## 管线架构

```
START → receptionist → 条件路由
                          ├── chitchat / escalate → respond → END
                          └── tech / order / product / web_search
                                  → quality_check → 条件路由
                                      ├── escalate_final → END
                                      └── respond → END
```

| 节点                         | 职责                                                                    |
| ---------------------------- | ----------------------------------------------------------------------- |
| `receptionist`               | JSON Mode 前台接待：意图分类 + 闲聊/转人工时直接生成自然语言回复        |
| `tech_support`               | FAQ 向量检索 → Agent 推理 → FAQ 未命中时加载 Agent Skill 排查流程       |
| `order_service`              | SQLite 订单查询 / 物流跟踪 → Agent 整理回复                             |
| `product_consult`            | SQLite 产品搜索 / 预算推荐 → Agent 推荐回复                             |
| `web_search`                 | MCP 百度搜索 → Agent 整理搜索结果为结构化回复（跳过质量检查）           |
| `quality_check`              | LLM 四维度评估（相关性/完整性/专业性/有用性），低分标记转人工           |
| `escalate_final` / `respond` | 标记转人工（前端展示横幅）/ 正常透传                                    |

## 数据架构

```
 用户消息
    │
    ▼
┌─────────────────┐
│  Receptionist   │  JSON Mode — 意图分类 + 闲聊回复
│   (前台接待)     │
└────────┬────────┘
         │ 条件路由
    ┌────┼────────┬────────┐
    ▼    ▼        ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────────┐
│ Tech ││Order ││Prod. ││WebSearch │
│Support││Service││Consult││(MCP搜索) │
└──┬───┘└──┬───┘└──┬───┘└────┬─────┘
   │      │       │         │
   ▼      ▼       ▼         ▼
ChromaDB SQLite  SQLite  MCP百度搜索
(FAQ×6)(订单×3)(产品×4)  (外部HTTP)
```

## 快速开始

### 环境要求

- Python 3.12+
- DashScope API Key（阿里云百炼）

### 安装

```bash
git clone <repo-url>
cd multi_agent_fastapi
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 配置

复制 `.env.example` 为 `.env`，填入 API Key：

```env
DASHSCOPE_API_KEY=sk-your-key-here
```

也可以通过环境变量设置。

### 启动

```bash
python main.py
```

访问 `http://localhost:8001` 打开客服界面，或 `http://localhost:8001/docs` 查看 API 文档。

### API 端点

| 方法     | 路径                         | 说明                    |
| -------- | ---------------------------- | ----------------------- |
| `POST`   | `/api/v1/chat`               | 非流式多 Agent 对话     |
| `POST`   | `/api/v1/chat/stream`        | 流式多 Agent 对话 (SSE) |
| `GET`    | `/api/v1/conversations/`     | 对话列表                |
| `GET`    | `/api/v1/conversations/{id}` | 对话详情                |
| `DELETE` | `/api/v1/conversations/{id}` | 删除对话                |

### Docker

```bash
docker build -t multi-agent-cs .
docker run -p 8001:8001 -e DASHSCOPE_API_KEY multi-agent-cs
```

## License

MIT
