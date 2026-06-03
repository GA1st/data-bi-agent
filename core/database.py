import re
import sqlite3
import threading
from pathlib import Path

from config import settings
from core.logger import get_logger
from core.exceptions import DatabaseError, ValidationError

logger = get_logger(__name__)

_local = threading.local()
_db_path: str = ""
_SCHEMA_CACHE_KEY = "db_full_schema"


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        db_path = _db_path or settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        logger.info("Database connection established")
    return conn


def _validate_identifier(name: str) -> str:
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValidationError(f"Invalid SQL identifier: {name}")
    return name


def init_db(db_url: str | None = None):
    global _db_path
    if db_url:
        _db_path = db_url.replace("sqlite:///", "")
    from core.cache import cache
    cache.delete(_SCHEMA_CACHE_KEY)
    _get_conn()


def execute_query(sql: str, params: dict | None = None) -> list[dict]:
    try:
        conn = _get_conn()
        cursor = conn.execute(sql, params or {})
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise DatabaseError(str(e)) from e


def execute_update(sql: str, params: dict | None = None) -> int:
    try:
        conn = _get_conn()
        cursor = conn.execute(sql, params or {})
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise DatabaseError(str(e)) from e


def get_table_names() -> list[str]:
    rows = execute_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r["name"] for r in rows]


def get_table_columns(table_name: str) -> list[dict]:
    safe_name = _validate_identifier(table_name)
    rows = execute_query(f"PRAGMA table_info('{safe_name}')")
    return [
        {
            "name": r["name"],
            "type": r["type"],
            "primary_key": bool(r["pk"]),
            "nullable": not r["notnull"],
        }
        for r in rows
    ]


def get_full_schema() -> str:
    from core.cache import cache
    cached_schema = cache.get(_SCHEMA_CACHE_KEY)
    if cached_schema is not None:
        return cached_schema

    tables = get_table_names()
    schema_parts = []
    for table in tables:
        safe = _validate_identifier(table)
        cols = get_table_columns(safe)
        col_defs = []
        for c in cols:
            pk = " PRIMARY KEY" if c["primary_key"] else ""
            nullable = "" if c["nullable"] else " NOT NULL"
            col_defs.append(f"  {c['name']} {c['type']}{pk}{nullable}")
        schema_parts.append(f"CREATE TABLE {safe} (\n" + ",\n".join(col_defs) + "\n);")

        fks = execute_query(f"PRAGMA foreign_key_list('{safe}')")
        for fk in fks:
            schema_parts.append(f"-- {safe}.{fk['from']} -> {fk['table']}.{fk['to']}")

    schema = "\n\n".join(schema_parts)
    cache.set(_SCHEMA_CACHE_KEY, schema)
    logger.debug("Schema built and cached")
    return schema


def get_sample_data(table_name: str, limit: int = 5) -> list[dict]:
    safe = _validate_identifier(table_name)
    return execute_query(f"SELECT * FROM {safe} LIMIT {limit}")


def close_db():
    conn = getattr(_local, "conn", None)
    if conn:
        conn.close()
        _local.conn = None
        logger.info("Database connection closed")
