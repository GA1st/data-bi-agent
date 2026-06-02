import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.logger import get_logger
from config import settings

logger = get_logger(__name__)

PUBLIC_PATHS = {"/", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)

        path = request.url.path

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(f"Auth failed: no key for {path}")
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "API key required. Pass X-API-Key header."}},
            )

        if not settings.auth_api_key:
            logger.error("Auth enabled but API key not configured")
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "AUTH_CONFIG_ERROR", "message": "Server auth misconfigured"}},
            )

        if not hmac.compare_digest(api_key, settings.auth_api_key):
            logger.warning(f"Auth failed: invalid key for {path}")
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "Invalid API key"}},
            )

        return await call_next(request)
