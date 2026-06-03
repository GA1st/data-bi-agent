# 项目亮点与面试话术

## 30 秒项目介绍

> 这是一个 BI 数据分析 Agent，用户用自然语言提问，系统自动生成 SQL 查询数据库、生成可视化图表和经营分析报告。采用 FastAPI 中间件架构，包含认证、限流、审计、缓存、定时任务、Prometheus 监控等生产级基础设施，Docker 容器化部署，有完整的 CI/CD pipeline。

## 可以展开讲的工程亮点

### 1. 中间件栈设计
- 5 层中间件（ErrorHandler → Logging → RateLimit → Auth → SecurityHeaders）
- 利用 Starlette 逆序执行特性，按安全层级排列
- 可配置开关（.env 控制 auth/rate_limit/cache/scheduler）
- **面试点**：中间件模式、洋葱模型、关注点分离

### 2. SQL 注入多层防御
- API 参数校验 → identifier 正则 → SQL 关键词拦截 → 参数化查询
- 13 个危险关键词正则匹配
- 自动 LIMIT 防止内存溢出
- **面试点**：纵深防御、永不信任用户输入

### 3. LLM 模型降级路由
- heavy model（gpt-4）用于 NL→SQL 等复杂任务
- light model（gpt-4o-mini）用于图表建议、SQL 修复等简单任务
- 成本降低约 80%，延迟降低约 60%
- **面试点**：成本优化、任务分级、API 设计

### 4. Context Management
- token 预算分配（system prompt + history + question + response reserve）
- 历史对话超限时自动摘要压缩
- 中文/英文混合 token 估算
- **面试点**：长对话管理、prompt engineering、成本控制

### 5. 零新依赖的生产级基础设施
- TTL 缓存（threading.Lock + dict，无 Redis）
- 线程安全 SQLite（threading.local + WAL 模式）
- 定时任务（threading + while loop，无 APScheduler）
- Prometheus metrics（自实现 text format，无 prometheus_client）
- **面试点**：为什么不过度依赖第三方库、Python stdlib 的能力

### 6. 可观测性三支柱
- **日志**：JSON 结构化日志，request_id 追踪
- **指标**：Prometheus 兼容的 /metrics 端点
- **审计**：查询审计日志，缓冲批量写入
- **面试点**：排障效率、可观测性设计

### 7. 优雅降级
- LLM 不可用时：报表展示数据 + 图表，跳过叙事
- 图表推荐失败时：_fallback_chart() 根据列类型生成基础图表
- 缓存关闭时：所有查询直接穿透到数据库
- **面试点**：核心功能不依赖可选组件

## 可能被追问的深度问题

**Q: 这个项目的性能瓶颈在哪？**
- LLM 调用延迟（2-5 秒），用 SSE 流式缓解体感
- SQLite 写入并发（单写入者），用 WAL 模式 + 缓冲写入缓解
- schema 构建开销，用 TTL 缓存解决

**Q: 如果用户量从 10 扩展到 10000？**
- SQLite → PostgreSQL（database.py 层已抽象）
- 内存缓存 → Redis
- 单进程 → Gunicorn 多 worker + Nginx 负载均衡
- 会话存储 → Redis/数据库

**Q: 如果要支持多租户？**
- 每个租户独立的数据库 schema（SQLite 文件隔离）
- API key 绑定租户 ID
- Auth 中间件解析租户信息，路由到对应数据库

**Q: LLM 的成本控制？**
- model downgrade：简单任务用 light model
- context trimming：控制 prompt 长度
- 缓存：相同问题复用结果
- 监控：audit_log 追踪每次调用

**Q: 你觉得这个项目还有什么不足？**
- 测试覆盖率：主要是单元测试，缺少集成/E2E 测试
- 数据库迁移：没有版本化 schema 管理
- 前端：无 TypeScript、无组件化框架
- 认证：只有 API key，没有 OAuth/JWT
- 国际化：目前只支持中文

## 项目文件结构速查

```
data_bi_agent/
├── app.py                    # 入口：lifespan + 中间件注册
├── config.py                 # 统一配置（pydantic-settings）
├── core/
│   ├── database.py           # SQLite 线程安全层
│   ├── llm.py                # LLM 客户端 + model routing
│   ├── cache.py              # TTL 缓存 + @cached
│   ├── session.py            # 会话管理 (OrderedDict LRU)
│   ├── context.py            # Token 预算 + 历史裁剪
│   ├── scheduler.py          # 定时任务 (threading)
│   ├── metrics.py            # Prometheus metrics
│   ├── exceptions.py         # 异常层级
│   ├── logger.py             # JSON 日志
│   └── middleware/           # 5 层中间件
├── agents/
│   ├── sql_agent.py          # NL→SQL + 自动修复
│   ├── chart_agent.py        # 图表推荐 (ECharts)
│   ├── anomaly_agent.py      # 异常检测 (Z-Score + IQR)
│   └── report_agent.py       # 报表生成
├── services/
│   ├── query_executor.py     # SQL 安全校验 + 执行
│   ├── query_audit.py        # 审计日志 (缓冲写入)
│   ├── multi_datasource.py   # CSV 导入 + 类型推断
│   └── data_initializer.py   # Demo 数据初始化
├── api/
│   ├── chat.py               # SSE 流式对话
│   ├── dashboard.py          # 报表 API
│   ├── data_explorer.py      # 数据浏览 + 保存查询
│   ├── database_manage.py    # 数据库管理
│   └── system.py             # 审计/调度/CSV/Metrics
├── static/                   # SPA 前端 (HTML/CSS/JS)
├── tests/run_tests.py        # 25 个测试
├── docs/                     # 面试文档
├── Dockerfile                # 非 root + HEALTHCHECK
├── docker-compose.yml
└── .github/workflows/ci.yml  # CI/CD pipeline
```

## 面试文档索引

| 文档 | 主题 |
|------|------|
| [00-architecture](00-architecture.md) | 架构总览 + 数据流 |
| [01-middleware-security](01-middleware-security.md) | 中间件栈 + SQL 注入防护 |
| [02-nl2sql-agent](02-nl2sql-agent.md) | NL→SQL + prompt 工程 |
| [03-database-caching-session](03-database-caching-session.md) | 数据库 + 缓存 + 会话 |
| [04-visualization-anomaly-report](04-visualization-anomaly-report.md) | 图表 + 异常检测 + 报表 |
| [05-scheduler-audit-metrics](05-scheduler-audit-metrics.md) | 定时任务 + 审计 + 可观测性 |
| [06-ci-docker](06-ci-docker.md) | CI/CD + Docker 部署 |
| [07-sse-frontend](07-sse-frontend.md) | SSE 流式 + 前端架构 |
| [08-project-highlights](08-project-highlights.md) | 项目亮点 + 追问题库 |
| [09-distributed-evolution](09-distributed-evolution.md) | 分布式架构演进 |
| [10-architecture-retrospective](10-architecture-retrospective.md) | 架构反思：不足与改进 |
