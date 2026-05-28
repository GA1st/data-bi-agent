"""
Query audit log — records all executed queries with timing and metadata.
Persists to SQLite table 'query_audit_log'.
"""
import threading
import time
from datetime import datetime

from core.logger import get_logger
from core.exceptions import DatabaseError

logger = get_logger(__name__)

_lock = threading.Lock()
_buffer: list[dict] = []
_MAX_BUFFER = 50
_initialized = False


def _ensure_table():
    global _initialized
    if _initialized:
        return
    try:
        from core.database import execute_update
        execute_update("""
            CREATE TABLE IF NOT EXISTS query_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                sql TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                row_count INTEGER DEFAULT 0,
                duration_ms REAL,
                source TEXT DEFAULT 'chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _initialized = True
    except Exception:
        pass  # may fail during early init


def record_query(
    sql: str,
    success: bool = True,
    row_count: int = 0,
    duration_ms: float = 0,
    session_id: str = "",
    source: str = "chat",
):
    _ensure_table()
    entry = {
        "sql": sql[:2000],
        "success": 1 if success else 0,
        "row_count": row_count,
        "duration_ms": round(duration_ms, 1),
        "session_id": session_id,
        "source": source,
    }
    with _lock:
        _buffer.append(entry)
        if len(_buffer) >= _MAX_BUFFER:
            _flush()


def _flush():
    if not _buffer:
        return
    entries = _buffer.copy()
    _buffer.clear()
    try:
        from core.database import execute_update
        for e in entries:
            execute_update(
                """INSERT INTO query_audit_log (sql, success, row_count, duration_ms, session_id, source)
                VALUES (:sql, :success, :row_count, :duration_ms, :session_id, :source)""",
                e,
            )
    except Exception as ex:
        logger.error(f"Audit flush failed: {ex}")


def flush():
    with _lock:
        _flush()


def get_recent(limit: int = 50) -> list[dict]:
    _ensure_table()
    flush()
    try:
        from core.database import execute_query
        return execute_query(
            "SELECT * FROM query_audit_log ORDER BY id DESC LIMIT ?", [limit]
        )
    except Exception:
        return []


def get_recent_slow(threshold_ms: float = 2000, limit: int = 20) -> list[dict]:
    _ensure_table()
    flush()
    try:
        from core.database import execute_query
        return execute_query(
            "SELECT * FROM query_audit_log WHERE duration_ms > ? ORDER BY duration_ms DESC LIMIT ?",
            [threshold_ms, limit],
        )
    except Exception:
        return []


def get_stats() -> dict:
    _ensure_table()
    flush()
    try:
        from core.database import execute_query
        total = execute_query("SELECT COUNT(*) as cnt FROM query_audit_log")
        avg = execute_query("SELECT AVG(duration_ms) as avg_ms FROM query_audit_log")
        slow = execute_query("SELECT COUNT(*) as cnt FROM query_audit_log WHERE duration_ms > 2000")
        failed = execute_query("SELECT COUNT(*) as cnt FROM query_audit_log WHERE success = 0")
        return {
            "total_queries": total[0]["cnt"] if total else 0,
            "avg_duration_ms": round(avg[0]["avg_ms"], 1) if avg and avg[0]["avg_ms"] else 0,
            "slow_queries": slow[0]["cnt"] if slow else 0,
            "failed_queries": failed[0]["cnt"] if failed else 0,
        }
    except Exception:
        return {"total_queries": 0, "avg_duration_ms": 0, "slow_queries": 0, "failed_queries": 0}
