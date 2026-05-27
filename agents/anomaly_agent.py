import numpy as np
from core.llm import chat
import json


def detect_anomalies(data: list[dict], columns: list[str]) -> dict:
    numeric_cols = _find_numeric_cols(data, columns)
    if not numeric_cols:
        return {"has_anomaly": False, "anomalies": [], "summary": "无数值列可供检测"}

    anomalies = []

    for col in numeric_cols:
        values = np.array([row.get(col, 0) for row in data], dtype=float)
        valid_mask = ~np.isnan(values)
        values = values[valid_mask]

        if len(values) < 3:
            continue

        col_anomalies = []

        z_outliers = _zscore_detect(values, threshold=2.5)
        for idx in z_outliers:
            col_anomalies.append({
                "method": "Z-Score",
                "index": int(idx),
                "value": float(values[idx]),
                "reason": f"偏离均值 {abs(values[idx] - np.mean(values)) / np.std(values):.1f} 个标准差",
            })

        iqr_outliers = _iqr_detect(values)
        for idx in iqr_outliers:
            if idx not in z_outliers:
                col_anomalies.append({
                    "method": "IQR",
                    "index": int(idx),
                    "value": float(values[idx]),
                    "reason": f"超出四分位范围 (Q1={np.percentile(values, 25):.2f}, Q3={np.percentile(values, 75):.2f})",
                })

        for a in col_anomalies[:10]:
            original_idx = int(np.where(valid_mask)[0][a["index"]]) if a["index"] < len(valid_mask) else a["index"]
            row_context = data[original_idx] if original_idx < len(data) else {}
            a["row"] = row_context
            a["column"] = col

        anomalies.extend(col_anomalies)

    summary = _summarize(data, numeric_cols) if anomalies else "未检测到显著异常"

    return {
        "has_anomaly": len(anomalies) > 0,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:20],
        "summary": summary,
    }


async def explain_anomalies(question: str, anomaly_result: dict, data: list[dict]) -> str:
    if not anomaly_result["has_anomaly"]:
        return anomaly_result["summary"]

    messages = [
        {
            "role": "system",
            "content": "你是数据分析专家。用简洁的中文解释检测到的数据异常，给出业务建议。2-3句话。",
        },
        {
            "role": "user",
            "content": f"问题: {question}\n异常检测结果: {json.dumps(anomaly_result, ensure_ascii=False, default=str)}\n数据量: {len(data)}行",
        },
    ]
    return await chat(messages)


def _find_numeric_cols(data: list[dict], columns: list[str]) -> list[str]:
    numeric = []
    for col in columns:
        sample_vals = [row.get(col) for row in data[:20]]
        num_count = sum(1 for v in sample_vals if isinstance(v, (int, float)))
        if num_count > len(sample_vals) * 0.5:
            numeric.append(col)
    return numeric


def _zscore_detect(values: np.ndarray, threshold: float = 2.5) -> list[int]:
    std = np.std(values)
    if std == 0:
        return []
    mean = np.mean(values)
    z_scores = np.abs((values - mean) / std)
    return np.where(z_scores > threshold)[0].tolist()


def _iqr_detect(values: np.ndarray) -> list[int]:
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    if iqr == 0:
        return []
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return np.where((values < lower) | (values > upper))[0].tolist()


def _summarize(data: list[dict], numeric_cols: list[str]) -> str:
    parts = []
    for col in numeric_cols[:5]:
        values = np.array([row.get(col, 0) for row in data], dtype=float)
        values = values[~np.isnan(values)]
        if len(values) == 0:
            continue
        parts.append(
            f"  {col}: 均值={np.mean(values):.2f}, 中位数={np.median(values):.2f}, "
            f"标准差={np.std(values):.2f}, 范围=[{np.min(values):.2f}, {np.max(values):.2f}]"
        )
    return "数值统计:\n" + "\n".join(parts)
