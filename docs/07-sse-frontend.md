# SSE 流式通信与前端设计

## SSE (Server-Sent Events)

### 为什么用 SSE 而不是 WebSocket？

| 维度 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 服务端 → 客户端（单向） | 双向 |
| 协议 | 标准 HTTP | 升级协议 |
| 重连 | 浏览器自动重连 | 需要手动实现 |
| 兼容性 | 所有浏览器 + 代理 | 部分代理不支持 |
| 复杂度 | 低 | 高 |

**选择 SSE 的理由**：BI 查询是"一问一答"模式，客户端发送请求后只需要接收服务端的流式推送，不需要双向通信。

### SSE 事件流设计

```
→ {type: "status", message: "正在分析您的问题..."}
→ {type: "sql", sql: "SELECT ...", explanation: "..."}
→ {type: "status", message: "正在执行查询..."}
→ {type: "data", data: [...], columns: [...], row_count: 42}
→ {type: "chart", chart: {echarts option}}
→ {type: "anomaly", anomaly: {...}}       // 可选
→ {type: "explanation", message: "..."}
→ {type: "done"}
```

每个阶段完成后立即推送，用户能看到实时进度。

### 后端实现

```python
@router.post("/api/chat")
async def chat_endpoint(req, session_id):
    async def stream():
        yield sse({"type": "status", "message": "..."})

        sql_result = await nl_to_sql(...)       # 耗时 ~2s
        yield sse({"type": "sql", ...})

        query_result = run_query(sql)           # 耗时 ~0.1s
        yield sse({"type": "data", ...})

        chart = await suggest_chart(...)        # 耗时 ~1s
        yield sse({"type": "chart", ...})

        # ...
        yield sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream")
```

### 前端实现

```javascript
const es = new EventSource("/api/chat", {headers: {"X-Session-ID": sessionId}});
// 注意：实际用 fetch + ReadableStream，因为 POST 请求不支持 EventSource API

const response = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Session-ID": sessionId},
    body: JSON.stringify({message: input})
});

const reader = response.body.getReader();
while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    // 解析 SSE 行，按 type 分发到 UI 更新
}
```

## 前端 SPA 架构

### 四页路由

| 页面 | 功能 | 核心 API |
|------|------|---------|
| Dashboard | KPI 卡片 + 图表 | `/api/dashboard/report` |
| AI Chat | SSE 对话 + 图表渲染 | `/api/chat` (POST, SSE) |
| Explorer | 表浏览 + 分页 | `/api/tables`, `/api/tables/{name}/data` |
| Saved Queries | 保存的查询管理 | `/api/saved-queries` (CRUD) |

### 文件组织

```
static/
├── index.html        # SPA 壳 + 侧边栏导航
├── css/style.css     # 暗色主题 + CSS 变量
└── js/
    ├── app.js        # 全局状态、导航、工具函数
    ├── chat.js       # SSE 流式处理
    └── dashboard.js  # 报表渲染 + Explorer + Saved
```

- **无构建工具**：原生 JS + CSS，零依赖
- **暗色主题**：CSS 变量统一管理配色
- **响应式**：CSS Grid + Flexbox

---

## 面试高频问题

**Q: SSE 和 WebSocket 的主要区别？什么时候用哪个？**
- SSE 基于 HTTP，单向推送，适合服务端向客户端发送状态更新
- WebSocket 是独立协议，双向通信，适合聊天室、协作编辑等实时交互
- BI 查询场景是"请求 → 多阶段推送"，SSE 更简单更合适

**Q: SSE 怎么配合中间件？**
- `BaseHTTPMiddleware` 会缓冲 `StreamingResponse` 的内容
- 但由于我们直接 `yield` 字符串（不是 generator of chunks），中间件能正常传递
- 如果遇到问题，可以改用纯 ASGI middleware（不继承 BaseHTTPMiddleware）

**Q: 前端为什么不用 React/Vue？**
- 项目是 BI 工具，不是复杂的交互应用
- 4 个页面的 SPA 用原生 JS 完全够用
- 避免引入构建工具链（webpack/vite），降低项目复杂度
- 如果页面增多或交互变复杂，可以迁移到 Vue（CDN 引入即可）

**Q: 如果要做实时协作（多人同时看一个报表）你会怎么做？**
- WebSocket 建立双向通道
- 服务端维护房间（room）概念
- 一个用户修改查询 → 广播给同房间的其他用户
- 用 Redis Pub/Sub 实现跨进程消息传递
