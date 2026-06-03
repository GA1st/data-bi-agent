import threading
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from core.database import execute_query, get_table_names, get_table_columns, get_sample_data, _validate_identifier
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["data"])


# --- Saved Queries ---

_saved_lock = threading.Lock()
_saved_queries: list[dict] = []
_next_id = 1


class SavedQueryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    question: str = Field(..., max_length=500)
    sql: str = Field(..., max_length=5000)


@router.get("/saved-queries")
async def list_saved_queries():
    with _saved_lock:
        return {"queries": list(_saved_queries)}


@router.post("/saved-queries")
async def create_saved_query(req: SavedQueryCreate):
    with _saved_lock:
        global _next_id
        entry = {
            "id": _next_id,
            "name": req.name,
            "question": req.question,
            "sql": req.sql,
        }
        _next_id += 1
        _saved_queries.append(entry)
        logger.info(f"Saved query: {req.name}")
        return entry


@router.delete("/saved-queries/{query_id}")
async def delete_saved_query(query_id: int):
    with _saved_lock:
        global _saved_queries
        _saved_queries = [q for q in _saved_queries if q["id"] != query_id]
    return {"message": "已删除"}


def _safe_table(name: str) -> str:
    try:
        return _validate_identifier(name)
    except Exception:
        raise HTTPException(400, f"Invalid table name: {name}")


# --- Data Explorer ---

@router.get("/tables")
async def list_tables():
    tables = get_table_names()
    result = []
    for t in tables:
        if t.startswith("sqlite_"):
            continue
        safe = _safe_table(t)
        cols = get_table_columns(safe)
        count_row = execute_query(f'SELECT COUNT(*) as cnt FROM "{safe}"')
        count = count_row[0]["cnt"] if count_row else 0
        result.append({
            "name": t,
            "columns": cols,
            "row_count": count,
        })
    return {"tables": result}


@router.get("/tables/{table_name}/data")
async def table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    safe = _safe_table(table_name)
    offset = (page - 1) * page_size
    rows = execute_query(f'SELECT * FROM "{safe}" LIMIT ? OFFSET ?', [page_size, offset])
    count_row = execute_query(f'SELECT COUNT(*) as cnt FROM "{safe}"')
    total = count_row[0]["cnt"] if count_row else 0
    columns = list(rows[0].keys()) if rows else []
    return {
        "data": rows,
        "columns": columns,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
