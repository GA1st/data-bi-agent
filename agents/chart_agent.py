import json
from core.llm import chat_json


async def suggest_chart(question: str, sql: str, data: list[dict], columns: list[str]) -> dict:
    if not data or len(data) == 0:
        return {"chart_type": "none", "config": {}}

    preview = data[:30]
    messages = [
        {
            "role": "system",
            "content": """你是数据可视化专家。根据用户的查询和返回的数据，推荐最佳图表类型并生成 ECharts 配置。

支持的图表类型:
- bar: 柱状图 (比较不同类别的数值)
- line: 折线图 (展示趋势变化)
- pie: 饼图 (展示占比)
- scatter: 散点图 (展示相关性)

规则:
1. 使用 ECharts option 格式
2. 标题、标签、图例全部用中文
3. 合理使用 tooltip
4. 时间序列数据用 line 图
5. 类别占比用 pie 图 (不超过10个分类)

返回JSON:
{
  "chart_type": "bar|line|pie|scatter|table",
  "reason": "选择原因",
  "config": { ECharts option 对象 }
}""",
        },
        {
            "role": "user",
            "content": f"问题: {question}\nSQL: {sql}\n列名: {columns}\n数据: {json.dumps(preview, ensure_ascii=False, default=str)}\n总行数: {len(data)}",
        },
    ]

    try:
        result = await chat_json(messages, temperature=0.1, task_type="light")
        return result
    except Exception:
        return _fallback_chart(data, columns)


def _fallback_chart(data: list[dict], columns: list[str]) -> dict:
    if len(columns) < 2:
        return {"chart_type": "table", "reason": "数据列不足，使用表格展示", "config": {}}

    x_col = columns[0]
    y_cols = [c for c in columns[1:] if isinstance(data[0].get(c), (int, float))]

    if not y_cols:
        return {"chart_type": "table", "reason": "无数值列，使用表格展示", "config": {}}

    x_data = [str(row[x_col]) for row in data[:30]]
    series = []
    for yc in y_cols[:4]:
        series.append({
            "name": yc,
            "type": "bar",
            "data": [row.get(yc, 0) for row in data[:30]],
        })

    config = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [s["name"] for s in series]},
        "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 30}},
        "yAxis": {"type": "value"},
        "series": series,
    }
    return {"chart_type": "bar", "reason": "默认柱状图", "config": config}
