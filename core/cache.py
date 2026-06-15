import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

_hits = 0
_misses = 0
_stats_lock = threading.Lock()


class TTLCache:
    def __init__(self, ttl: int | None = None, max_size: int | None = None):
        self.ttl = ttl or settings.cache_ttl_seconds
        self.max_size = max_size or settings.cache_max_size
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        global _hits, _misses
        if not settings.cache_enabled:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                with _stats_lock:
                    _misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                with _stats_lock:
                    _misses += 1
                return None
            with _stats_lock:
                _hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        if not settings.cache_enabled:
            return
        with self._lock:
            if len(self._store) >= self.max_size:
                self._evict_oldest()
            self._store[key] = (value, time.monotonic() + self.ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_oldest(self) -> None:
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]


cache = TTLCache()


def cached(key_prefix: str, ttl: int | None = None):
    def decorator(func: Callable) -> Callable:
        _cache = TTLCache(ttl=ttl) if ttl else cache

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{key_prefix}:{func.__qualname__}"
            result = _cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit: {key}")
                return result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result
        return wrapper
    return decorator
