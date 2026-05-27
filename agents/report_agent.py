import json
from core.llm import chat
from core.database import execute_query
from core.logger import get_logger

logger = get_logger(__name__)


async def generate_report(report_type: str = "daily") -> dict:
    kpis = _get_kpis()
    trends = _get_trends()
    top_products = _get_top_products()
    region_dist = _get_region_distribution()
    anomalies = _get_anomaly_summary()

    report_data = {
        "type": report_type,
        "kpis": kpis,
        "trends": trends,
        "top_products": top_products,
        "region_distribution": region_dist,
        "anomalies": anomalies,
    }

    narrative = await _generate_narrative(report_data)
    report_data["narrative"] = narrative or "报告生成需要配置 LLM API Key。"

    charts = _generate_report_charts(kpis, trends, top_products, region_dist)
    report_data["charts"] = charts

    return report_data


def _get_kpis() -> dict:
    queries = {
        "total_revenue": "SELECT ROUND(SUM(total_amount), 2) as v FROM orders WHERE status != '已取消'",
        "total_orders": "SELECT COUNT(*) as v FROM orders WHERE status != '已取消'",
        "total_customers": "SELECT COUNT(*) as v FROM customers",
        "avg_order_amount": "SELECT ROUND(AVG(total_amount), 2) as v FROM orders WHERE status != '已取消'",
        "today_revenue": "SELECT ROUND(SUM(total_amount), 2) as v FROM orders WHERE DATE(order_date) = DATE('now') AND status != '已取消'",
        "month_revenue": "SELECT ROUND(SUM(total_amount), 2) as v FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now') AND status != '已取消'",
        "month_orders": "SELECT COUNT(*) as v FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now') AND status != '已取消'",
        "cancel_rate": "SELECT ROUND(CAST(SUM(CASE WHEN status='已取消' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as v FROM orders",
    }
    result = {}
    for key, sql in queries.items():
        rows = execute_query(sql)
        result[key] = rows[0]["v"] if rows and rows[0]["v"] is not None else 0
    return result


def _get_trends() -> list[dict]:
    return execute_query("""
        SELECT
            strftime('%Y-%m', order_date) as month,
            COUNT(*) as order_count,
            ROUND(SUM(total_amount), 2) as revenue,
            ROUND(AVG(total_amount), 2) as avg_amount
        FROM orders
        WHERE status != '已取消'
        GROUP BY strftime('%Y-%m', order_date)
        ORDER BY month DESC
        LIMIT 12
    """)


def _get_top_products() -> list[dict]:
    return execute_query("""
        SELECT
            p.name as product_name,
            c.name as category,
            SUM(oi.quantity) as total_qty,
            ROUND(SUM(oi.subtotal), 2) as total_revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != '已取消'
        GROUP BY p.id
        ORDER BY total_revenue DESC
        LIMIT 10
    """)


def _get_region_distribution() -> list[dict]:
    return execute_query("""
        SELECT
            region,
            COUNT(*) as order_count,
            ROUND(SUM(total_amount), 2) as revenue,
            ROUND(AVG(total_amount), 2) as avg_order
        FROM orders
        WHERE status != '已取消'
        GROUP BY region
        ORDER BY revenue DESC
    """)


def _get_anomaly_summary() -> dict:
    daily = execute_query("""
        SELECT
            DATE(order_date) as date,
            ROUND(SUM(total_amount), 2) as revenue,
            COUNT(*) as orders
        FROM orders
        WHERE status != '已取消'
        GROUP BY DATE(order_date)
        ORDER BY date DESC
        LIMIT 30
    """)
    if len(daily) < 7:
        return {"status": "数据不足", "details": []}

    revenues = [d["revenue"] for d in daily]
    import numpy as np
    arr = np.array(revenues, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)
    anomalies = []
    for i, rev in enumerate(revenues):
        if std > 0 and abs(rev - mean) / std > 2:
            anomalies.append({
                "date": daily[i]["date"],
                "revenue": rev,
                "deviation": f"{(rev - mean) / std:.1f}σ",
            })
    return {"status": f"检测到{len(anomalies)}个异常日", "details": anomalies[:5]}


async def _generate_narrative(report_data: dict) -> str | None:
    try:
        messages = [
            {
                "role": "system",
                "content": "你是高级数据分析师。根据以下数据指标，用简洁专业的中文撰写一份经营分析摘要。包括关键数据、趋势判断、异常提醒和行动建议。不超过300字。",
            },
            {
                "role": "user",
                "content": f"报告数据:\n{json.dumps(report_data, ensure_ascii=False, default=str)}",
            },
        ]
        return await chat(messages, task_type="heavy")
    except Exception as e:
        logger.warning(f"Narrative generation failed: {e}")
        return None


def _generate_report_charts(kpis, trends, top_products, region_dist) -> dict:
    charts = {}

    if trends:
        months = [t["month"] for t in reversed(trends)]
        revenues = [t["revenue"] for t in reversed(trends)]
        orders = [t["order_count"] for t in reversed(trends)]
        charts["trend"] = {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["销售额", "订单数"]},
            "xAxis": {"type": "category", "data": months},
            "yAxis": [
                {"type": "value", "name": "销售额"},
                {"type": "value", "name": "订单数"},
            ],
            "series": [
                {"name": "销售额", "type": "line", "data": revenues, "smooth": True, "areaStyle": {"opacity": 0.3}},
                {"name": "订单数", "type": "bar", "yAxisIndex": 1, "data": orders},
            ],
        }

    if top_products:
        charts["top_products"] = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "xAxis": {"type": "value", "name": "销售额"},
            "yAxis": {"type": "category", "data": [p["product_name"] for p in reversed(top_products)]},
            "series": [{"name": "销售额", "type": "bar", "data": [p["total_revenue"] for p in reversed(top_products)]}],
        }

    if region_dist:
        charts["region"] = {
            "tooltip": {"trigger": "item"},
            "series": [{
                "type": "pie",
                "radius": ["40%", "70%"],
                "data": [{"name": r["region"], "value": r["revenue"]} for r in region_dist],
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
            }],
        }

    return charts
