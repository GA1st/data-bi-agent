# NL→SQL Agent — 自然语言转 SQL

## 核心流程

```
用户问题 → ContextManager 构建 Prompt → LLM 生成 SQL → 安全校验 → 执行 → 结果
```

## sql_agent.py 设计

### prompt 工程

```
System Prompt 结构：
1. 角色定义 — "你是专业的数据分析师和 SQL 专家"
2. 数据库 Schema — 完整的 CREATE TABLE 语句（含注释）
3. 历史摘要 — 长对话压缩后的上下文
4. 最近对话 — 最近 N 轮问答对
5. 当前问题 — 用户的自然语言查询

输出要求：JSON 格式 {sql, explanation}
```

### 三种 LLM 调用场景

| 场景 | 函数 | 模型 | 理由 |
|------|------|------|------|
| NL→SQL | `nl_to_sql()` | heavy (gpt-4) | 需要理解语义 + 生成复杂 SQL |
| 解释结果 | `explain_result()` | light (gpt-4o-mini) | 简单总结任务 |
| 修复 SQL | `fix_sql()` | light (gpt-4o-mini) | 基于错误信息微调 |

### 自动 SQL 修复

```
SQL 执行失败 → fix_sql() 将错误信息 + 原始 SQL + 问题发给 LLM
              → LLM 返回修复后的 SQL
              → 重新执行
              → 仍然失败则返回错误给用户
```

## query_executor.py 安全机制

```python
validate_sql(sql):
  1. 空检查
  2. 必须以 SELECT/WITH 开头
  3. 13 个危险关键词正则匹配
  4. 多语句检测（分号后跟非空白字符）

add_limit(sql):
  - 自动追加 LIMIT 5000（如果原 SQL 没有 LIMIT）
  - 防止返回百万行数据导致内存溢出
```

---

## 面试高频问题

**Q: prompt 怎么设计的？为什么不用 Few-shot？**
- System prompt 包含完整 schema，LLM 能理解表关系
- 历史对话作为上下文隐式提供了 few-shot 效果
- 不硬编码 few-shot examples，因为用户的问题模式多变

**Q: 如果 LLM 生成了错误的 SQL 怎么办？**
- 第一道防线：validate_sql() 拦截非 SELECT 和危险关键词
- 第二道防线：执行失败后调用 fix_sql() 自动修复
- 第三道防线：修复仍失败则返回错误给用户，不静默吞错误

**Q: model downgrade 是怎么实现的？**
- `_resolve_model(model, task_type)` — 如果显式指定 model 则用指定的，否则按 task_type 路由
- `task_type="heavy"` → gpt-4（NL→SQL、报告叙事等复杂任务）
- `task_type="light"` → gpt-4o-mini（SQL 修复、图表建议、结果解释等简单任务）
- 降低成本：大部分请求只需要 light model，成本是 heavy model 的 1/10

**Q: Context management 解决了什么问题？**
- LLM 有 token 上限，历史对话太长会超限
- ContextManager 根据 token 预算裁剪历史：优先保留最近的对话
- 超过 threshold（默认 12 轮）时，调用 LLM 对历史做摘要压缩
- token 估算：中文约 2 tokens/字，英文约 1.3 tokens/word

**Q: 如何防止 prompt injection？**
- SQL 校验层会拦截所有非 SELECT 操作
- 用户输入不直接拼接到 SQL 中，而是作为 LLM prompt 的一部分
- LLM 输出经过 validate_sql() 二次校验
- 参数化查询确保即使 SQL 中有注入也无法执行
