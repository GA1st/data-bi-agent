# 可视化、异常检测与自动报表

## Chart Agent (agents/chart_agent.py)

### 设计思路

```python
async def suggest_chart(question, sql, data, columns):
    # light model 推荐图表类型 + ECharts 配置
    messages = [
        {"role": "system", "content": "根据数据和问题推荐 ECharts 图表配置..."},
        {"role": "user", "content": f"问题: {question}\n数据: {data[:20]}\n列: {columns}"}
    ]
    return await chat_json(messages, task_type="light")
```

- 使用 **light model**（gpt-4o-mini），因为图表推荐是结构化输出任务
- 返回 ECharts option JSON，前端直接 `setOption()` 渲染
- **降级兜底**：LLM 失败时 `_fallback_chart()` 根据列类型自动生成基础图表

### 前端 ECharts 渲染

- SSE 流中收到 `type: "chart"` 事件后，前端调用 `echarts.setOption()`
- 暗色主题统一配置
- 响应式布局：图表容器自动 resize

## Anomaly Agent (agents/anomaly_agent.py)

### 纯统计算法，不依赖 LLM

**两种检测方法并行执行：**

#### 1. Z-Score 检测
```python
mean = np.mean(values)
std = np.std(values)
for v in values:
    z_score = abs(v - mean) / std
    if z_score > 2.5:  # 超过 2.5 个标准差
        anomalies.append(...)
```
- 适用：正态分布数据
- 阈值 2.5σ → 约 98.7% 置信度

#### 2. IQR 检测
```python
Q1, Q3 = np.percentile(values, [25, 75])
IQR = Q3 - Q1
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR
```
- 适用：非正态分布数据（如偏态销售数据）
- 不受极端值影响（中位数比均值更鲁棒）

**合并结果**：两种方法取并集，减少漏检

### 返回结构
```json
{
  "has_anomaly": true,
  "anomaly_count": 3,
  "anomalies": [
    {"index": 5, "column": "revenue", "value": 50000, "expected_range": [1000, 8000], "method": "zscore"}
  ],
  "summary": "检测到 3 个异常值..."
}
```

## Report Agent (agents/report_agent.py)

### 报表生成流水线

```
KPIs → 趋势 → Top产品 → 区域分布 → 异常检测 → LLM 叙事 → ECharts 图表
```

### KPI 查询（8 个核心指标）

| 指标 | SQL 特点 |
|------|---------|
| 总销售额 | `SUM + WHERE status != '已取消'` |
| 订单总数 | `COUNT` |
| 客户数 | 独立表 COUNT |
| 平均客单价 | `AVG` |
| 今日/本月销售额 | `DATE()` / `strftime()` 时间过滤 |
| 取消率 | `CASE WHEN` 条件计数 + 百分比 |

### LLM 叙事生成

```python
async def _generate_narrative(report_data):
    messages = [
        {"role": "system", "content": "根据数据指标撰写经营分析摘要..."},
        {"role": "user", "content": f"报告数据:\n{json.dumps(report_data)}"}
    ]
    return await chat(messages, task_type="heavy")
```

- 使用 **heavy model**，因为需要综合分析 + 生成文本
- **优雅降级**：LLM 不可用时返回固定文本，不影响 KPI 和图表展示
- 300 字以内，要求包含趋势判断、异常提醒和行动建议

### ECharts 图表配置

自动生成 3 种图表：
1. **趋势图**：折线（销售额）+ 柱状（订单数）双 Y 轴
2. **Top 产品**：水平柱状图
3. **区域分布**：环形饼图

---

## 面试高频问题

**Q: 为什么异常检测不用 LLM？**
- 统计算法更可靠：确定性输出，不依赖 prompt 质量
- 成本更低：纯计算，无 API 调用
- 延迟更低：毫秒级 vs 秒级
- LLM 适合做解释（为什么异常），但不适合做检测（是否异常）

**Q: Z-Score 和 IQR 各有什么局限？**
- Z-Score 假设正态分布，偏态数据不准确
- IQR 对小样本不敏感，数据量太少时检测不到异常
- 所以两种方法并行，取并集降低漏检率

**Q: 报表生成的降级策略是什么？**
- LLM 叙事失败不影响数据展示：KPI、图表照样显示
- 前端在 LLM 不可用时显示默认文本
- 这体现了"核心功能不依赖可选组件"的设计原则

**Q: 如果数据量很大（百万行），报表查询会变慢怎么办？**
- 当前已有 LIMIT 保护
- 可以在数据库层做预聚合（物化视图 / 定时汇总表）
- 报表数据通常按天/月聚合，可以缓存聚合结果
- 趋势图只需要 12 个月的数据，查询量本身不大
