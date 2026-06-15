"""
Multi-datasource support — connect to different databases at runtime.

Supports:
- SQLite (default, built-in)
- CSV file upload (auto-imported to SQLite)
- MySQL / PostgreSQL (via SQLAlchemy, optional)
"""
import csv
import io
import uuid
from pathlib import Path

from core.database import _validate_identifier, execute_query, execute_update
from core.exceptions import ValidationError
from core.logger import get_logger

logger = get_logger(__name__)


def import_csv_to_table(csv_path: str, table_name: str | None = None, delimiter: str = ",") -> dict:
    """Import a CSV file as a new table in the current database."""
    path = Path(csv_path)
    if not path.exists():
        raise ValidationError(f"CSV file not found: {csv_path}")

    if table_name is None:
        table_name = path.stem.replace("-", "_").replace(" ", "_")
    table_name = _validate_identifier(table_name)

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        headers = next(reader)
        rows = list(reader)

    if not headers:
        raise ValidationError("CSV file is empty")

    clean_headers = []
    for h in headers:
        clean = h.strip().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
        if not clean:
            clean = f"col_{len(clean_headers)}"
        clean = _validate_identifier(clean)
        clean_headers.append(clean)

    col_types = _detect_types(rows, clean_headers)

    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    col_defs = [f'  "{h}" {col_types[h]}' for h in clean_headers]
    create_sql += ",\n".join(col_defs) + "\n)"
    execute_update(create_sql)

    inserted = 0
    for row in rows:
        if len(row) != len(clean_headers):
            continue
        placeholders = ", ".join([f":p{i}" for i in range(len(clean_headers))])
        params = {f"p{i}": _cast_val(row[i], col_types[clean_headers[i]]) for i in range(len(clean_headers))}
        execute_update(
            f'INSERT INTO "{table_name}" ({", ".join(f"{h}" for h in clean_headers)}) VALUES ({placeholders})',
            params,
        )
        inserted += 1

    logger.info(f"CSV imported: {table_name} ({inserted} rows, {len(clean_headers)} columns)")
    return {
        "table_name": table_name,
        "rows": inserted,
        "columns": clean_headers,
        "column_types": col_types,
    }


def import_csv_bytes(filename: str, content: bytes, delimiter: str = ",") -> dict:
    """Import CSV from uploaded bytes (used by API)."""
    base_name = Path(filename).stem.replace("-", "_").replace(" ", "_")
    table_name = f"{base_name}_{uuid.uuid4().hex[:6]}"
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    headers = next(reader)
    rows = list(reader)

    if not headers:
        raise ValidationError("CSV is empty")

    table_name = _validate_identifier(table_name)
    clean_headers = []
    for h in headers:
        clean = h.strip().replace(" ", "_").replace("-", "_")
        if not clean:
            clean = f"col_{len(clean_headers)}"
        clean = _validate_identifier(clean)
        clean_headers.append(clean)

    col_types = _detect_types(rows, clean_headers)

    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n'
    col_defs = [f'  "{h}" {col_types[h]}' for h in clean_headers]
    create_sql += ",\n".join(col_defs) + "\n)"
    execute_update(create_sql)

    inserted = 0
    for row in rows:
        if len(row) != len(clean_headers):
            continue
        placeholders = ", ".join([f":p{i}" for i in range(len(clean_headers))])
        params = {f"p{i}": _cast_val(row[i], col_types[clean_headers[i]]) for i in range(len(clean_headers))}
        execute_update(
            f'INSERT INTO "{table_name}" ({", ".join(f"{h}" for h in clean_headers)}) VALUES ({placeholders})',
            params,
        )
        inserted += 1

    logger.info(f"CSV uploaded: {table_name} ({inserted} rows)")
    return {"table_name": table_name, "rows": inserted, "columns": clean_headers}


def list_datasources() -> list[dict]:
    """List all available data sources (tables in current DB)."""
    from core.database import get_table_names
    sources = []
    for name in get_table_names():
        if name.startswith("sqlite_") or name == "query_audit_log":
            continue
        try:
            cnt = execute_query(f'SELECT COUNT(*) as c FROM "{name}"')
            sources.append({"name": name, "type": "sqlite", "rows": cnt[0]["c"] if cnt else 0})
        except Exception:
            sources.append({"name": name, "type": "sqlite", "rows": 0})
    return sources


def _detect_types(rows: list[list[str]], headers: list[str]) -> dict[str, str]:
    """Auto-detect column types from CSV data."""
    types = {}
    for i, header in enumerate(headers):
        is_int = True
        is_float = True
        for row in rows[:100]:
            if i >= len(row) or not row[i].strip():
                continue
            try:
                int(row[i])
            except ValueError:
                is_int = False
            try:
                float(row[i])
            except ValueError:
                is_float = False
        if is_int:
            types[header] = "INTEGER"
        elif is_float:
            types[header] = "REAL"
        else:
            types[header] = "TEXT"
    return types


def _cast_val(val: str, col_type: str):
    if not val or not val.strip():
        return None
    if col_type == "INTEGER":
        try:
            return int(val)
        except ValueError:
            return val
    if col_type == "REAL":
        try:
            return float(val)
        except ValueError:
            return val
    return val
