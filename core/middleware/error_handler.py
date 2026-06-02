import traceback

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.exceptions import AppError
from core.logger import get_logger
from config import settings

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = getattr(request.state, "request_id", "")
        try:
            response = await call_next(request)
            return response
        except AppError as exc:
            logger.warning(
                f"AppError: {exc.error_code} - {exc.detail}",
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.error_code,
                        "message": exc.detail,
                    },
                    "request_id": request_id,
                },
            )
        except Exception as exc:
            logger.error(
                f"Unhandled exception: {traceback.format_exc()}",
                extra={"request_id": request_id},
            )
            msg = str(exc) if settings.debug else "Internal server error"
            if not settings.debug:
                logger.error(f"Masked error detail: {str(exc)[:200]}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": msg,
                    },
                    "request_id": request_id,
                },
            )
