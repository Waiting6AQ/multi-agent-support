# 多 Agent 智能客服系统

前后端分离的智能客服系统：Spring Boot 业务后端（JWT 鉴权 + 会话管理 + AI 转发）+ Vue 3 前端 + Python 多 Agent 客服引擎。Java 作为唯一对外出口，通过 SSE 透传实现 Token 级打字机效果。

## 特性

- **Java 业务系统 + Python AI 微服务**：Java 网关统一对外（鉴权/审计/转发），Python 引擎作为内部能力层通过 HTTP 集成
- **JWT 无状态认证**：jjwt 签发/校验 + BCrypt 密码哈希，简化 RBAC（user/role 两张表），拦截器统一鉴权
- **会话归属隔离**：业务侧自持会话记录（chat_session + chat_message），用户只能看到自己的会话，列表/详情/删除/聊天全链路校验
- **AI 服务无状态**：对话归属（user_id ↔ conversation_id）在业务侧 MySQL，AI 侧 checkpoint 只管多轮上下文；转发时网关注入 `X-User-Id` 可信头，预留数据隔离/审计
- **SSE 流式透传**：Spring 用 `StreamingResponseBody` + `RestClient` 对引擎 SSE 流做逐行原样透传（只劫持 done 事件附加 session_id），前端逐 token 渲染打字机效果 + 实时意图反馈
- **意图标签留存**：每轮回复的意图分类业务侧落库，可审计可统计（引擎侧不保留历史意图）
- **容错降级**：AI 服务超时/不可达返回友好提示而非 500；客户端断连静默处理；全局异常统一 `Result` 结构
- **多 Agent 引擎能力**（详见 `agent_engine/README.md`）：LangGraph 编排 5 个专科 Agent，FAQ 向量检索、订单/产品查询、联网搜索、质量评估自动转人工

## 技术栈

| 层       | 技术                                                                                    |
| -------- | --------------------------------------------------------------------------------------- |
| 前端     | Vue 3 / Vite / axios / fetch（SSE 流式读取）                                            |
| 业务后端 | Spring Boot 3.5 / MyBatis（注解 + XML）/ MySQL / jjwt / spring-security-crypto / RestClient |
| AI 引擎  | Python FastAPI / LangGraph / LangChain / ChromaDB / DashScope Qwen / MCP                |

## 目录结构

```
agent_system/
├── agent_engine/    Python 多 Agent 客服引擎（AI 能力层，:8001）
├── backend/         Spring Boot 业务后端（:8082）
│   ├── db/init.sql          建库脚本（可选，默认自动建库）
│   └── src/main/resources/
│       ├── schema.sql       建表脚本（启动自动执行，utf8mb4）
│       └── mapper/*.xml     复杂 SQL（分页查询）
└── frontend/        Vue 3 前端（:5173，开发代理到 :8082）
```

## 系统架构

```
浏览器（Vue 3）
    │  JWT 鉴权（Authorization: Bearer <token>）
    ▼
Spring Boot 业务后端 (:8082)
    ├─ 用户体系：注册/登录/角色（user + role）
    ├─ 会话管理：chat_session + chat_message（业务侧审计记录）
    ├─ 转发：/api/chat（非流式）、/api/chat/stream（SSE 透传）
    │      │  内部 HTTP（X-User-Id 可信头）
    │      ▼
    Python 多 Agent 引擎 (:8001)
    │  LangGraph：接待员 → 条件路由 → 专科 Agent → 质量检查 → 转人工判断
    ▼
SQLite + ChromaDB（checkpoint 多轮上下文 / FAQ 向量索引）
```

## 快速开始

### 环境要求

- JDK 17+、Node 18+、Python 3.12+
- MySQL 8+（root 密码通过 `backend/.env` 的 `DB_PASSWORD` 提供，见下方配置步骤）
- DashScope API Key（agent_engine/.env）

### 配置

先复制两份模板并填入真实值（`.env` 均已 gitignore，不会提交）：

```bash
# AI 引擎密钥（DashScope）
cd agent_engine
copy .env.example .env      # 填入 DASHSCOPE_API_KEY
cd ..

# 业务后端数据库/密钥
cd backend
copy .env.example .env      # 填入 DB_PASSWORD（MySQL root 密码）、JWT_SECRET
```

### 启动

```bash
# 1. AI 引擎（:8001）
cd agent_engine
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
python main.py

# 2. 业务后端（:8082，自动建库建表 + 预置管理员）
cd backend
.\mvnw.cmd spring-boot:run

# 3. 前端（:5173）
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`，默认管理员账号 `admin / admin123`（首次登录后请修改）。

### API 端点

| 方法   | 路径                | 说明                            |
| ------ | ------------------- | ------------------------------- |
| POST   | /api/auth/register  | 注册（默认 USER 角色）          |
| POST   | /api/auth/login     | 登录，签发 JWT                  |
| POST   | /api/sessions       | 创建会话                        |
| GET    | /api/sessions       | 会话列表（分页，仅当前用户）    |
| GET    | /api/sessions/{id}  | 会话详情（含消息 + 意图标签）   |
| DELETE | /api/sessions/{id}  | 删除会话（级联删消息）          |
| POST   | /api/chat           | 聊天（非流式，落库）            |
| POST   | /api/chat/stream    | 聊天（SSE 流式，打字机效果）    |

## License

MIT
