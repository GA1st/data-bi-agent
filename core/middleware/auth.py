import hmac

from starlette.requests import Request
from starlette.responses import JSONResponse

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

PUBLIC_PATHS = {"/", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static",)


class AuthMiddleware:
    """Pure ASGI middleware — does not buffer StreamingResponse."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if not settings.auth_enabled:
            await self.app(scope, receive, send)
            return

        path = request.url.path

        if request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(f"Auth failed: no key for {path}")
            response = JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "API key required. Pass X-API-Key header."}},
            )
            await response(scope, receive, send)
            return

        if not settings.auth_api_key:
            logger.error("Auth enabled but API key not configured")
            response = JSONResponse(
                status_code=500,
                content={"error": {"code": "AUTH_CONFIG_ERROR", "message": "Server auth misconfigured"}},
            )
            await response(scope, receive, send)
            return

        if not hmac.compare_digest(api_key, settings.auth_api_key):
            logger.warning(f"Auth failed: invalid key for {path}")
            response = JSONResponse(
                status_code=401,
                content={"error": {"code": "AUTH_ERROR", "message": "Invalid API key"}},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
