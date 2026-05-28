from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from core.logger import setup_logging, get_logger
from core.database import init_db, close_db, get_table_names
from core.session import sessions
from core.scheduler import start_scheduler, stop_scheduler
from services.data_initializer import init_demo_data
from api.chat import router as chat_router
from api.dashboard import router as dashboard_router
from api.database_manage import router as db_router
from api.data_explorer import router as explorer_router
from api.system import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger(__name__)

    logger.info("Initializing database...")
    init_db()

    logger.info("Loading demo data...")
    created = init_demo_data()
    if created:
        logger.info("Demo data generated")
    else:
        logger.info("Demo data already exists")

    tables = get_table_names()
    logger.info(f"Available tables: {tables}")
    logger.info(f"Data BI Agent started: http://localhost:{settings.app_port}")
    logger.info(f"Auth: {'enabled' if settings.auth_enabled else 'disabled'}")
    logger.info(f"Rate limit: {'enabled' if settings.rate_limit_enabled else 'disabled'}")
    logger.info(f"Cache: {'enabled' if settings.cache_enabled else 'disabled'}")

    start_scheduler()

    yield

    logger.info("Shutting down...")
    stop_scheduler()
    close_db()


app = FastAPI(
    title="Data BI Agent",
    description="智能数据分析 + BI Agent — 自然语言查询数据库、自动生成报表、异常检测",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware registration (Starlette executes in REVERSE order — last added runs first)
# Request flow: CORS → SecurityHeaders → Auth → RateLimit → Logging → ErrorHandler → Route
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from core.middleware import (
    SecurityHeadersMiddleware,
    AuthMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    ErrorHandlerMiddleware,
)

app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(db_router)
app.include_router(explorer_router)
app.include_router(system_router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    index_file = Path(__file__).parent / "static" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Data BI Agent API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
