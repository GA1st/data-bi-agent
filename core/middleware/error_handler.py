import traceback

from starlette.requests import Request
from starlette.responses import JSONResponse

from core.exceptions import AppError
from core.logger import get_logger
from config import settings

logger = get_logger(__name__)


class ErrorHandlerMiddleware:
    """Pure ASGI middleware — does not buffer StreamingResponse."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = ""
        try:
            await self.app(scope, receive, send)
        except AppError as exc:
            request_id = getattr(request.state, "request_id", "")
            logger.warning(
                f"AppError: {exc.error_code} - {exc.detail}",
                extra={"request_id": request_id},
            )
            response = JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.error_code,
                        "message": exc.detail,
                    },
                    "request_id": request_id,
                },
            )
            await response(scope, receive, send)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "")
            logger.error(
                f"Unhandled exception: {traceback.format_exc()}",
                extra={"request_id": request_id},
            )
            msg = str(exc) if settings.debug else "Internal server error"
            if not settings.debug:
                logger.error(f"Masked error detail: {str(exc)[:200]}")
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": msg,
                    },
                    "request_id": request_id,
                },
            )
            await response(scope, receive, send)
