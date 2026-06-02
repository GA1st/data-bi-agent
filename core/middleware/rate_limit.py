import time
import threading
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.logger import get_logger
from config import settings

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.max_requests = settings.rate_limit_max_requests
        self.window_seconds = settings.rate_limit_window_seconds
        self._requests: defaultdict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

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

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path.startswith("/static") or path in ("/", "/favicon.ico"):
            return await call_next(request)

        key = self._client_key(request)
        if self._is_limited(key):
            logger.warning(f"Rate limited: {key} on {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Too many requests. Limit: {self.max_requests}/{self.window_seconds}s",
                    }
                },
            )
        return await call_next(request)
