import json
import threading
from fastapi import APIRouter
from pydantic import BaseModel
from core.database import execute_query, get_table_names, get_table_columns, get_sample_data
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["data"])


# --- Saved Queries ---

_saved_lock = threading.Lock()
_saved_queries: list[dict] = []


class SavedQueryCreate(BaseModel):
    name: str
    question: str
    sql: str


@router.get("/saved-queries")
async def list_saved_queries():
    with _saved_lock:
        return {"queries": _saved_queries}


@router.post("/saved-queries")
async def create_saved_query(req: SavedQueryCreate):
    with _saved_lock:
        entry = {
            "id": len(_saved_queries) + 1,
            "name": req.name,
            "question": req.question,
            "sql": req.sql,
        }
        _saved_queries.append(entry)
        logger.info(f"Saved query: {req.name}")
        return entry


@router.delete("/saved-queries/{query_id}")
async def delete_saved_query(query_id: int):
    with _saved_lock:
        global _saved_queries
        _saved_queries = [q for q in _saved_queries if q["id"] != query_id]
    return {"message": "已删除"}


# --- Data Explorer ---

@router.get("/tables")
async def list_tables():
    tables = get_table_names()
    result = []
    for t in tables:
        if t.startswith("sqlite_"):
            continue
        cols = get_table_columns(t)
        count_row = execute_query(f'SELECT COUNT(*) as cnt FROM "{t}"')
        count = count_row[0]["cnt"] if count_row else 0
        result.append({
            "name": t,
            "columns": cols,
            "row_count": count,
        })
    return {"tables": result}


@router.get("/tables/{table_name}/data")
async def table_data(table_name: str, page: int = 1, page_size: int = 50):
    offset = (page - 1) * page_size
    rows = execute_query(f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', [page_size, offset])
    count_row = execute_query(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
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
