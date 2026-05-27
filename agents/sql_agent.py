import json
from core.llm import chat_json, chat
from core.database import get_full_schema
from core.context import ContextManager, summarize_history
from config import settings

SYSTEM_PROMPT = """你是一个专业的数据分析师和SQL专家。你的任务是将用户的自然语言问题转换为准确的SQL查询。

## 规则
1. 只生成 SELECT 查询，不要生成任何修改数据的语句
2. 使用 SQLite 方言
3. 表名和字段名必须与提供的schema完全一致
4. 日期处理使用 SQLite 函数 (date(), strftime() 等)
5. 对于模糊的时间描述:
   - "今天" -> DATE('now')
   - "昨天" -> DATE('now', '-1 day')
   - "本周" -> 使用 strftime('%W', date) = strftime('%W', 'now')
   - "本月" -> strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now')
   - "上月" -> 类似地用 '-1 month'
   - "最近N天" -> order_date >= DATE('now', '-N day')
6. 如果用户的问题无法用现有表回答，回复 error 字段说明原因
7. 始终使用中文别名 (AS 中文别名)
8. 数值保留2位小数，使用 ROUND()
9. 排序默认使用 DESC (从大到小)
10. 对订单状态注意: 已完成/已付款/已发货 表示有效订单，已取消表示无效

## 数据库Schema
{schema}
"""

_ctx = ContextManager(max_tokens=settings.context_max_tokens)


async def nl_to_sql(
    question: str,
    history: list[dict] | None = None,
    summary: str | None = None,
) -> dict:
    schema = get_full_schema()
    system = SYSTEM_PROMPT.format(schema=schema)

    messages = _ctx.build_messages(system, history or [], question, summary)

    messages[-1]["content"] += (
        "\n\n请生成SQL查询，以JSON格式返回: {\"sql\": \"...\", \"explanation\": \"...\", \"error\": null}"
    )

    try:
        result = await chat_json(messages, temperature=0, task_type="heavy")
        return {
            "sql": result.get("sql", ""),
            "explanation": result.get("explanation", ""),
            "error": result.get("error"),
        }
    except Exception as e:
        return {"sql": "", "explanation": "", "error": str(e)}


async def explain_result(question: str, sql: str, data: list[dict], columns: list[str]) -> str:
    if not data:
        return "查询没有返回数据。"

    preview = data[:20]
    messages = [
        {"role": "system", "content": "你是数据分析师，用简洁的中文解释查询结果中的关键发现。包含数字洞察，2-4句话。"},
        {"role": "user", "content": f"问题: {question}\nSQL: {sql}\n列: {columns}\n数据(前20行): {json.dumps(preview, ensure_ascii=False, default=str)}\n总行数: {len(data)}"},
    ]
    return await chat(messages, task_type="light")


async def fix_sql(sql: str, error: str, question: str) -> dict:
    schema = get_full_schema()
    messages = [
        {"role": "system", "content": f"你是SQL专家。修复以下报错的SQL。\n\nSchema:\n{schema}\n\n仅返回JSON: {{\"sql\": \"...\", \"explanation\": \"修复说明\"}}"},
        {"role": "user", "content": f"问题: {question}\n错误的SQL: {sql}\n报错信息: {error}"},
    ]
    try:
        result = await chat_json(messages, task_type="light")
        return {"sql": result.get("sql", ""), "explanation": result.get("explanation", "")}
    except Exception:
        return {"sql": "", "explanation": "无法自动修复SQL"}
