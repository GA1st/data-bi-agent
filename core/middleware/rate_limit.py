import threading
import time
from collections import defaultdict, deque

from starlette.requests import Request
from starlette.responses import JSONResponse

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware:
    """Pure ASGI middleware — does not buffer StreamingResponse."""

    def __init__(self, app):
        self.app = app
        self.max_requests = settings.rate_limit_max_requests
        self.window_seconds = settings.rate_limit_window_seconds
        self._requests: defaultdict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path
        if path.startswith("/static") or path in ("/", "/favicon.ico"):
            await self.app(scope, receive, send)
            return

        key = self._client_key(request)
        if self._is_limited(key):
            logger.warning(f"Rate limited: {key} on {path}")
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Too many requests. Limit: {self.max_requests}/{self.window_seconds}s",
                    }
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _client_key(self, request: Request) -> str:
        client_ip = request.client.host if request.client else "unknown"
        if settings.trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For", "")
            first_ip = forwarded.split(",")[0].strip() if forwarded else ""
            if first_ip and client_ip in settings.trusted_proxies:
                return first_ip
        return client_ip

    def _is_limited(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._requests[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                return True
            q.append(now)
            return False
