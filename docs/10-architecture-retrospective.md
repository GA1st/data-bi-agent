# 架构反思 — 不足与改进方向

## 当前架构的三个硬伤

### 硬伤 1：Agent 层直接依赖数据库

**现状**：
```python
# agents/report_agent.py
from core.database import execute_query  # Agent 直接操作数据库

def _get_kpis() -> dict:
    queries = {
        "total_revenue": "SELECT ROUND(SUM(total_amount), 2) FROM orders ...",
        ...
    }
    for key, sql in queries.items():
        rows = execute_query(sql)  # SQL 写死在 Agent 里
```

**问题**：
- Agent 的职责是"与 LLM 交互"，现在又管 LLM 又管数据库，违反单一职责原则
- 单元测试必须连真实数据库，无法 mock
- SQL 分散在 Agent 里，Database 层的 schema 变更要改 Agent 代码

**理想做法**：
```python
# services/report_service.py — 数据获取
class ReportService:
    def __init__(self, repo: DataRepository):
        self.repo = repo

    def get_kpis(self) -> dict:
        return self.repo.query_kpis()  # 通过 Repository 拿数据

# agents/report_agent.py — 纯 LLM 交互
async def generate_narrative(report_data: dict) -> str:
    # 只负责调用 LLM，不知道数据从哪来
    messages = [...]
    return await chat(messages, task_type="heavy")
```

### 硬伤 2：API 层混了编排逻辑

**现状**：
```python
# api/chat.py — SSE 流式端点
async def stream():
    sql_result = await nl_to_sql(...)        # 调 Agent
    query_result = run_query(sql)            # 调 Service
    chart_result = await suggest_chart(...)   # 调 Agent
    anomaly_result = detect_anomalies(...)    # 调 Agent
    explanation = await explain_result(...)   # 调 Agent
    sessions.append(...)                      # 管 Session
```

**问题**：
- API 层既管 HTTP 协议又管业务编排，职责不清
- 如果要做 CLI 版本或 gRPC 接口，整个编排逻辑要复制一遍
- 修改业务流程需要改 API 文件，容易引入 HTTP 层面的 bug

**理想做法**：
```python
# services/chat_service.py — 纯业务编排
class ChatService:
    def __init__(self, sql_agent, chart_agent, anomaly_agent, query_executor, session_mgr):
        self.sql_agent = sql_agent
        self.chart_agent = chart_agent
        ...

    async def process(self, question, session_id):
        sql_result = await self.sql_agent.generate(question)
        query_result = self.query_executor.run(sql_result.sql)
        chart = await self.chart_agent.suggest(query_result)
        ...
        return ChatResponse(...)

# api/chat.py — 只管 HTTP
@router.post("")
async def chat_endpoint(req: ChatRequest):
    response = await chat_service.process(req.message, session_id)
    return StreamingResponse(response.stream(), media_type="text/event-stream")
```

### 硬伤 3：没有依赖注入

**现状**：
```python
# 所有模块通过 import 硬编码依赖
from core.database import execute_query
from core.cache import cache
from services.query_audit import record_query
```

**问题**：
- 测试时无法替换真实实现（比如把 LLM 调用换成 mock）
- 模块之间紧耦合，改一个会影响所有 import 它的模块
- 无法在不同场景下注入不同实现（开发用 SQLite，测试用 mock，生产用 PostgreSQL）

**理想做法**：
```python
# 方案 A：构造函数注入（最简单）
class QueryExecutor:
    def __init__(self, db: Database, audit: AuditLogger, metrics: Metrics):
        self.db = db
        self.audit = audit
        self.metrics = metrics

# 测试时
executor = QueryExecutor(db=MockDB(), audit=SpyAudit(), metrics=FakeMetrics())

# 方案 B：FastAPI 的 Depends（最 Pythonic）
def get_db() -> Database:
    return SQLiteDatabase()

@router.post("/chat")
async def chat(req: ChatRequest, db: Database = Depends(get_db)):
    ...

# 测试时覆盖
app.dependency_overrides[get_db] = lambda: MockDB()
```

---

## 理想的分层架构

```
┌──────────── API 层 ────────────┐
│  只管 HTTP：解析请求、返回响应    │
│  不包含任何业务逻辑              │
└──────────────┬─────────────────┘
               │
┌──────────────▼ Service 层 ─────┐
│  纯业务编排                      │
│  ChatService / ReportService    │
│  协调 Agent + Repository        │
└──────────────┬─────────────────┘
               │
        ┌──────┴──────┐
        ▼              ▼
┌── Agent 层 ──┐ ┌─ Repository 层 ─┐
│ 纯 LLM 交互  │ │ 数据访问抽象     │
│ 不知道 DB    │ │ 不知道 LLM       │
└──────┬──────┘ └──────┬──────────┘
       │               │
┌──────▼───────────────▼──────────┐
│           Core 基础设施层         │
│  Database / Cache / Config / LLM │
└─────────────────────────────────┘
```

**依赖方向**：API → Service → Agent / Repository → Core
**核心原则**：依赖只能从上层指向下层，不能反向

---

## 为什么没一开始就这么做？

| 原因 | 说明 |
|------|------|
| 项目初期快速迭代 | 分层越细，改动越多，初期速度越慢 |
| Python 的文化 | Python 社区偏好"简单优于正确"，不过度工程化 |
| 单人开发 | 依赖注入在多人协作时价值更大，单人项目收益有限 |
| 3.14 兼容性压力 | 主要精力花在解决 stdlib 替代方案上，不是架构设计 |

**这是务实的选择，不是设计能力的缺陷。** 面试时展示你知道问题和改进方向，比写出完美代码更有价值。

---

## 面试高频问题

**Q: 你这个项目的架构有什么不足？**
- 主动暴露上面三个硬伤，说明你对自己的代码有清醒认知
- "Agent 层直接依赖数据库是我最大的架构遗憾，如果重来我会加 Repository 层"

**Q: 如果给你两周时间重构，你会怎么做？**
1. 第一周：加 Repository 层 + Service 层，把 Agent 和 Database 解耦
2. 第二周：加依赖注入（FastAPI Depends），让所有组件可测试
3. 目标：每个组件都能独立测试，不依赖真实数据库或 LLM

**Q: 你觉得好的架构标准是什么？**
- **可测试**：每个组件都能独立测试（mock 外部依赖）
- **可替换**：SQLite 换 PostgreSQL 只改一个文件
- **可理解**：新人看 5 分钟就知道改哪
- **不过度设计**：不为假设的未来需求写代码

**Q: 依赖注入在 Python 里怎么实现？**
- 轻量级：构造函数传参（不需要框架）
- FastAPI 原生：`Depends()` + `app.dependency_overrides`
- 不推荐在 Python 里用 Spring 那样的重量级 IoC 容器
- Python 的 duck typing 让 mock 天然容易，不需要接口+实现分离

**Q: 你怎么看"快速交付"和"架构质量"之间的权衡？**
- 取决于项目阶段和团队规模
- MVP 阶段：速度 > 架构，先验证业务价值
- 增长阶段：还技术债，补架构
- 项目初期的"不够好"不是问题，问题是你是否知道哪里不够好、怎么改
- 这个项目从 MVP 到现在的演进过程本身就展示了这个权衡
