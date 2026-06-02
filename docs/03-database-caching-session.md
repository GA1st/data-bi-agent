# 数据库、缓存与会话管理

## 数据库层 (core/database.py)

### 线程安全设计

```python
_local = threading.local()  # 每个线程独立的数据库连接

def _get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")      # WAL 模式支持并发读写
        conn.execute("PRAGMA foreign_keys=ON")         # 启用外键约束
        _local.conn = conn
    return conn
```

**为什么用 `threading.local()`？**
- SQLite 连接不能跨线程共享
- FastAPI 用线程池处理同步路由，每个线程需要自己的连接
- 比 `check_same_thread=False` + 全局连接更安全

**WAL 模式的好处？**
- 读操作不阻塞写操作，写操作不阻塞读操作
- 适合 Web 服务的高并发读场景
- 比 DELETE journal 模式性能提升 30-50%

### Schema 缓存

```python
def get_full_schema():
    cached = cache.get("db_full_schema")  # TTL 缓存
    if cached:
        return cached
    # 构建完整 schema...
    cache.set("db_full_schema", schema)
    return schema
```
- 每次 NL→SQL 都需要 schema，缓存避免重复构建
- TTL 到期自动刷新，数据库变更后也能感知

## TTL 缓存 (core/cache.py)

### 实现要点

```python
class TTLCache:
    _store: dict[str, tuple[value, expires_at]]

    def get(key):
        entry = _store[key]
        if time.monotonic() > entry.expires_at:
            del _store[key]  # 惰性删除
            return None
        return entry.value

    def set(key, value):
        if len(_store) >= max_size:
            _evict_oldest()  # 淘汰最早过期的
        _store[key] = (value, time.monotonic() + ttl)
```

- **线程安全**：所有操作用 `threading.Lock` 保护
- **惰性过期**：get 时检查过期，不启动后台清理线程
- **容量淘汰**：超过 max_size 时淘汰最早过期的 key
- **缓存命中率**：通过全局计数器 `_hits/_misses` 追踪，暴露到 Prometheus metrics

### @cached 装饰器

```python
@cached(key_prefix="schema", ttl=300)
def get_full_schema():
    ...
```
- 自动生成缓存 key：`{prefix}:{func.__qualname__}`
- 命中时直接返回缓存，未命中时执行函数并缓存结果

## 会话管理 (core/session.py)

### 设计

```python
class SessionManager:
    _sessions: OrderedDict[str, dict]  # {session_id: {history, summary}}
    _max_sessions = 100
    MAX_HISTORY_PER_SESSION = 30
```

- **OrderedDict**：支持 LRU 淘汰（`move_to_end` + `popitem(last=False)`）
- **会话通过 `X-Session-ID` header 识别**（格式校验：`^[a-zA-Z0-9_-]{1,64}$`）
- **自动淘汰**：超过 100 个会话时淘汰最久未访问的
- **历史限制**：每个会话最多 30 条记录

### 会话隔离

- 不同的 `X-Session-ID` → 完全独立的对话历史
- 无 header 时共享 `"default"` 会话（开发便利）
- 会话数据纯内存，重启丢失（适合 BI 查询场景）

---

## 面试高频问题

**Q: 为什么不直接用 Redis 做缓存？**
- 项目是单机部署的 BI 工具，内存缓存足够
- 避免引入外部依赖，降低部署复杂度
- 如果需要扩展，TTLCache 的接口可以替换为 Redis 实现

**Q: 缓存的淘汰策略为什么选"最早过期"而不是 LRU？**
- TTL 缓存中，已过期或即将过期的数据价值最低
- LRU 需要维护访问顺序链表，实现更复杂
- 结合 max_size 和 TTL，双重保护内存不被撑爆

**Q: OrderedDict 做 LRU 的复杂度？**
- `move_to_end()`：O(1)
- `popitem(last=False)`：O(1)
- 比手写双向链表更简洁，性能相当

**Q: 如果要做分布式会话你会怎么改？**
- SessionManager 改为 Redis/数据库后端
- session_id 改为 JWT token，携带用户信息
- 历史记录序列化存储到 Redis，支持跨实例共享

**Q: SQLite 的并发上限是多少？**
- WAL 模式下支持多个并发读者 + 一个写入者
- 写入会短暂获取锁，但 WAL 的锁持有时间远短于 DELETE 模式
- 对于 BI 查询场景（读多写少），性能完全足够
- 如果写入压力大，可以切换到 PostgreSQL
