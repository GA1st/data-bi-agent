import time
import uuid

from starlette.requests import Request

from core.logger import get_logger
from core.metrics import metrics

logger = get_logger("request")


class RequestLoggingMiddleware:
    """Pure ASGI middleware — does not buffer StreamingResponse."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.monotonic()

        logger.info(
            f"--> {request.method} {request.url.path}",
            extra={"request_id": request_id},
        )

        status_code = 200

        async def send_with_logging(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        await self.app(scope, receive, send_with_logging)

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            f"<-- {request.method} {request.url.path} {status_code} {elapsed_ms:.1f}ms",
            extra={"request_id": request_id},
        )

        metrics.inc_counter("http_requests_total", labels={"method": request.method, "status": str(status_code)})
        metrics.observe_histogram("http_request_duration_ms", elapsed_ms, labels={"method": request.method, "path": request.url.path})
