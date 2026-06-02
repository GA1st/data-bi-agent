# 项目架构总览

## 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| Web 框架 | FastAPI + Uvicorn | 异步支持、自动 OpenAPI 文档、类型安全 |
| 数据库 | SQLite + WAL 模式 | 零部署依赖、WAL 支持并发读写 |
| LLM | OpenAI-compatible API | 模型可替换，支持本地部署模型 |
| 前端 | 原生 SPA + ECharts | 无构建工具依赖，轻量级 |
| 容器化 | Docker + docker-compose | 标准化部署 |

## 架构分层

```
┌─────────────── 前端 SPA ───────────────┐
│  Dashboard  │  AI Chat  │  Explorer  │
└────────────────┬──────────────────────┘
                 │ SSE / REST
┌────────────────▼──────────────────────┐
│           中间件层 (Middleware)         │
│  CORS → SecurityHeaders → Auth        │
│  → RateLimit → Logging → ErrorHandler │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│              API 层 (api/)             │
│  chat  │  dashboard  │  explorer      │
│  database_manage  │  system           │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│            服务层 (services/)          │
│  query_executor │ query_audit         │
│  multi_datasource │ data_initializer  │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│            智能体层 (agents/)           │
│  sql_agent  │  chart_agent            │
│  anomaly_agent │ report_agent         │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│            核心层 (core/)              │
│  database │ llm │ cache │ session     │
│  context  │ scheduler │ metrics       │
│  exceptions │ logger │ middleware     │
└───────────────────────────────────────┘
```

## 数据流：用户提问 → 结果返回

1. 用户发送自然语言问题（SSE 流式连接）
2. Auth/RateLimit/Logging 中间件依次拦截处理
3. SessionManager 获取/创建会话历史
4. ContextManager 根据 token 预算裁剪历史，构建 LLM prompt
5. sql_agent（heavy model）生成 SQL
6. query_executor 校验 SQL 安全性 → 执行 → 记录审计
7. 如 SQL 报错，chart_agent（light model）自动修复
8. chart_agent（light model）推荐可视化方案
9. anomaly_agent（纯统计算法）检测异常
10. 结果通过 SSE 流逐步推送到前端

---

## 面试高频问题

**Q: 为什么用 FastAPI 而不是 Flask/Django？**
- 原生 async/await 支持，SSE 流式响应天然适配
- Pydantic 模型自动做请求校验，减少手写校验代码
- 自动生成 OpenAPI 文档，前后端协作效率高

**Q: 为什么用 SQLite 而不是 MySQL/PostgreSQL？**
- BI Agent 通常是单机场景，SQLite 零运维
- WAL 模式下支持并发读写，性能足够
- 如果需要扩展，database.py 层做了抽象，可以切换到 SQLAlchemy 支持的其他数据库

**Q: 分层架构的好处？**
- 每层职责单一，方便单独测试和替换
- agents/ 层不依赖 FastAPI，可以独立作为库使用
- core/ 层是纯 Python，不依赖 Web 框架

**Q: 这个项目的难点是什么？**
- Python 3.14 兼容性：aiosqlite/APScheduler/pytest 都没有适配，需要全部用 stdlib 重新实现
- SSE + 中间件兼容：BaseHTTPMiddleware 与 StreamingResponse 的配合需要特别处理
- LLM 调用的健壮性：需要处理超时、JSON 解析失败、API 不可用等降级场景
