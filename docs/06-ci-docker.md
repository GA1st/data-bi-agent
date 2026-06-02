# CI/CD 与 Docker 部署

## GitHub Actions Pipeline

### 三个 Job

```yaml
jobs:
  lint:     # Ruff lint 检查
  test:     # 运行 25 个测试
  docker:   # 构建镜像 + 冒烟测试（依赖 lint + test 通过）
```

### 设计要点

- **lint + test 并行**：互不依赖，加快 CI 速度
- **docker 依赖前两个**：只有代码质量检查通过才构建镜像
- **冒烟测试**：启动容器 → sleep 5s → curl 首页 → 确认服务可访问
- **Python 3.12**：用稳定版本，避免 3.14 兼容性问题

### 触发条件

- push 到 `main`/`master`
- PR 到 `main`/`master`

## Docker 部署

### Dockerfile 设计

```dockerfile
FROM python:3.12-slim          # 精简基础镜像（~150MB vs 1GB+）

COPY requirements.txt .        # 先复制依赖文件
RUN pip install ...             # 依赖层缓存（代码变不影响）

COPY . .                       # 再复制源码

RUN adduser --disabled-password appuser
USER appuser                    # 非 root 运行

HEALTHCHECK --interval=30s ...  # 健康检查
```

### 安全实践

| 实践 | 说明 |
|------|------|
| 非 root 用户 | `adduser appuser` + `USER appuser` |
| .dockerignore | 排除 `.env`、`.git`、`__pycache__`、`*.db` |
| HEALTHCHECK | Docker/orchestrator 自动检测服务健康 |
| 精简镜像 | `python:3.12-slim` 而非 `python:3.12` |
| 分层缓存 | requirements.txt 先复制，代码变更不重新安装依赖 |

### docker-compose.yml

```yaml
services:
  bi-agent:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data       # 数据持久化
      - ./.env:/app/.env:ro    # 只读配置
    restart: unless-stopped
```

### 部署命令

```bash
# 开发
docker compose up --build

# 生产
docker compose up -d
docker compose logs -f
```

---

## 面试高频问题

**Q: Dockerfile 分层缓存的原理是什么？**
- Docker 构建是分层（layer）的，每条指令产生一层
- 如果某层没变，Docker 会复用缓存，不重新执行
- `COPY requirements.txt` + `RUN pip install` 放在 `COPY . .` 前面
- 这样只有依赖变化时才重新安装，代码变更只重新复制源码

**Q: 为什么用非 root 用户？**
- 容器默认 root 运行，如果被攻破，攻击者拥有宿主机 root 权限（在某些场景下）
- `USER appuser` 后，进程只能访问 appuser 有权限的文件
- 即使容器被入侵，攻击者的权限也被限制

**Q: HEALTHCHECK 的作用？**
- Docker 引擎定期执行检查命令
- 健康检查失败 → 容器状态变为 unhealthy
- 配合 docker-compose `restart: unless-stopped` → 自动重启
- Kubernetes 的 liveness/readiness probe 也依赖类似机制

**Q: 如果要部署到生产环境还需要什么？**
- HTTPS：Nginx/Caddy 反向代理 + Let's Encrypt
- 数据库持久化：挂载 volume 到独立存储
- 监控：Prometheus 抓取 `/api/system/metrics`
- 日志：JSON 格式日志 → ELK/Loki 收集
- 负载均衡：如果并发高，前面加 Nginx 做负载均衡
- CI/CD：GitHub Actions 构建镜像 → 推送到镜像仓库 → 自动部署
