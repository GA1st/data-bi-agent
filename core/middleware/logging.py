import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.logger import get_logger
from core.metrics import metrics

logger = get_logger("request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.monotonic()

        logger.info(
            f"--> {request.method} {request.url.path}",
            extra={"request_id": request_id},
        )

        response = await call_next(request)

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            f"<-- {request.method} {request.url.path} {response.status_code} {elapsed_ms:.1f}ms",
            extra={"request_id": request_id},
        )

        metrics.inc_counter("http_requests_total", labels={"method": request.method, "status": str(response.status_code)})
        metrics.observe_histogram("http_request_duration_ms", elapsed_ms, labels={"method": request.method, "path": request.url.path})

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response
