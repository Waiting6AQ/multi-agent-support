# 执行步骤

## Phase 1: 基础设施 ✅
- [x] 创建目录结构
- [x] `.env` / `.env.example` / `.gitignore`
- [x] `requirements.txt`
- [x] `core/config.py`（Settings 配置类）
- [x] `utils/json_utils.py`（safe_parse_json）

## Phase 2: 工具层 ✅
- [x] `utils/llm.py`（create_llm 工厂函数）
- [x] `utils/embeddings.py`（AliyunEmbeddings）
- [x] `utils/db_init.py`（FAQ + 订单/产品种子数据）

## Phase 3: 数据模型 ✅
- [x] `models/chat.py`（ChatRequest / ChatResponse）
- [x] `models/conversation.py`（对话管理模型）

## Phase 4: Agent 定义 ✅
- [x] `agents/tech_support.py`（search_faq → ChromaDB）
- [x] `agents/order_service.py`（query_order, track_shipping → SQLite）
- [x] `agents/product_consult.py`（search_product, get_recommendations → SQLite）

## Phase 5: 服务层 ✅
- [x] `services/intent_classifier.py`（意图分类器）
- [x] `services/quality_checker.py`（质量检查器）
- [x] `services/conversation_service.py`（对话元数据 CRUD）
- [x] `services/agent_service.py`（LangGraph 编排核心）

## Phase 6: 依赖注入 ✅
- [x] `core/dependencies.py`（单例工厂）

## Phase 7: 路由层 ✅
- [x] `routers/chat.py`（SSE 流式 + 非流式）
- [x] `routers/conversations.py`（对话管理）

## Phase 8: 组装 ✅
- [x] `main.py`（注册路由、CORS、静态文件、port 8001）
- [x] `static/index.html`（客服风格 Web 聊天界面）

## Phase 9: 文档和验证 ✅
- [x] `docs/requirements.md`
- [x] `docs/tech_stack.md`
- [x] `docs/design_spec.md`
- [x] `docs/execution_plan.md`
- [x] `dev_logs/devlog.md`
- [x] `dev_logs/bug_log.md`
- [x] 启动验证：端口 8001，测试 API 和 Web 界面

## Phase 10: 联网搜索 Agent ✅
- [x] `agents/web_search.py`（WebSearchAgent）
- [x] `utils/llm.py` 新增 create_search_llm()
- [x] intent_classifier 新增 web_search 意图
- [x] agent_service 加节点 + 路由
- [x] web_search 跳过质量检查

## Phase 11: 前台接待 Agent（Coordinator 模式） ✅
- [x] `agents/receptionist.py`（ReceptionistAgent + JSON Mode）
- [x] `utils/llm.py` 新增 create_json_llm()
- [x] 替代 classify_intent 节点，删 _node_escalate + ESCALATION_MESSAGE
- [x] 前端 chitchat 标签 + 欢迎语更新

## Phase 12: 优化与修复 ✅
- [x] 消息截断 [-11:] 保留 5 轮完整对话
- [x] 引导语与 Agent 回复换行分隔
- [x] web_search prompt 去硬编码产品名
- [x] 意图标签命名优化（置信度 → 意图把握）
- [x] State 字段跨轮污染修复
- [x] delete_history() checkpoints 清理
- [x] 5 个 Agent × 12 个场景全通过
