# 定时任务、查询审计与可观测性

## 定时任务 (core/scheduler.py)

### 设计选型：为什么不用 APScheduler/Celery？

| 方案 | 弃用原因 |
|------|---------|
| APScheduler | Python 3.14 不兼容，且引入重度依赖 |
| Celery | 需要 Redis/RabbitMQ，过度设计 |
| XXL-Job | Java 生态，Python 客户端不成熟 |
| **threading + while loop** | 零依赖，满足简单定时需求 |

### 实现

```python
_lock = threading.Lock()
_jobs: list[dict] = []

def register_job(name, func, interval_seconds, enabled=True):
    with _lock:
        _jobs.append({...})

def _scheduler_loop():
    while _running:
        with _lock:
            snapshot = list(_jobs)  # 快照，避免迭代时修改
        for job in snapshot:
            if now - job["last_run"] >= job["interval"]:
                job["func"]()
                job["last_run"] = now
        time.sleep(interval)
```

- **线程安全**：register 和 loop 都用锁保护，loop 用快照避免迭代时修改
- **daemon 线程**：主进程退出时自动终止
- **app.py lifespan 管理**：启动时 `start_scheduler()`，关闭时 `stop_scheduler()`

### 内置 3 个任务

| 任务 | 间隔 | 功能 |
|------|------|------|
| data_quality | 5 min | 检查空表、异常表 |
| slow_query_audit | 2 min | 从审计日志中提取慢查询 |
| cache_stats | 10 min | 记录缓存命中率 |

## 查询审计 (services/query_audit.py)

### 缓冲写入设计

```python
_buffer: list[dict] = []
_MAX_BUFFER = 50

def record_query(sql, success, row_count, duration_ms, ...):
    with _lock:
        _buffer.append(entry)
        if len(_buffer) >= 50:
            _flush()  # 批量写入数据库

def _flush():
    for entry in _buffer:
        execute_update("INSERT INTO query_audit_log ...", entry)
```

- **缓冲 50 条**：减少数据库写入次数，提升性能
- **线程安全**：所有操作用 `threading.Lock` 保护
- **自动建表**：首次调用时 `CREATE TABLE IF NOT EXISTS`

### 审计字段

| 字段 | 说明 |
|------|------|
| sql | 执行的 SQL（截断 2000 字符）|
| success | 是否成功 |
| row_count | 返回行数 |
| duration_ms | 执行耗时（毫秒）|
| session_id | 来源会话 |
| source | 来源类型（chat/api） |
| created_at | 执行时间 |

### 统计接口

- `get_stats()` → 总查询数、平均耗时、慢查询数、失败数
- `get_recent(limit)` → 最近 N 条记录
- `get_recent_slow(threshold)` → 超过阈值的慢查询

## Prometheus 指标 (core/metrics.py)

### 零依赖实现

自实现 Prometheus text exposition format，不依赖 `prometheus_client` 库。

### 支持的指标类型

| 类型 | 用途 | 示例 |
|------|------|------|
| Counter | 单调递增计数 | `http_requests_total`, `queries_total` |
| Gauge | 可增可减的值 | `active_sessions`, `cache_hit_rate` |
| Histogram | 延迟分布 | `http_request_duration_ms`, `query_duration_ms` |

### 采集的指标

```
# HTTP 层（logging middleware 采集）
http_requests_total{method="GET", status="200"} 1234
http_request_duration_ms{method="POST", path="/api/chat"} 450.2

# 查询层（query_executor 采集）
queries_total{status="success"} 500
queries_total{status="rejected"} 12
query_duration_ms 230.5

# 缓存层
cache_hit_rate 0.85
cache_hits_total 1024
cache_misses_total 180

# 业务层
active_sessions 15
audit_total_queries 512
audit_failed_queries 3
```

### 访问方式

```
GET /api/system/metrics → text/plain，Prometheus 兼容格式
```

---

## 面试高频问题

**Q: 为什么审计用缓冲写入而不是每条直接写？**
- 每次查询都 INSERT 一次数据库，会增加查询延迟
- 缓冲 50 条批量写入，均摊了 I/O 开销
- 缺点是进程崩溃会丢失缓冲中的记录，但对于审计日志这是可接受的
- 如果要求零丢失，可以减小 `_MAX_BUFFER` 或改为 WAL 模式的同步写入

**Q: 如果定时任务执行时间超过间隔会怎样？**
- 当前实现是串行执行，一个任务超时会延迟后续任务
- 改进方案：每个任务用独立线程，或用 `concurrent.futures.ThreadPoolExecutor`
- 对于当前场景（数据质量检查、缓存统计），执行时间远小于间隔，不存在此问题

**Q: Prometheus metrics 为什么自己实现而不用 prometheus_client？**
- 项目目标是零新依赖（除了 fastapi/openai 等核心依赖）
- text exposition format 非常简单，自己实现不到 100 行
- 如果未来需要更丰富的指标类型（如 Summary 分位数），再引入也不迟

**Q: 如何基于这些指标做告警？**
- Prometheus + Alertmanager：配置 `query_duration_ms > 5000` 触发告警
- `cache_hit_rate < 0.5` → 缓存策略需要调整
- `audit_failed_queries` 持续增长 → SQL 生成质量下降
- `http_requests_total{status="500"}` 异常增长 → 服务端有问题
