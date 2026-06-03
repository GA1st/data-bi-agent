# Data BI Agent

智能数据分析 + BI Agent — 自然语言查询数据库、自动生成报表、异常检测。

## 功能

- **自然语言 → SQL**：用户用中文提问，AI 自动生成 SQL 查询
- **自动可视化**：根据查询结果自动推荐 ECharts 图表
- **异常检测**：Z-Score + IQR 双算法检测数据异常
- **自动报表**：一键生成 KPI、趋势、Top 产品、区域分布报表
- **多数据源**：支持 CSV 文件上传导入
- **SSE 流式响应**：对话过程实时推送进度

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key（不填也可以运行，AI 功能会降级）

# 启动
python app.py
```

访问 http://localhost:8000

## Docker 部署

```bash
docker compose up --build
```

## 运行测试

```bash
python tests/run_tests.py
```

## API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger 文档。

主要接口：

| 接口 | 说明 |
|------|------|
| `POST /api/chat` | AI 对话（SSE 流式） |
| `GET /api/dashboard/report` | 获取报表数据 |
| `GET /api/tables` | 数据表列表 |
| `GET /api/tables/{name}/data` | 表数据浏览（分页） |
| `POST /api/system/upload/csv` | CSV 文件上传 |
| `GET /api/system/metrics` | Prometheus 指标 |
| `GET /api/system/audit/stats` | 查询审计统计 |

## 技术栈

- **后端**：FastAPI + SQLite (WAL) + OpenAI-compatible LLM
- **前端**：原生 SPA + ECharts
- **基础设施**：5 层中间件（认证/限流/日志/错误处理/安全头）、TTL 缓存、会话管理、定时任务、查询审计、Prometheus 指标
- **部署**：Docker + GitHub Actions CI/CD

## 项目结构

```
├── app.py              # 入口
├── config.py           # 配置
├── core/               # 核心层（数据库/LLM/缓存/会话/中间件/指标/调度）
├── agents/             # 智能体（SQL/图表/异常/报表）
├── services/           # 服务层（查询执行/审计/数据源）
├── api/                # API 路由
├── static/             # 前端 SPA
├── tests/              # 测试套件
└── docs/               # 面试文档
```

## License

MIT
