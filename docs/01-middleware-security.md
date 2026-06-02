# 中间件与安全设计

## 中间件栈

Starlette 中间件按**注册的逆序**执行。我们在 app.py 中按以下顺序注册：

```python
app.add_middleware(ErrorHandlerMiddleware)    # 最后注册 = 最先执行（最外层）
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)  # 最先注册 = 最后执行（最内层）
```

实际请求流：`CORS → SecurityHeaders → Auth → RateLimit → Logging → ErrorHandler → Route`

## 5 个中间件的职责

### 1. ErrorHandlerMiddleware
- 捕获 `AppError` → 返回结构化 JSON 错误（含 error_code）
- 捕获未处理异常 → 生产环境返回 `"Internal server error"`，debug 模式返回原始错误
- 所有意外的异常都被兜底，不会返回 500 的 stack trace 给用户

### 2. RequestLoggingMiddleware
- 生成 `X-Request-ID`（或使用客户端传入的）
- 记录请求方法、路径、响应状态码、耗时
- 在响应头中返回 `X-Request-ID` 和 `X-Response-Time`
- **同时记录 Prometheus 指标**（请求计数、延迟直方图）

### 3. RateLimitMiddleware
- 基于 IP 的滑动窗口限流（deque + time.monotonic）
- 默认 60 次/分钟，超过返回 429
- X-Forwarded-For 只信任 `trusted_proxies` 配置的代理 IP
- 静态资源路径跳过限流

### 4. AuthMiddleware
- 检查 `X-API-Key` header（不使用 query param，避免 URL 泄露）
- 使用 `hmac.compare_digest` 防止时序攻击
- 空配置时拒绝所有请求（防止误配置导致开放）
- `/docs`、`/openapi.json` 在 auth 开启时也受保护

### 5. SecurityHeadersMiddleware
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: default-src 'self'`
- `Strict-Transport-Security: max-age=31536000`

## SQL 注入防护

### 多层防御策略

```
用户输入 → API 参数校验 → _validate_identifier() → 参数化查询 → 执行
```

1. **API 层**：所有 `table_name` 路径参数都经过 `_validate_identifier()` 校验
2. **Identifier 校验**：正则 `^[a-zA-Z_][a-zA-Z0-9_]*$` 严格限制格式
3. **参数化查询**：所有用户数据通过 `?` 占位符传入，杜绝 SQL 注入
4. **SQL 关键词拦截**：13 个危险关键词（DROP、DELETE、INSERT 等）正则匹配
5. **多语句拦截**：检测分号后跟非空白字符

### CSV 导入安全
- 文件名只用于推导表名（经过 `_validate_identifier`）
- 文件内容不写入磁盘，全在内存中处理
- 文件大小限制 50MB

---

## 面试高频问题

**Q: 中间件的执行顺序是怎么确定的？**
- Starlette（以及大多数 WSGI/ASGI 框架）中间件按注册逆序执行
- 最外层（最后注册的）先处理请求、最后处理响应
- 所以 ErrorHandler 放在最外层，能捕获所有内层的异常

**Q: 为什么用 `hmac.compare_digest` 而不是 `==`？**
- `==` 比较在第一个不匹配的字符就返回，攻击者可以通过响应时间差异逐字符爆破 API Key
- `hmac.compare_digest` 无论是否匹配都执行相同时间，防止时序攻击

**Q: X-Forwarded-For 为什么不能无条件信任？**
- 任何人都可以伪造这个 header
- 如果无条件信任，攻击者可以伪造 IP 绕过限流
- 只在 `trusted_proxies` 配置了代理 IP 时才信任该 header

**Q: CORS 设置 `allow_origins=["*"]` + `allow_credentials=True` 有什么问题？**
- CORS 规范不允许通配符 + credentials 同时使用
- 浏览器会拒绝这种组合的响应
- 我们的处理：通配符时自动设置 `allow_credentials=False`

**Q: 如果要加 RBAC（基于角色的访问控制）你会怎么做？**
- Auth 中间件改为从 token 解析用户角色
- 每个路由用 decorator 声明所需角色
- 例如 `@require_role("admin")` 装饰器
- 角色和权限存在数据库中，支持动态配置
