from fastapi import APIRouter

from core.database import init_db, execute_query, get_table_names, get_full_schema, close_db, _validate_identifier
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/database", tags=["database"])


@router.post("/init")
async def initialize_database():
    init_db()
    tables = get_table_names()
    logger.info(f"Database re-initialized: {tables}")
    return {"message": "数据库初始化成功", "tables": tables}


@router.get("/status")
async def database_status():
    try:
        tables = get_table_names()
        table_stats = []
        for t in tables:
            safe = _validate_identifier(t)
            count_result = execute_query(f'SELECT COUNT(*) as cnt FROM "{safe}"')
            count = count_result[0]["cnt"] if count_result else 0
            table_stats.append({"name": t, "rows": count})
        return {"connected": True, "tables": table_stats}
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        return {"connected": False, "error": str(e)}


@router.get("/schema")
async def get_schema():
    schema = get_full_schema()
    return {"schema": schema}
