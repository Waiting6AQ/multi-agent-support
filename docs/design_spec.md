# 设计规范

## 目录结构

```
multi_agent_fastapi/
├── main.py                     # FastAPI 入口
├── core/
│   ├── config.py               # 配置（pydantic-settings）
│   └── dependencies.py         # 依赖注入
├── models/
│   ├── chat.py                 # 客服对话请求/响应模型
│   └── conversation.py         # 对话管理模型
├── routers/
│   ├── chat.py                 # 客服聊天路由（流式+非流式）
│   └── conversations.py        # 对话管理路由
├── services/
│   ├── agent_service.py        # 多 Agent 编排（LangGraph）
│   ├── intent_classifier.py    # 意图分类器（已替换为 ReceptionistAgent，保留供参考）
│   ├── quality_checker.py      # 质量检查器
│   └── conversation_service.py # 对话元数据 CRUD
├── agents/
│   ├── receptionist.py         # 前台接待 Agent（JSON Mode）
│   ├── tech_support.py         # 技术支持 Agent
│   ├── order_service.py        # 订单服务 Agent
│   ├── product_consult.py      # 产品咨询 Agent
│   └── web_search.py           # 联网搜索 Agent（MCP 百度搜索）
├── skills/                     # Agent Skills 目录
│   └── tech_support/           # 技术支持 Agent 专属 Skill
├── utils/
│   ├── embeddings.py           # AliyunEmbeddings
│   ├── llm.py                  # LLM 工厂（create_llm / create_json_llm）
│   ├── db_schema.py            # 数据库 DDL
│   ├── db_seed.py              # 种子数据
│   ├── db_init.py              # 数据初始化入口
│   └── json_utils.py           # JSON 安全解析
├── data/                       # gitignored
│   ├── chroma_db/
│   ├── checkpoints.db
│   └── app.db
├── static/                     # Web 前端
├── docs/                       # 项目文档
├── dev_logs/                   # 开发日志
├── Dockerfile                    # Docker 镜像
├── .dockerignore                 # Docker 构建排除
├── .env / .env.example / .gitignore
└── requirements.txt
```

## 命名规范

- **文件名**: 小写下划线 `agent_service.py`
- **类名**: 大驼峰 `AgentService`
- **函数/变量**: 小写下划线 `classify_intent()`
- **常量**: 大写下划线 `FAQ_ENTRIES`
- **路由前缀**: `/api/v1/`

## API 设计规范

- 使用 `response_model` 声明响应类型
- 错误情况抛出 `HTTPException`
- 所有端点添加 `summary` 和 `description`
- 流式端点返回 `StreamingResponse`，`text/event-stream`

## 代码规范

- 中文注释（一行说明意图）
- 类型注解（FastAPI + Pydantic 风格）
- 不在代码中硬编码密钥
- 每个 `.py` 文件顶部写一行模块说明的 docstring
