# 分布式架构演进 — 从单机到可扩展

## 当前架构（单机）

```
┌────────── 浏览器 ──────────┐
│     SPA (ECharts/Marked)    │
└─────────────┬──────────────┘
              │ HTTP / SSE
┌─────────────▼──────────────┐
│     FastAPI (单进程)        │
│  中间件 → API → Agents      │
│  SQLite + 内存缓存 + 会话   │
└────────────────────────────┘
```

**适用场景**：10 人以下团队、日查询量 < 10 万、数据量 < 10GB

**单机瓶颈**：

| 组件 | 瓶颈 | 为什么 |
|------|------|--------|
| SQLite | 单写入者 | WAL 模式支持并发读，但写操作串行 |
| 内存缓存 | 单机不共享 | 多 Worker 各自独立缓存，命中率低 |
| 会话存储 | 进程重启丢失 | 内存中的对话历史，重启即清空 |
| 单进程 | CPU 利用率低 | 只用一个核心，无法利用多核 |

---

## 演进路线

### Phase 1：多 Worker（改动最小，收益最大）

```
┌──────── Nginx ─────────┐
│   负载均衡 / SSL 终止    │
└─────┬──────┬───────────┘
      │      │
┌─────▼──┐ ┌▼────────┐
│Worker 1│ │Worker 2 │  (Gunicorn, 各自无状态)
└───┬────┘ └──┬──────┘
    │         │
┌───▼─────────▼────────┐
│   SQLite (WAL 只读)    │  ← 仍然单机，但读性能翻倍
└──────────────────────┘
```

**改动点**：
- `app.py` 改用 `gunicorn -w 4 app:app` 启动
- 会话和缓存移到 Redis（多 Worker 共享）
- SQLite 只读场景完全够用

**效果**：吞吐量从 ~200 QPS → ~800 QPS

### Phase 2：数据库迁移（真正的分布式基础）

```
┌──────── Nginx ─────────┐
│   负载均衡 / SSL 终止    │
└─────┬──────┬───────────┘
      │      │
┌─────▼──┐ ┌▼────────┐
│Worker 1│ │Worker 2 │
└───┬────┘ └──┬──────┘
    │         │
┌───▼─────────▼──┐
│   PostgreSQL    │  ← 替代 SQLite
│   主从复制       │
└────────────────┘
```

**改动点**：
- `core/database.py` 用 SQLAlchemy Engine 替换 `sqlite3`
- 只改这一层，上层代码完全不动（**这就是分层的价值**）
- PostgreSQL 支持并发读写、MVCC、行级锁

**Repository Pattern**（我们当前代码已隐式做到）：

```python
# core/database.py 是唯一的数据库访问层
# 所有上层代码通过 execute_query() / execute_update() 调用
# 替换数据库只需改这一个文件

# 当前：
def execute_query(sql, params=None):
    conn = sqlite3.connect(...)
    return conn.execute(sql, params)

# 迁移后：
def execute_query(sql, params=None):
    engine = sqlalchemy.create_engine("postgresql://...")
    with engine.connect() as conn:
        return conn.execute(text(sql), params)
```

**效果**：写入性能从串行 → 并发，支持多个写入者

### Phase 3：OLAP 引擎（大数据量场景）

```
┌─────────── FastAPI Workers ───────────┐
│                                       │
│  ┌─ 小数据量 (< 1千万行) ──────────┐  │
│  │  → PostgreSQL (事务型查询)       │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ┌─ 大数据量 (> 1千万行) ──────────┐  │
│  │  → ClickHouse (列式 OLAP)       │  │
│  │  或 DuckDB (嵌入式 OLAP)        │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

**多数据源适配**（当前 `core/database.py` 可以扩展为）：

```python
class QueryEngine:
    """统一查询接口，底层路由到不同引擎"""
    def execute(self, sql: str, params=None) -> list[dict]:
        raise NotImplementedError

class SQLiteEngine(QueryEngine):     # 默认，零依赖
    ...

class PostgreSQLEngine(QueryEngine): # 生产级，并发读写
    ...

class ClickHouseEngine(QueryEngine): # 大数据量，列式查询
    ...

class DuckDBEngine(QueryEngine):     # 嵌入式 OLAP，零部署
    ...

# 路由逻辑
def get_engine(dataset_size: str = "small") -> QueryEngine:
    if dataset_size == "large":
        return ClickHouseEngine()
    return SQLiteEngine()
```

**效果**：亿级数据秒级查询，真正的 BI 分析能力

### Phase 4：微服务拆分（万级 QPS 场景）

```
┌──────── API Gateway ────────┐
│  认证 / 限流 / 路由          │
└──┬──────┬──────┬──────┬─────┘
   │      │      │      │
┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐
│Chat ││Dash ││Data ││Auth │  各服务独立部署、独立扩缩容
│Svc  ││Svc  ││Svc  ││Svc  │
└──┬──┘└──┬──┘└──┬──┘└─────┘
   │      │      │
   ▼      ▼      ▼
 Redis  ClickHouse PostgreSQL
```

**拆分原则**：
- Chat Service：有状态（SSE 长连接），需要独立扩缩容
- Dashboard Service：无状态，缓存报表数据
- Data Explorer Service：无状态，代理查询请求
- Auth Service：独立认证中心，支持 OAuth/JWT

**通信方式**：
- 服务内：直接函数调用（当前方式）
- 跨服务：gRPC（低延迟）或 REST（简单）
- 事件驱动：Redis Stream / Kafka（异步任务）

---

## 分布式缓存设计

```python
# 当前：单机 TTLCache
class TTLCache:
    _store: dict[str, tuple[value, expires_at]]
    # 优点：零依赖、延迟低
    # 缺点：单机不共享、重启丢失

# 演进：Redis 后端
class RedisCache(TTLCache):
    def __init__(self, redis_url):
        self._redis = redis.from_url(redis_url)

    def get(self, key):
        data = self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    def set(self, key, value, ttl):
        self._redis.setex(key, ttl, json.dumps(value))

# 使用方代码完全不变
cache.set("schema", schema_text)    # 不关心后端是 dict 还是 Redis
result = cache.get("schema")        # 接口一致
```

## 会话存储演进

```
单机内存 (当前) → Redis (多 Worker) → 数据库 (持久化)
     ↓                  ↓                    ↓
  dict 存储         Redis Hash           PostgreSQL
  重启丢失           多 Worker 共享         跨重启保留
  100 会话           10 万会话             无限会话
```

---

## 数据管道（完整的 BI 还需要什么）

当前项目覆盖了"查询 → 可视化"环节。完整的 BI 系统还需要：

```
数据源 → 抽取 → 清洗 → 入库 → 分析 → 可视化
          ↑              ↑
        Airflow       dbt / SQL
      (任务调度)     (数据建模)
```

**可以加的组件**：

| 组件 | 作用 | 替代方案 |
|------|------|---------|
| Airflow | DAG 任务调度 | DolphinScheduler (国产) |
| dbt | SQL 数据建模 + 测试 | 手写 migration 脚本 |
| Great Expectations | 数据质量监控 | 当前 scheduler 已有简化版 |
| MinIO / S3 | 数据湖存储 | 本地文件系统 |
| Metabase / Superset | 报表分享 | 当前的 dashboard 页面 |

---

## 面试高频问题

**Q: 为什么不一开始就做成分布式的？**
- YAGNI 原则（You Aren't Gonna Need It）
- 单机 SQLite 能覆盖 95% 的 BI 使用场景
- 过早引入分布式会增加部署复杂度和运维成本
- 代码分层做得好，迁移成本很低

**Q: 分布式系统最大的挑战是什么？**
- **一致性**：缓存在多个 Worker 间可能不一致（解决方案：Redis Pub/Sub 失效广播）
- **幂等性**：LLM 调用不幂等，重试可能产生不同结果（解决方案：缓存 LLM 响应）
- **会话亲和性**：SSE 长连接需要路由到同一个 Worker（解决方案：Nginx ip_hash / sticky session）

**Q: ClickHouse 和 PostgreSQL 的区别？什么时候用哪个？**
- PostgreSQL：行存储，适合事务型操作（增删改查），万级数据秒出
- ClickHouse：列存储，适合分析型操作（聚合、GROUP BY），亿级数据秒出
- 规则：数据量 < 千万行用 PostgreSQL，> 千万行用 ClickHouse
- 可以共存：PostgreSQL 做业务库，通过 CDC 同步到 ClickHouse 做分析

**Q: 如果让你重新设计这个项目的架构，你会怎么做？**
- 保持分层不变（core / services / agents / api）
- database.py 改为 Repository Pattern，支持多引擎
- 加 DuckDB 作为嵌入式 OLAP 引擎（零部署，性能接近 ClickHouse）
- 缓存接口抽象化，本地开发用内存，生产用 Redis
- 加一个数据管道模块，支持定时从外部数据源同步

**Q: 你怎么看待微服务 vs 单体？**
- 看团队规模和业务复杂度
- 5 人以下团队：单体 > 微服务（运维成本低，开发效率高）
- 20 人以上团队：按业务域拆分微服务
- BI Agent 是典型的"数据密集型"而非"流量密集型"，单体 + 好的数据库就够了
- 真正需要分布式的是数据层（ClickHouse 集群），而不是应用层
