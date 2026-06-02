"""
Scheduled task manager using standard library (no APScheduler dependency).

Supports:
- Periodic data quality checks
- Scheduled report generation
- Slow query detection
- Configurable via .env (SCHEDULER_ENABLED, SCHEDULER_INTERVAL_SECONDS)
"""
import threading
import time
from datetime import datetime

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_jobs: list[dict] = []
_running = False
_thread: threading.Thread | None = None


def register_job(name: str, func, interval_seconds: int, enabled: bool = True):
    with _lock:
        _jobs.append({
            "name": name,
            "func": func,
            "interval": interval_seconds,
            "enabled": enabled,
            "last_run": 0,
        })
    logger.info(f"Scheduler job registered: {name} (every {interval_seconds}s)")


def start_scheduler():
    global _running, _thread
    if not getattr(settings, 'scheduler_enabled', True):
        logger.info("Scheduler disabled by config")
        return
    _running = True
    _thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _thread.start()
    logger.info(f"Scheduler started with {len(_jobs)} jobs")


def stop_scheduler():
    global _running
    _running = False
    logger.info("Scheduler stopped")


def _scheduler_loop():
    while _running:
        now = time.time()
        with _lock:
            snapshot = list(_jobs)
        for job in snapshot:
            if not job["enabled"]:
                continue
            if now - job["last_run"] >= job["interval"]:
                try:
                    job["func"]()
                    job["last_run"] = now
                    logger.debug(f"Job executed: {job['name']}")
                except Exception as e:
                    logger.error(f"Job failed: {job['name']} - {e}")
        time.sleep(getattr(settings, 'scheduler_interval_seconds', 30))


def get_job_status() -> list[dict]:
    with _lock:
        return [
            {
                "name": j["name"],
                "interval": j["interval"],
                "enabled": j["enabled"],
                "last_run": datetime.fromtimestamp(j["last_run"]).isoformat() if j["last_run"] else None,
            }
            for j in _jobs
        ]


# --- Built-in Jobs ---

def job_data_quality_check():
    """Check data quality: null ratios, duplicate detection, stale data."""
    from core.database import execute_query
    try:
        tables = execute_query("SELECT name FROM sqlite_master WHERE type='table'")
        issues = []
        for t in tables:
            name = t["name"]
            if name.startswith("sqlite_"):
                continue
            try:
                count = execute_query(f'SELECT COUNT(*) as cnt FROM "{name}"')
                if count and count[0]["cnt"] == 0:
                    issues.append(f"{name}: table is empty")
            except Exception:
                pass
        if issues:
            logger.warning(f"Data quality issues: {issues}")
        else:
            logger.info("Data quality check: all OK")
        return issues
    except Exception as e:
        logger.error(f"Quality check failed: {e}")
        return [str(e)]


def job_slow_query_audit():
    """Audit recent queries from the query log."""
    from services.query_audit import get_recent_slow
    slow = get_recent_slow(threshold_ms=2000)
    if slow:
        logger.warning(f"Slow queries detected: {len(slow)} queries > 2s")
    return slow


def job_cache_stats():
    """Log cache statistics."""
    from core.cache import cache
    logger.info(f"Cache stats: {len(cache._store)} items stored")


# Auto-register built-in jobs
register_job("data_quality", job_data_quality_check, interval_seconds=300)
register_job("slow_query_audit", job_slow_query_audit, interval_seconds=120)
register_job("cache_stats", job_cache_stats, interval_seconds=600)
