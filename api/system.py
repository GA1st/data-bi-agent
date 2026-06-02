from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.logger import get_logger
from core.metrics import metrics
from core.cache import _hits, _misses, _stats_lock
from core.session import sessions
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
async def audit_recent(limit: int = Query(50, ge=1, le=200)):
    return {"entries": get_recent(limit)}


@router.get("/audit/slow")
async def audit_slow(threshold_ms: float = Query(2000, ge=0), limit: int = Query(20, ge=1, le=200)):
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


# --- Metrics ---

@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    with _stats_lock:
        h, m = _hits, _misses
    total = h + m
    hit_rate = h / total if total > 0 else 0
    metrics.set_gauge("cache_hit_rate", round(hit_rate, 4))
    metrics.set_gauge("cache_hits_total", h)
    metrics.set_gauge("cache_misses_total", m)
    metrics.set_gauge("active_sessions", sessions.active_sessions)

    audit = get_stats()
    metrics.set_gauge("audit_total_queries", audit["total_queries"])
    metrics.set_gauge("audit_failed_queries", audit["failed_queries"])
    metrics.set_gauge("audit_slow_queries", audit["slow_queries"])

    return metrics.expose()
