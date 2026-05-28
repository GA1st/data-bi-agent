from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from core.logger import get_logger
from core.scheduler import get_job_status
from services.query_audit import get_stats, get_recent, get_recent_slow
from services.multi_datasource import import_csv_bytes, list_datasources

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


# --- Audit ---

@router.get("/audit/stats")
async def audit_stats():
    return get_stats()


@router.get("/audit/recent")
async def audit_recent(limit: int = 50):
    return {"entries": get_recent(limit)}


@router.get("/audit/slow")
async def audit_slow(threshold_ms: float = 2000, limit: int = 20):
    return {"entries": get_recent_slow(threshold_ms, limit)}


# --- Scheduler ---

@router.get("/scheduler/status")
async def scheduler_status():
    return {"jobs": get_job_status()}


# --- Data Sources ---

@router.get("/datasources")
async def datasources():
    return {"sources": list_datasources()}


@router.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".tsv")):
        raise HTTPException(400, "仅支持 CSV/TSV 文件")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 50MB")
    delimiter = "\t" if file.filename.endswith(".tsv") else ","
    try:
        result = import_csv_bytes(file.filename, content, delimiter)
        logger.info(f"CSV uploaded: {result['table_name']} ({result['rows']} rows)")
        return result
    except Exception as e:
        raise HTTPException(400, str(e))
