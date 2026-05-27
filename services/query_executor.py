import re
from core.database import execute_query

MAX_ROWS = 5000
# Keywords that indicate data modification — blocked for safety
DANGEROUS_KEYWORDS = [
    r'\bDROP\b', r'\bDELETE\b', r'\bINSERT\b', r'\bUPDATE\b', r'\bALTER\b',
    r'\bCREATE\b', r'\bTRUNCATE\b', r'\bRENAME\b', r'\bATTACH\b', r'\bDETACH\b',
    r'\bPRAGMA\b', r'\bVACUUM\b', r'\bREINDEX\b',
]


def validate_sql(sql: str) -> tuple[bool, str]:
    stripped = sql.strip().upper()
    if not stripped:
        return False, "SQL不能为空"

    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        return False, "仅支持SELECT查询，不允许修改数据"

    for pattern in DANGEROUS_KEYWORDS:
        if re.search(pattern, stripped):
            kw = pattern.replace(r'\b', '')
            return False, f"SQL中包含不允许的关键词: {kw}"

    if re.search(r';\s*\S', sql):
        return False, "不允许执行多条SQL语句"

    return True, ""


def add_limit(sql: str, limit: int = MAX_ROWS) -> str:
    stripped = sql.strip().rstrip(";")
    upper = stripped.upper()
    if "LIMIT" not in upper:
        return f"{stripped} LIMIT {limit}"
    return stripped


def run_query(sql: str) -> dict:
    valid, msg = validate_sql(sql)
    if not valid:
        return {"success": False, "error": msg, "data": [], "columns": [], "row_count": 0}

    safe_sql = add_limit(sql)

    try:
        rows = execute_query(safe_sql)
        columns = list(rows[0].keys()) if rows else []
        return {
            "success": True,
            "data": rows,
            "columns": columns,
            "row_count": len(rows),
            "sql": safe_sql,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "columns": [],
            "row_count": 0,
            "sql": safe_sql,
        }
